"""Breakout: buy when the price closes above the highest high of the last
N candles. Exit when it closes below the lowest low of a shorter window."""

import pandas as pd

from .. import indicators as ind


def donchian_breakout(df: pd.DataFrame, entry_period=20, exit_period=10,
                      atr_stop=2.0, tag="donchian") -> pd.DataFrame:
    entry_low, entry_high = ind.donchian(df, entry_period)
    exit_low, exit_high = ind.donchian(df, exit_period)
    close = df["close"]

    out = pd.DataFrame(index=df.index)
    out["entry"] = 0
    out.loc[close > entry_high, "entry"] = 1
    out.loc[close < entry_low, "entry"] = -1
    out["tag"] = tag
    out["stop_dist"] = ind.atr(df) * atr_stop
    out[f"exit_long_{tag}"] = close < exit_low
    out[f"exit_short_{tag}"] = close > exit_high
    return out
