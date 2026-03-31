import asyncio
from datetime import datetime, timezone

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.domain.enums import DecisionStatus, MarketRegime
from cats_py.domain.models import AccountState, BalanceState, TradeDecision
from cats_py.services.decision_runtime import DecisionRuntimeService


class DummyNofxWithGlobalData:
    def __init__(self) -> None:
        self.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    async def coin(self, symbol: str) -> dict[str, object]:
        return {
            "data": {
                "timestamp": self.timestamp_ms,
                "price": 50_000,
                "price_change": {"15m": 0.01, "1h": 0.02, "4h": 0.03},
                "netflow": {
                    "institution": {"future": {"15m": 1.0, "1h": 1.0, "4h": 1.0}},
                    "personal": {"future": {"1h": 0.0}},
                },
                "oi": {
                    "binance": {"delta": {"1h": {"oi_delta_percent": 5.0}}},
                    "bybit": {"delta": {"1h": {"oi_delta_percent": 2.0}}},
                },
                "ai500": {"score": 0.0},
            }
        }

    async def funding_rate(self, symbol: str) -> dict[str, object]:
        return {"data": {"funding_rate": 0.2, "timestamp": self.timestamp_ms}}

    async def heatmap_future(self, symbol: str) -> dict[str, object]:
        return {"data": {"heatmap": {"delta": 1000, "timestamp": self.timestamp_ms}}}

    async def query_rank(self, *, limit: int = 20) -> dict[str, object]:
        return {
            "data": {
                "rankings": [
                    {"symbol": "BTC", "rank": 1},
                    {"symbol": "ETH", "rank": 2},
                    {"symbol": "DOGE", "rank": 3},
                ]
            }
        }

    async def ai300_list(self, *, limit: int | None = None) -> dict[str, object]:
        return {
            "data": {
                "coins": [
                    {"symbol": "BTC", "level": "A"},
                    {"symbol": "ETH", "level": "B"},
                    {"symbol": "DOGE", "level": "C"},
                ]
            }
        }


class FeatureCapturingEngine:
    """Captures features passed to decide() for inspection."""
    def __init__(self) -> None:
        self.captured_features = {}

    def decide(self, feature, account_snapshot) -> TradeDecision:
        self.captured_features[feature.symbol] = feature
        return TradeDecision.no_trade(
            decision_id=f"d-{feature.symbol}",
            symbol=feature.symbol,
            regime=MarketRegime.UNKNOWN,
            rationale=["test"],
        )


class DummyReconciler:
    def __init__(self, account_state: AccountState) -> None:
        self.account_state = account_state

    async def reconcile(self):
        return self.account_state


class MemoryJournal:
    def __init__(self) -> None:
        self.entries: list[tuple[str, object]] = []

    def record(self, stream: str, payload) -> None:
        self.entries.append((stream, payload))


def make_mode_summary() -> RuntimeModeSummary:
    return RuntimeModeSummary(
        env="test",
        mode=RuntimeMode.SHADOW,
        decision_loop_enabled=True,
        live_order_submission=False,
        paper_execution=False,
        allowed_symbol_tiers=("core", "liquid_alt", "experimental"),
        configured_symbol_counts={"core": 1, "liquid_alt": 1},
        core_loop_interval_seconds=1,
    )


def test_features_receive_query_rank_from_global_data() -> None:
    engine = FeatureCapturingEngine()
    account = AccountState()
    account.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
    account.record_user_stream_event(datetime.now(timezone.utc))
    service = DecisionRuntimeService(
        nofx=DummyNofxWithGlobalData(),
        decision_engine=engine,  # type: ignore[arg-type]
        reconciler=DummyReconciler(account),  # type: ignore[arg-type]
        journal=MemoryJournal(),  # type: ignore[arg-type]
        app_config=AppConfig(mode=RuntimeMode.SHADOW, nofx_stale_kill_seconds=120),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=["DOGEUSDT"], experimental=[]),
        mode_summary=make_mode_summary(),
    )

    asyncio.run(service.run_cycle())

    btc_feature = engine.captured_features["BTCUSDT"]
    assert btc_feature.query_rank == 1

    doge_feature = engine.captured_features["DOGEUSDT"]
    assert doge_feature.query_rank == 3


def test_features_receive_ai300_level_score_from_global_data() -> None:
    engine = FeatureCapturingEngine()
    account = AccountState()
    account.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
    account.record_user_stream_event(datetime.now(timezone.utc))
    service = DecisionRuntimeService(
        nofx=DummyNofxWithGlobalData(),
        decision_engine=engine,  # type: ignore[arg-type]
        reconciler=DummyReconciler(account),  # type: ignore[arg-type]
        journal=MemoryJournal(),  # type: ignore[arg-type]
        app_config=AppConfig(mode=RuntimeMode.SHADOW, nofx_stale_kill_seconds=120),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=["DOGEUSDT"], experimental=[]),
        mode_summary=make_mode_summary(),
    )

    asyncio.run(service.run_cycle())

    btc_feature = engine.captured_features["BTCUSDT"]
    assert btc_feature.ai300_level_score == 1.0  # level A

    doge_feature = engine.captured_features["DOGEUSDT"]
    assert doge_feature.ai300_level_score == 0.5  # level C


def test_crowding_reversal_receives_non_none_query_rank() -> None:
    engine = FeatureCapturingEngine()
    account = AccountState()
    account.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
    account.record_user_stream_event(datetime.now(timezone.utc))
    service = DecisionRuntimeService(
        nofx=DummyNofxWithGlobalData(),
        decision_engine=engine,  # type: ignore[arg-type]
        reconciler=DummyReconciler(account),  # type: ignore[arg-type]
        journal=MemoryJournal(),  # type: ignore[arg-type]
        app_config=AppConfig(mode=RuntimeMode.SHADOW, nofx_stale_kill_seconds=120),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(),
    )

    asyncio.run(service.run_cycle())

    btc_feature = engine.captured_features["BTCUSDT"]
    assert btc_feature.query_rank is not None
    hot = (btc_feature.query_rank or 999) <= 5
    assert hot is True
