"""Mean reversion for sideways markets: buy when the price dips below the
lower Bollinger Band and RSI says it's oversold; sell when it returns to the
middle band. The mirror image is used for shorts on futures."""

import pandas as pd

from .. import indicators as ind


def bb_rsi(df: pd.DataFrame, bb_period=20, bb_std=2.0, rsi_period=14,
           rsi_low=30, rsi_high=70, atr_stop=1.5, tag="bb_rsi") -> pd.DataFrame:
    lower, mid, upper = ind.bollinger(df["close"], bb_period, bb_std)
    strength = ind.rsi(df["close"], rsi_period)
    close = df["close"]

    out = pd.DataFrame(index=df.index)
    out["entry"] = 0
    out.loc[(close < lower) & (strength < rsi_low), "entry"] = 1
    out.loc[(close > upper) & (strength > rsi_high), "entry"] = -1
    out["tag"] = tag
    out["stop_dist"] = ind.atr(df) * atr_stop
    out[f"exit_long_{tag}"] = close >= mid
    out[f"exit_short_{tag}"] = close <= mid
    return out
