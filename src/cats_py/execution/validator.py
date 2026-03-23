from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, ROUND_DOWN
from typing import Any

from cats_py.domain.enums import OrderType
from cats_py.domain.models import OrderRequest


@dataclass(slots=True)
class SymbolRule:
    symbol: str
    tick_size: Decimal
    step_size: Decimal
    min_qty: Decimal
    min_notional: Decimal
    market_step_size: Decimal | None = None
    market_min_qty: Decimal | None = None
    market_max_qty: Decimal | None = None
    min_price: Decimal | None = None
    max_price: Decimal | None = None
    percent_price_up: Decimal | None = None
    percent_price_down: Decimal | None = None
    market_take_bound: Decimal | None = None
    trigger_protect: Decimal | None = None
    max_initial_leverage: float | None = None
    max_notional_cap: Decimal | None = None
    status: str = "TRADING"


ALGO_ORDER_TYPES = {
    OrderType.STOP,
    OrderType.STOP_MARKET,
    OrderType.TAKE_PROFIT,
    OrderType.TAKE_PROFIT_MARKET,
    OrderType.TRAILING_STOP_MARKET,
}


def decimal_or_default(value: Any, default: str) -> Decimal:
    if value is None or value == "":
        return Decimal(default)
    return Decimal(str(value))


def optional_decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    return Decimal(str(value))


def floor_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        raise ValueError("step must be > 0")
    return (value / step).quantize(Decimal("1"), rounding=ROUND_DOWN) * step


class PreTradeValidator:
    def __init__(self, symbol_rules: dict[str, SymbolRule]) -> None:
        self.symbol_rules = symbol_rules

    def validate(
        self,
        request: OrderRequest,
        mark_price: Decimal | None = None,
    ) -> OrderRequest:
        if request.symbol not in self.symbol_rules:
            raise KeyError(f"missing rules for symbol={request.symbol}")

        rules = self.symbol_rules[request.symbol]
        if rules.status != "TRADING":
            raise ValueError(f"symbol not tradable: {request.symbol}")

        normalized = replace(request)

        if normalized.order_type in ALGO_ORDER_TYPES and normalized.close_position:
            if normalized.quantity is not None:
                raise ValueError("closePosition=true cannot be sent with quantity for algo orders")
            if normalized.reduce_only:
                raise ValueError("closePosition=true cannot be sent with reduceOnly for algo orders")

        if normalized.reduce_only and normalized.position_side != "BOTH":
            raise ValueError("reduceOnly cannot be sent in hedge mode")

        qty_step = rules.market_step_size if normalized.order_type == OrderType.MARKET and rules.market_step_size else rules.step_size
        qty_min = rules.market_min_qty if normalized.order_type == OrderType.MARKET and rules.market_min_qty else rules.min_qty
        qty_max = rules.market_max_qty if normalized.order_type == OrderType.MARKET and rules.market_max_qty else None

        if normalized.quantity is not None:
            normalized_qty = floor_to_step(normalized.quantity, qty_step)
            if normalized_qty < qty_min:
                raise ValueError("quantity below minQty")
            if qty_max is not None and normalized_qty > qty_max:
                raise ValueError("quantity above maxQty")
            normalized.quantity = normalized_qty

        if normalized.price is not None:
            normalized.price = floor_to_step(normalized.price, rules.tick_size)
            if rules.min_price is not None and normalized.price < rules.min_price:
                raise ValueError("price below minPrice")
            if rules.max_price is not None and normalized.price > rules.max_price:
                raise ValueError("price above maxPrice")

        if normalized.trigger_price is not None:
            normalized.trigger_price = floor_to_step(normalized.trigger_price, rules.tick_size)

        if normalized.activate_price is not None:
            normalized.activate_price = floor_to_step(normalized.activate_price, rules.tick_size)

        if normalized.price is not None and normalized.quantity is not None:
            if normalized.price * normalized.quantity < rules.min_notional:
                raise ValueError("notional below minimum")

        reference_price = mark_price or normalized.price
        if normalized.quantity is not None and reference_price is not None and reference_price * normalized.quantity < rules.min_notional:
            raise ValueError("notional below minimum")

        if normalized.order_type == OrderType.MARKET and normalized.quantity is not None and mark_price is not None:
            if rules.market_take_bound is not None and normalized.price is not None:
                upper = mark_price * (Decimal("1") + rules.market_take_bound)
                lower = mark_price * (Decimal("1") - rules.market_take_bound)
                if normalized.price > upper or normalized.price < lower:
                    raise ValueError("market execution price outside marketTakeBound")

        if normalized.price is not None and mark_price is not None:
            if rules.percent_price_up is not None and normalized.price > mark_price * rules.percent_price_up:
                raise ValueError("price above PERCENT_PRICE upper bound")
            if rules.percent_price_down is not None and normalized.price < mark_price * rules.percent_price_down:
                raise ValueError("price below PERCENT_PRICE lower bound")

        return normalized

    @staticmethod
    def build_symbol_rules(exchange_info: dict[str, Any], leverage_brackets: dict[str, Any]) -> dict[str, SymbolRule]:
        bracket_map: dict[str, dict[str, Any]] = {}
        raw_brackets = leverage_brackets.get("data", leverage_brackets)
        if isinstance(raw_brackets, list):
            for item in raw_brackets:
                if isinstance(item, dict):
                    symbol = item.get("symbol")
                    if isinstance(symbol, str):
                        bracket_map[symbol] = item

        rules: dict[str, SymbolRule] = {}
        symbols = exchange_info.get("data", exchange_info).get("symbols", [])
        for item in symbols:
            if not isinstance(item, dict):
                continue
            symbol = item.get("symbol")
            if not isinstance(symbol, str):
                continue
            filters = {f["filterType"]: f for f in item.get("filters", []) if isinstance(f, dict)}
            bracket = bracket_map.get(symbol, {})
            bracket_list = bracket.get("brackets", [])
            first_bracket = bracket_list[0] if bracket_list and isinstance(bracket_list[0], dict) else {}

            min_notional_raw = filters.get("MIN_NOTIONAL", {}).get("notional", "0")
            lot_size = filters.get("LOT_SIZE", {})
            market_lot_size = filters.get("MARKET_LOT_SIZE", {})
            price_filter = filters.get("PRICE_FILTER", {})
            percent_price = filters.get("PERCENT_PRICE", {})

            rules[symbol] = SymbolRule(
                symbol=symbol,
                tick_size=decimal_or_default(price_filter.get("tickSize"), "0.0001"),
                step_size=decimal_or_default(lot_size.get("stepSize"), "0.001"),
                min_qty=decimal_or_default(lot_size.get("minQty"), "0"),
                min_notional=decimal_or_default(min_notional_raw, "0"),
                market_step_size=decimal_or_default(market_lot_size.get("stepSize", lot_size.get("stepSize")), "0.001"),
                market_min_qty=decimal_or_default(market_lot_size.get("minQty", lot_size.get("minQty")), "0"),
                market_max_qty=optional_decimal(market_lot_size.get("maxQty")) if market_lot_size else None,
                min_price=decimal_or_default(price_filter.get("minPrice"), "0"),
                max_price=optional_decimal(price_filter.get("maxPrice")),
                percent_price_up=optional_decimal(percent_price.get("multiplierUp")) if percent_price else None,
                percent_price_down=optional_decimal(percent_price.get("multiplierDown")) if percent_price else None,
                market_take_bound=optional_decimal(item.get("marketTakeBound")),
                trigger_protect=optional_decimal(item.get("triggerProtect")),
                max_initial_leverage=float(first_bracket.get("initialLeverage", 1.0)),
                max_notional_cap=optional_decimal(first_bracket.get("notionalCap")) if first_bracket else None,
                status=str(item.get("status", "TRADING")),
            )
        return rules
