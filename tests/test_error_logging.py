import asyncio
from datetime import datetime, timezone

from cats_py.app.bootstrap import RuntimeModeSummary
from cats_py.config.settings import AppConfig, RuntimeMode, SymbolConfig
from cats_py.domain.enums import MarketRegime
from cats_py.domain.models import AccountState, BalanceState, TradeDecision
from cats_py.services.decision_runtime import DecisionRuntimeService


class EmptyMessageError(Exception):
    """An exception whose str() returns empty string."""
    def __str__(self) -> str:
        return ""


class FailingNofx:
    """Fails on coin() for specific symbols, succeeds for others."""
    def __init__(self, *, fail_symbol: str) -> None:
        self.fail_symbol = fail_symbol
        self.timestamp_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    async def coin(self, symbol: str) -> dict[str, object]:
        if symbol == self.fail_symbol:
            raise EmptyMessageError()
        return {
            "data": {
                "timestamp": self.timestamp_ms,
                "price": 100,
                "price_change": {"15m": 0.01, "1h": 0.02, "4h": 0.03},
                "netflow": {
                    "institution": {"future": {"15m": 1.0, "1h": 1.0, "4h": 1.0}},
                    "personal": {"future": {"1h": 0.0}},
                },
                "oi": {
                    "binance": {"delta": {"1h": {"oi_delta_percent": 5.0}}},
                    "bybit": {"delta": {"1h": {"oi_delta_percent": 2.0}}},
                },
                "ai500": {"score": 75.0},
            }
        }

    async def funding_rate(self, symbol: str) -> dict[str, object]:
        return {"data": {"funding_rate": 0.1, "timestamp": self.timestamp_ms}}

    async def heatmap_future(self, symbol: str) -> dict[str, object]:
        return {"data": {"heatmap": {"delta": 100, "timestamp": self.timestamp_ms}}}

    async def query_rank(self, *, limit: int = 20) -> dict[str, object]:
        return {"data": {"rankings": []}}

    async def ai300_list(self, *, limit: int | None = None) -> dict[str, object]:
        return {"data": {"coins": []}}


class DummyDecisionEngine:
    def decide(self, feature, account_snapshot) -> TradeDecision:
        return TradeDecision.no_trade(
            decision_id=f"d-{feature.symbol}",
            symbol=feature.symbol,
            regime=MarketRegime.UNKNOWN,
            rationale=["test"],
        )


class DummyReconciler:
    async def reconcile(self):
        state = AccountState()
        state.upsert_balance(BalanceState(asset="USDT", wallet_balance=1000))  # type: ignore[arg-type]
        state.record_user_stream_event(datetime.now(timezone.utc))
        return state


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
        allowed_symbol_tiers=("core", "liquid_alt"),
        configured_symbol_counts={"core": 2},
        core_loop_interval_seconds=1,
    )


def test_error_log_includes_type_and_traceback_for_empty_message_exception() -> None:
    journal = MemoryJournal()
    service = DecisionRuntimeService(
        nofx=FailingNofx(fail_symbol="BTCUSDT"),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(mode=RuntimeMode.SHADOW, nofx_stale_kill_seconds=120),
        symbol_config=SymbolConfig(core=["BTCUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(),
    )

    asyncio.run(service.run_cycle())

    error_entries = [(s, p) for s, p in journal.entries if s == "decision_cycle_error"]
    assert len(error_entries) == 1
    payload = error_entries[0][1]
    assert payload["error_type"] == "EmptyMessageError"
    assert payload["error"] != ""  # repr fallback works
    assert "traceback" in payload
    assert payload["traceback"] != ""


def test_error_on_one_symbol_does_not_block_others() -> None:
    journal = MemoryJournal()
    service = DecisionRuntimeService(
        nofx=FailingNofx(fail_symbol="BTCUSDT"),
        decision_engine=DummyDecisionEngine(),
        reconciler=DummyReconciler(),  # type: ignore[arg-type]
        journal=journal,  # type: ignore[arg-type]
        app_config=AppConfig(mode=RuntimeMode.SHADOW, nofx_stale_kill_seconds=120),
        symbol_config=SymbolConfig(core=["BTCUSDT", "ETHUSDT"], liquid_alt=[], experimental=[]),
        mode_summary=make_mode_summary(),
    )

    result = asyncio.run(service.run_cycle())

    assert len(result.decisions) == 1
    assert result.decisions[0].symbol == "ETHUSDT"

    error_entries = [p for s, p in journal.entries if s == "decision_cycle_error"]
    assert len(error_entries) == 1
    assert error_entries[0]["symbol"] == "BTCUSDT"
