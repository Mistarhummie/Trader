"""Loads settings from config.yaml and API keys from .env."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent


@dataclass
class RiskSettings:
    risk_per_trade: float = 0.01
    max_daily_loss: float = 0.03
    max_open_positions: int = 3
    futures_enabled: bool = False
    max_leverage: float = 2.0
    min_order_usdt: float = 5.0


@dataclass
class BacktestSettings:
    start: str = "2024-01-01"
    end: str | None = None
    fee_rate: float = 0.001
    slippage: float = 0.0005


@dataclass
class Config:
    exchange: str = "binance"
    market: str = "spot"
    timeframe: str = "1h"
    symbols: list[str] = field(default_factory=lambda: ["ETH/USDT"])
    starting_kes: float = 5000.0
    kes_per_usdt: float = 129.0
    risk: RiskSettings = field(default_factory=RiskSettings)
    strategy: str = "auto"
    strategy_params: dict = field(default_factory=dict)
    backtest: BacktestSettings = field(default_factory=BacktestSettings)

    @property
    def starting_usdt(self) -> float:
        return self.starting_kes / self.kes_per_usdt

    def validate(self) -> None:
        if self.market not in ("spot", "future"):
            raise ValueError("market must be 'spot' or 'future'")
        if self.market == "future" and not self.risk.futures_enabled:
            raise ValueError(
                "market is 'future' but risk.futures_enabled is false. "
                "Switch futures on deliberately in config.yaml first."
            )
        if self.risk.max_leverage > 2:
            raise ValueError("max_leverage above 2 is outside the agreed risk limits")
        if not 0 < self.risk.risk_per_trade <= 0.02:
            raise ValueError("risk_per_trade must be between 0 and 0.02 (2%)")


def load_config(path: str | Path | None = None) -> Config:
    """Read config.yaml (or config.example.yaml if you haven't made one yet)."""
    if path is None:
        path = ROOT / "config.yaml"
        if not path.exists():
            path = ROOT / "config.example.yaml"
    raw = yaml.safe_load(Path(path).read_text()) or {}

    capital = raw.pop("capital", {}) or {}
    cfg = Config(
        exchange=raw.get("exchange", "binance"),
        market=raw.get("market", "spot"),
        timeframe=raw.get("timeframe", "1h"),
        symbols=raw.get("symbols", ["ETH/USDT"]),
        starting_kes=float(capital.get("starting_kes", 5000)),
        kes_per_usdt=float(capital.get("kes_per_usdt", 129)),
        risk=RiskSettings(**(raw.get("risk") or {})),
        strategy=raw.get("strategy", "auto"),
        strategy_params=raw.get("strategy_params") or {},
        backtest=BacktestSettings(**(raw.get("backtest") or {})),
    )
    cfg.validate()
    return cfg


def load_api_keys() -> tuple[str | None, str | None]:
    """Read API keys from the .env file. Returns (None, None) if not set."""
    load_dotenv(ROOT / ".env")
    key = os.getenv("BINANCE_API_KEY") or None
    secret = os.getenv("BINANCE_API_SECRET") or None
    return key, secret
