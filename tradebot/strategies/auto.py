"""Auto-switch: measure each coin's trend strength (ADX) and use a trend
strategy when it's trending, a range strategy when it's going sideways, and
nothing in between (when the market is undecided)."""

import pandas as pd

from .. import indicators as ind
from .bb_rsi import bb_rsi
from .donchian import donchian_breakout


def auto(df: pd.DataFrame, adx_period=14, trend_above=25, range_below=20,
         donchian=None, bb_rsi_params=None, **_) -> pd.DataFrame:
    strength = ind.adx(df, adx_period)
    trending = strength >= trend_above
    ranging = strength < range_below

    trend = donchian_breakout(df, **(donchian or {}))
    rng = bb_rsi(df, **(bb_rsi_params or {}))

    out = pd.DataFrame(index=df.index)
    out["entry"] = 0
    out["tag"] = ""
    out["stop_dist"] = 0.0
    use_trend = trending & (trend["entry"] != 0)
    use_range = ranging & (rng["entry"] != 0)
    out.loc[use_trend, ["entry", "tag", "stop_dist"]] = trend.loc[use_trend, ["entry", "tag", "stop_dist"]]
    out.loc[use_range, ["entry", "tag", "stop_dist"]] = rng.loc[use_range, ["entry", "tag", "stop_dist"]]
    # Each open trade keeps using the exit rule of the strategy that opened it.
    for col in trend.columns:
        if col.startswith("exit_"):
            out[col] = trend[col]
    for col in rng.columns:
        if col.startswith("exit_"):
            out[col] = rng[col]
    out["regime"] = "undecided"
    out.loc[trending, "regime"] = "trend"
    out.loc[ranging, "regime"] = "range"
    return out
