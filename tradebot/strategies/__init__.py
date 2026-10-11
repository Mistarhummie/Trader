"""Trading strategies. Each one reads candles and returns signals.

Every strategy returns a DataFrame with the same index as the candles and:
  entry        1 = open a long, -1 = open a short, 0 = do nothing
  tag          which strategy produced the entry (used to pick its exit rule)
  stop_dist    how far below/above the entry price the stop-loss goes
  exit_long_<tag>, exit_short_<tag>   True when that strategy wants out

Signals are decided on a candle's close; the backtester and the live bot
act on the NEXT candle, so a strategy can never peek at the future.
"""

from .bb_rsi import bb_rsi
from .donchian import donchian_breakout
from .ema_adx import ema_adx
from .auto import auto

STRATEGIES = {
    "ema_adx": ema_adx,
    "donchian": donchian_breakout,
    "bb_rsi": bb_rsi,
    "auto": auto,
}


def get_strategy(name: str):
    try:
        return STRATEGIES[name]
    except KeyError:
        raise ValueError(f"Unknown strategy '{name}'. Choose from: {', '.join(STRATEGIES)}")
