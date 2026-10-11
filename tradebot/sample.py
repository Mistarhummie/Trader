"""Made-up price data for testing the bot without internet access.
It is NOT real market data, so results on it say nothing about profit."""

from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic_candles(n: int = 4000, start_price: float = 100.0, seed: int = 0,
                      freq: str = "1h") -> pd.DataFrame:
    """A random walk that alternates between trending and sideways stretches."""
    rng = np.random.default_rng(seed)
    drift = np.zeros(n)
    i = 0
    while i < n:
        length = int(rng.integers(150, 500))
        drift[i:i + length] = rng.choice([0.0015, -0.0015, 0.0, 0.0])
        i += length
    returns = drift + rng.normal(0, 0.008, n)
    close = start_price * np.exp(np.cumsum(returns))
    open_ = np.concatenate([[start_price], close[:-1]])
    spread = np.abs(rng.normal(0, 0.004, n)) * close
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    index = pd.date_range("2024-01-01", periods=n, freq=freq.replace("m", "min"), tz="UTC")
    return pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                         "volume": rng.uniform(100, 1000, n)}, index=index)
