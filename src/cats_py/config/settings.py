from __future__ import annotations

from enum import Enum
from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RuntimeMode(str, Enum):
    SHADOW = "shadow"
    PAPER = "paper"
    LIVE_MICRO = "live_micro"
    LIVE = "live"


class RuntimeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = Field(default="dev", alias="CATS_ENV")
    mode: RuntimeMode = Field(
        default=RuntimeMode.SHADOW, alias="CATS_MODE"
    )
    log_level: str = Field(default="INFO", alias="CATS_LOG_LEVEL")

    nofx_api_key: str = Field(default="", alias="NOFX_API_KEY")
    nofx_auth_mode: str = Field(default="bearer", alias="NOFX_AUTH_MODE")
    nofx_base_url: str = Field(default="https://nofxos.ai", alias="NOFX_BASE_URL")

    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")
    binance_rest_base_url: str = Field(default="https://fapi.binance.com", alias="BINANCE_REST_BASE_URL")
    binance_ws_public_url: str = Field(default="wss://fstream.binance.com/public", alias="BINANCE_WS_PUBLIC_URL")
    binance_ws_market_url: str = Field(default="wss://fstream.binance.com/market", alias="BINANCE_WS_MARKET_URL")
    binance_ws_private_url: str = Field(default="wss://fstream.binance.com/private", alias="BINANCE_WS_PRIVATE_URL")

    postgres_dsn: str = Field(default="", alias="POSTGRES_DSN")
    redis_url: str = Field(default="", alias="REDIS_URL")
    clickhouse_dsn: str = Field(default="", alias="CLICKHOUSE_DSN")

    app_config_path: Path = Field(default=Path("configs/app.yaml"), alias="CATS_APP_CONFIG")
    risk_config_path: Path = Field(default=Path("configs/risk.yaml"), alias="CATS_RISK_CONFIG")
    symbols_config_path: Path = Field(default=Path("configs/symbols.yaml"), alias="CATS_SYMBOLS_CONFIG")


class AppConfig(BaseModel):
    mode: RuntimeMode = RuntimeMode.SHADOW
    core_loop_interval_seconds: int = 5
    user_stream_stale_kill_seconds: int = 90
    nofx_stale_kill_seconds: int = 45
    paper_starting_balance: float = 10_000.0
    paper_fill_slippage_bps: float = 1.0
    paper_taker_fee_bps: float = 4.0
    paper_funding_interval_hours: float = 8.0
    nofx: dict[str, object] = Field(default_factory=dict)
    binance: dict[str, object] = Field(default_factory=dict)


class RiskConfig(BaseModel):
    risk: dict[str, object] = Field(default_factory=dict)
    tiers: dict[str, object] = Field(default_factory=dict)


class SymbolConfig(BaseModel):
    core: list[str] = Field(default_factory=list)
    liquid_alt: list[str] = Field(default_factory=list)
    experimental: list[str] = Field(default_factory=list)


def _load_yaml(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"missing config file: {path}")
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        raise TypeError(f"config must be a dict: {path}")
    return data


def load_all_settings() -> tuple[RuntimeSettings, AppConfig, RiskConfig, SymbolConfig]:
    runtime = RuntimeSettings()
    app = AppConfig.model_validate(_load_yaml(runtime.app_config_path))
    risk = RiskConfig.model_validate(_load_yaml(runtime.risk_config_path))
    symbols = SymbolConfig.model_validate(_load_yaml(runtime.symbols_config_path))
    return runtime, app, risk, symbols
