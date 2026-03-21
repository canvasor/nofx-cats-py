from __future__ import annotations

from enum import Enum


class Side(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"
    STOP = "STOP"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT = "TAKE_PROFIT"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"
    TRAILING_STOP_MARKET = "TRAILING_STOP_MARKET"


class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"
    GTX = "GTX"


class MarketRegime(str, Enum):
    TREND = "TREND"
    RANGE = "RANGE"
    CROWDING = "CROWDING"
    DEFENSE = "DEFENSE"
    UNKNOWN = "UNKNOWN"


class SymbolTier(str, Enum):
    CORE = "core"
    LIQUID_ALT = "liquid_alt"
    EXPERIMENTAL = "experimental"


class RiskDecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    HALTED = "HALTED"


class DecisionStatus(str, Enum):
    EXECUTE = "EXECUTE"
    NO_TRADE = "NO_TRADE"


class OrderLifecycleStatus(str, Enum):
    NEW = "NEW"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELED = "CANCELED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"
    TRIGGERED = "TRIGGERED"
    UNKNOWN = "UNKNOWN"


class PositionDirection(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    FLAT = "FLAT"
