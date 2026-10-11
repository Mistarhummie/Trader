"""Downloads price candles and saves them to the data/ folder, so backtests
can be re-run without downloading again."""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from .config import ROOT

DATA_DIR = ROOT / "data"
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def candle_file(exchange: str, market: str, symbol: str, timeframe: str) -> Path:
    name = f"{exchange}_{market}_{symbol.replace('/', '-').replace(':', '-')}_{timeframe}.csv"
    return DATA_DIR / name


def download(exchange, symbol: str, timeframe: str, start: str, end: str | None = None,
             batch: int = 1000) -> pd.DataFrame:
    """Fetch all candles from start to end, page by page."""
    since = exchange.parse8601(f"{start}T00:00:00Z")
    until = exchange.parse8601(f"{end}T00:00:00Z") if end else exchange.milliseconds()
    rows: list[list] = []
    while since < until:
        page = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=batch)
        if not page:
            break
        rows.extend(page)
        next_since = page[-1][0] + 1
        if next_since <= since:
            break
        since = next_since
        time.sleep(exchange.rateLimit / 1000)
    df = pd.DataFrame(rows, columns=COLUMNS).drop_duplicates("timestamp")
    df = df[df["timestamp"] < until]
    return to_frame(df)


def to_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["time"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    return df.set_index("time")[["open", "high", "low", "close", "volume"]].astype(float)


def save(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    out.insert(0, "timestamp", (out.index.astype("int64") // 10**6))
    out.to_csv(path, index=False)


def load(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"No price data at {path}. Run: python -m tradebot download"
        )
    return to_frame(pd.read_csv(path))
