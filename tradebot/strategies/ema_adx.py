"""Trend following: buy when the fast moving average crosses above the slow
one, but only if ADX says the trend is strong. Sell when it crosses back."""

import pandas as pd

from .. import indicators as ind


def ema_adx(df: pd.DataFrame, fast=20, slow=50, adx_period=14, adx_min=25,
            atr_stop=2.0, tag="ema_adx") -> pd.DataFrame:
    fast_ma = ind.ema(df["close"], fast)
    slow_ma = ind.ema(df["close"], slow)
    strength = ind.adx(df, adx_period)
    above = fast_ma > slow_ma
    crossed_up = above & ~above.shift(fill_value=False)
    crossed_down = ~above & above.shift(fill_value=False)
    strong = strength >= adx_min

    out = pd.DataFrame(index=df.index)
    out["entry"] = 0
    out.loc[crossed_up & strong, "entry"] = 1
    out.loc[crossed_down & strong, "entry"] = -1
    out["tag"] = tag
    out["stop_dist"] = ind.atr(df) * atr_stop
    out[f"exit_long_{tag}"] = ~above
    out[f"exit_short_{tag}"] = above
    out.iloc[:slow, out.columns.get_loc("entry")] = 0  # indicators still warming up
    return out
