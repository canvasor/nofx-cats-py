from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from cats_py.domain.enums import DecisionStatus, PositionDirection, Side
from cats_py.domain.models import AccountState, BalanceState, FeatureVector, PositionState, TradeDecision
from cats_py.journal.recorder import JournalRecorder

USDT = "USDT"
POSITION_SIDE = "BOTH"
DECIMAL_PLACES = Decimal("0.00000001")


@dataclass(slots=True)
class PaperFillResult:
    symbol: str
    fill_price: Decimal
    fill_quantity: Decimal
    realized_pnl_delta: Decimal
    resulting_quantity: Decimal


class PaperExecutionService:
    def __init__(
        self,
        *,
        journal: JournalRecorder,
        starting_balance: float = 10_000.0,
        slippage_bps: float = 1.0,
        taker_fee_bps: float = 4.0,
        funding_interval_hours: float = 8.0,
    ) -> None:
        self.journal = journal
        self.slippage_bps = Decimal(str(slippage_bps))
        self.taker_fee_bps = Decimal(str(taker_fee_bps))
        self.funding_interval_hours = Decimal(str(funding_interval_hours))
        self.realized_pnl = Decimal("0")
        self.fees_paid = Decimal("0")
        self.funding_pnl = Decimal("0")
        self.turnover_notional = Decimal("0")
        self.initial_balance = Decimal(str(starting_balance))
        self.last_funding_applied_at: dict[str, datetime] = {}
        self.state = AccountState()
        self.state.upsert_balance(
            BalanceState(
                asset=USDT,
                wallet_balance=self.initial_balance,
                available_balance=self.initial_balance,
                cross_wallet_balance=self.initial_balance,
            )
        )

    def account_state(self, *, now: datetime | None = None) -> AccountState:
        self.state.record_user_stream_event(now)
        self.state.mark_reconciled(now)
        return self.state

    def mark_to_market(self, features: dict[str, FeatureVector], *, cycle_id: str, ts: datetime) -> None:
        funding_delta = Decimal("0")
        for position in self.state.positions.values():
            if not position.is_open:
                continue
            feature = features.get(position.symbol)
            if feature is None or feature.reference_price <= 0:
                continue

            symbol_funding_delta = self._maybe_apply_funding(position, feature, ts)
            funding_delta += symbol_funding_delta
            mark_price = Decimal(str(feature.reference_price))
            position.mark_price = mark_price
            position.notional = position.quantity * mark_price
            position.unrealized_pnl = (mark_price - position.entry_price) * position.quantity
            position.updated_at = ts

        if funding_delta != 0:
            self.funding_pnl += funding_delta
            self._sync_balance()
        self.account_state(now=ts)
        self._record_pnl_snapshot(cycle_id=cycle_id, ts=ts, funding_pnl_delta=funding_delta)

    def apply_decision(
        self,
        decision: TradeDecision,
        feature: FeatureVector,
        *,
        cycle_id: str,
        ts: datetime,
    ) -> PaperFillResult | None:
        if decision.status != DecisionStatus.EXECUTE or decision.side is None or decision.risk is None:
            return None
        if feature.reference_price <= 0:
            return None

        fill_price = self._apply_slippage(Decimal(str(feature.reference_price)), decision.side)
        fill_quantity = (Decimal(str(decision.risk.approved_notional)) / fill_price).quantize(DECIMAL_PLACES)
        signed_fill_quantity = fill_quantity if decision.side == Side.BUY else -fill_quantity
        position_key = (decision.symbol, POSITION_SIDE)
        position = self.state.positions.get(
            position_key,
            PositionState(symbol=decision.symbol, position_side=POSITION_SIDE),
        )

        old_quantity = position.quantity
        old_entry_price = position.entry_price
        realized_delta = Decimal("0")
        turnover_delta = abs(fill_quantity * fill_price)
        fee_delta = (turnover_delta * self.taker_fee_bps / Decimal("10000")).quantize(
            DECIMAL_PLACES,
            rounding=ROUND_HALF_UP,
        )
        new_quantity = old_quantity + signed_fill_quantity

        if old_quantity == 0 or old_quantity * signed_fill_quantity > 0:
            new_entry_price = self._weighted_entry_price(old_quantity, old_entry_price, signed_fill_quantity, fill_price)
        else:
            closed_quantity = min(abs(old_quantity), abs(signed_fill_quantity))
            realized_delta = (fill_price - old_entry_price) * closed_quantity * self._quantity_sign(old_quantity)
            if abs(signed_fill_quantity) < abs(old_quantity):
                new_entry_price = old_entry_price
            elif abs(signed_fill_quantity) == abs(old_quantity):
                new_entry_price = Decimal("0")
            else:
                new_entry_price = fill_price

        position.quantity = new_quantity
        position.entry_price = new_entry_price
        position.mark_price = fill_price
        position.notional = new_quantity * fill_price
        position.unrealized_pnl = (fill_price - new_entry_price) * new_quantity if new_quantity != 0 else Decimal("0")
        position.direction = self._direction_for_quantity(new_quantity)
        position.leverage = max(int(round(decision.risk.approved_leverage)), 1)
        position.updated_at = ts

        self.state.upsert_position(position)
        self.realized_pnl += realized_delta
        self.fees_paid += fee_delta
        self.turnover_notional += turnover_delta
        self._sync_balance()
        self.account_state(now=ts)

        result = PaperFillResult(
            symbol=decision.symbol,
            fill_price=fill_price,
            fill_quantity=fill_quantity,
            realized_pnl_delta=realized_delta,
            resulting_quantity=new_quantity,
        )
        self.journal.record(
            "paper_fill_log",
            {
                "ts": ts.isoformat(),
                "cycle_id": cycle_id,
                "decision_id": decision.decision_id,
                "symbol": decision.symbol,
                "side": decision.side.value,
                "fill_price": float(fill_price),
                "fill_quantity": float(fill_quantity),
                "target_notional": decision.risk.approved_notional,
                "realized_pnl_delta": float(realized_delta),
                "resulting_quantity": float(new_quantity),
                "turnover_notional_delta": float(turnover_delta),
                "fee_paid_delta": float(fee_delta),
            },
        )
        self._record_pnl_snapshot(
            cycle_id=cycle_id,
            ts=ts,
            fee_paid_delta=fee_delta,
            turnover_notional_delta=turnover_delta,
        )
        return result

    def _record_pnl_snapshot(
        self,
        *,
        cycle_id: str,
        ts: datetime,
        funding_pnl_delta: Decimal = Decimal("0"),
        fee_paid_delta: Decimal = Decimal("0"),
        turnover_notional_delta: Decimal = Decimal("0"),
    ) -> None:
        balance = self.state.balances[USDT]
        self.journal.record(
            "paper_pnl_log",
            {
                "ts": ts.isoformat(),
                "cycle_id": cycle_id,
                "wallet_balance": float(balance.wallet_balance),
                "realized_pnl": float(self.realized_pnl),
                "funding_pnl": float(self.funding_pnl),
                "funding_pnl_delta": float(funding_pnl_delta),
                "fees_paid": float(self.fees_paid),
                "fee_paid_delta": float(fee_paid_delta),
                "turnover_notional": float(self.turnover_notional),
                "turnover_notional_delta": float(turnover_notional_delta),
                "unrealized_pnl": float(self.state.total_unrealized_pnl()),
                "equity": float(self.state.total_equity()),
                "gross_exposure": self.state.to_snapshot(now=ts).gross_exposure,
                "open_positions": self.state.open_position_count(),
                "positions": [
                    {
                        "symbol": position.symbol,
                        "quantity": float(position.quantity),
                        "entry_price": float(position.entry_price),
                        "mark_price": float(position.mark_price),
                        "unrealized_pnl": float(position.unrealized_pnl),
                    }
                    for position in self.state.positions.values()
                    if position.is_open
                ],
            },
        )

    def _sync_balance(self) -> None:
        balance = self.state.balances[USDT]
        balance.wallet_balance = (self.initial_balance + self.realized_pnl + self.funding_pnl - self.fees_paid).quantize(
            DECIMAL_PLACES,
            rounding=ROUND_HALF_UP,
        )
        balance.available_balance = balance.wallet_balance
        balance.cross_wallet_balance = balance.wallet_balance

    def _maybe_apply_funding(self, position: PositionState, feature: FeatureVector, ts: datetime) -> Decimal:
        if feature.funding_rate == 0:
            return Decimal("0")

        last_applied_at = self.last_funding_applied_at.get(position.symbol)
        if self.funding_interval_hours > 0:
            if last_applied_at is None:
                self.last_funding_applied_at[position.symbol] = ts
                return Decimal("0")
            elapsed_hours = Decimal(str((ts - last_applied_at).total_seconds() / 3600))
            if elapsed_hours < self.funding_interval_hours:
                return Decimal("0")

        self.last_funding_applied_at[position.symbol] = ts
        notional = abs(position.quantity * Decimal(str(feature.reference_price)))
        if notional == 0:
            return Decimal("0")
        position_sign = self._quantity_sign(position.quantity)
        funding_rate = Decimal(str(feature.funding_rate))
        return (-(notional * funding_rate * position_sign)).quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP)

    def _apply_slippage(self, price: Decimal, side: Side) -> Decimal:
        multiplier = Decimal("1") + (self.slippage_bps / Decimal("10000"))
        if side == Side.SELL:
            multiplier = Decimal("1") - (self.slippage_bps / Decimal("10000"))
        return (price * multiplier).quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def _quantity_sign(quantity: Decimal) -> Decimal:
        if quantity > 0:
            return Decimal("1")
        if quantity < 0:
            return Decimal("-1")
        return Decimal("0")

    @staticmethod
    def _direction_for_quantity(quantity: Decimal) -> PositionDirection:
        if quantity > 0:
            return PositionDirection.LONG
        if quantity < 0:
            return PositionDirection.SHORT
        return PositionDirection.FLAT

    @staticmethod
    def _weighted_entry_price(
        old_quantity: Decimal,
        old_entry_price: Decimal,
        fill_quantity: Decimal,
        fill_price: Decimal,
    ) -> Decimal:
        total_quantity = abs(old_quantity) + abs(fill_quantity)
        if total_quantity == 0:
            return Decimal("0")
        weighted_notional = (abs(old_quantity) * old_entry_price) + (abs(fill_quantity) * fill_price)
        return (weighted_notional / total_quantity).quantize(DECIMAL_PLACES, rounding=ROUND_HALF_UP)
