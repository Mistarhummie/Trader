"""Connects to an exchange through ccxt, so the same code works on Binance,
Bybit, OKX and the 100+ other exchanges ccxt supports."""

from __future__ import annotations

import ccxt

from .config import Config, load_api_keys


def connect(cfg: Config, with_keys: bool = False) -> ccxt.Exchange:
    """Create an exchange client. Public price data needs no keys."""
    exchange_class = getattr(ccxt, cfg.exchange)
    options = {"defaultType": "future" if cfg.market == "future" else "spot"}
    params = {"enableRateLimit": True, "options": options}
    if with_keys:
        key, secret = load_api_keys()
        if not key or not secret:
            raise RuntimeError("No API keys found. Copy .env.example to .env and fill it in.")
        params.update(apiKey=key, secret=secret)
    return exchange_class(params)


def min_order_usdt(exchange: ccxt.Exchange, symbol: str, fallback: float = 5.0) -> float:
    """The smallest order value (in USDT) the exchange accepts for a coin."""
    exchange.load_markets()
    market = exchange.market(symbol)
    cost_min = (market.get("limits", {}).get("cost") or {}).get("min")
    return float(cost_min) if cost_min else fallback
