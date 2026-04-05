from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from cats_py.domain.enums import (
    DecisionStatus,
    MarketRegime,
    PositionDirection,
    RiskDecisionStatus,
    Side,
    SymbolTier,
)
from cats_py.domain.models import (
    AccountState,
    FeatureVector,
    PositionState,
    RiskDecision,
    TradeDecision,
)


@dataclass(slots=True)
class PositionEntryMeta:
    entry_time: datetime
    peak_price: float
    strategy_name: str


@dataclass(slots=True)
class ExitConfig:
    stop_loss_pct: float = 0.015
    take_profit_pct: float = 0.02
    max_hold_hours: float = 12.0
    trailing_stop_pct: float = 0.025


class PositionExitEvaluator:
    def __init__(self, config: ExitConfig | None = None) -> None:
        self.config = config or ExitConfig()
        self.last_errors: list[str] = []

    def evaluate(
        self,
        account_state: AccountState,
        features: dict[str, FeatureVector],
        metadata: dict[str, PositionEntryMeta],
        now: datetime,
    ) -> list[TradeDecision]:
        exits: list[TradeDecision] = []
        self.last_errors = []
        for position in list(account_state.positions.values()):
            if not position.is_open:
                continue
            feature = features.get(position.symbol)
            if feature is None:
                continue
            try:
                meta = metadata.get(position.symbol)
                reason = self._check_exit(position, feature, meta, now)
                if reason is not None:
                    exits.append(self._build_exit_decision(position, feature, reason))
            except Exception as exc:  # noqa: BLE001
                self.last_errors.append(f"{position.symbol}: {exc!r}")
        return exits

    def _check_exit(
        self,
        position: PositionState,
        feature: FeatureVector,
        meta: PositionEntryMeta | None,
        now: datetime,
    ) -> str | None:
        entry_notional = abs(float(position.entry_price) * float(position.quantity))
        if entry_notional < 1.0:
            return None
        unrealized = float(position.unrealized_pnl)
        pnl_ratio = unrealized / entry_notional

        if pnl_ratio <= -self.config.stop_loss_pct:
            return "exit_stop_loss"

        if pnl_ratio >= self.config.take_profit_pct:
            return "exit_take_profit"

        if meta is not None:
            elapsed_hours = (now - meta.entry_time).total_seconds() / 3600.0
            if elapsed_hours >= self.config.max_hold_hours:
                return "exit_max_hold_time"

            if meta.peak_price > 0:
                mark = float(position.mark_price)
                if position.direction == PositionDirection.LONG:
                    retrace = (meta.peak_price - mark) / meta.peak_price
                else:
                    retrace = (mark - meta.peak_price) / meta.peak_price
                if retrace >= self.config.trailing_stop_pct:
                    return "exit_trailing_stop"

        if self._signal_reversal(position, feature):
            return "exit_signal_reversal"

        return None

    def _signal_reversal(self, position: PositionState, feature: FeatureVector) -> bool:
        if position.direction == PositionDirection.LONG:
            return feature.trend_score < -0.03 and feature.flow_score < 0
        if position.direction == PositionDirection.SHORT:
            return feature.trend_score > 0.03 and feature.flow_score > 0
        return False

    def _build_exit_decision(
        self,
        position: PositionState,
        feature: FeatureVector,
        exit_reason: str,
    ) -> TradeDecision:
        close_side = Side.SELL if position.direction == PositionDirection.LONG else Side.BUY
        notional = abs(float(position.mark_price) * float(position.quantity))
        return TradeDecision.execute(
            decision_id=f"{exit_reason}-{position.symbol.lower()}",
            symbol=position.symbol,
            regime=MarketRegime.UNKNOWN,
            side=close_side,
            rationale=[exit_reason, f"closing {position.direction.value} position"],
            risk=RiskDecision(
                status=RiskDecisionStatus.APPROVED,
                reason="exit approved (no risk gate for exits)",
                symbol_tier=SymbolTier.CORE,
                approved_notional=notional,
                approved_leverage=float(position.leverage),
                risk_budget_bps=0.0,
            ),
            action_score=0.0,
            selected_strategy=exit_reason,
        )
