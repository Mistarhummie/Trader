"""Replays past candles through the strategies and the risk manager to see
how the bot would have done, including fees, slippage and stop-losses.

Rules that keep the results honest:
  * Signals come from a candle's close; orders fill at the NEXT candle's open.
  * Stop-losses are checked against each candle's high/low and fill at the
    stop price (or the open, if the price gapped past it).
  * Every fill pays the fee and slippage from config.yaml.
  * Futures funding fees are not included yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import Config
from .risk import RiskManager
from .strategies import get_strategy


@dataclass
class Position:
    symbol: str
    side: int            # 1 long, -1 short
    tag: str
    qty: float
    entry_price: float
    stop: float
    entry_time: pd.Timestamp
    fees: float = 0.0


@dataclass
class Result:
    equity: pd.Series
    trades: pd.DataFrame
    start_balance: float
    buy_hold: dict = field(default_factory=dict)

    def summary(self) -> dict:
        eq = self.equity
        t = self.trades
        wins = t[t["pnl"] > 0] if len(t) else t
        losses = t[t["pnl"] <= 0] if len(t) else t
        gross_win = wins["pnl"].sum() if len(t) else 0.0
        gross_loss = -losses["pnl"].sum() if len(t) else 0.0
        drawdown = (eq / eq.cummax() - 1).min() if len(eq) else 0.0
        return {
            "start_balance": self.start_balance,
            "end_balance": float(eq.iloc[-1]) if len(eq) else self.start_balance,
            "return_pct": (float(eq.iloc[-1]) / self.start_balance - 1) * 100 if len(eq) else 0.0,
            "max_drawdown_pct": float(drawdown) * 100,
            "trades": int(len(t)),
            "win_rate_pct": (len(wins) / len(t) * 100) if len(t) else 0.0,
            "profit_factor": (gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win > 0 else 0.0,
            "fees_paid": float(t["fees"].sum()) if len(t) else 0.0,
            "buy_hold_return_pct": float(np.mean(list(self.buy_hold.values()))) if self.buy_hold else 0.0,
        }


def make_signals(cfg: Config, df: pd.DataFrame) -> pd.DataFrame:
    params = dict(cfg.strategy_params.get(cfg.strategy, {}))
    if cfg.strategy == "auto":
        params["donchian"] = cfg.strategy_params.get("donchian")
        params["bb_rsi_params"] = cfg.strategy_params.get("bb_rsi")
    return get_strategy(cfg.strategy)(df, **params)


def run(cfg: Config, candles: dict[str, pd.DataFrame], start_balance: float | None = None) -> Result:
    """Backtest every symbol together, sharing one balance, so the limits on
    open positions and daily loss work exactly as they will live."""
    balance = start_balance if start_balance is not None else cfg.starting_usdt
    fee, slip = cfg.backtest.fee_rate, cfg.backtest.slippage
    risk = RiskManager(cfg.risk, cfg.market)

    signals = {s: make_signals(cfg, df) for s, df in candles.items()}
    timeline = sorted(set().union(*[df.index for df in candles.values()]))

    cash = balance                       # realised balance (profit/loss accounting)
    positions: dict[str, Position] = {}
    pending: dict[str, tuple] = {}       # orders decided at a close, filled next open
    last_close: dict[str, float] = {}
    trades: list[dict] = []
    equity_curve = []

    def close_position(pos: Position, price: float, when, reason: str):
        nonlocal cash
        exit_fee = pos.qty * price * fee
        pnl = (price - pos.entry_price) * pos.qty * pos.side - pos.fees - exit_fee
        cash += (price - pos.entry_price) * pos.qty * pos.side - exit_fee
        trades.append({
            "symbol": pos.symbol, "side": "long" if pos.side > 0 else "short", "strategy": pos.tag,
            "entry_time": pos.entry_time, "entry_price": pos.entry_price,
            "exit_time": when, "exit_price": price, "qty": pos.qty,
            "pnl": pnl, "fees": pos.fees + exit_fee, "exit_reason": reason,
        })
        del positions[pos.symbol]

    def equity_now() -> float:
        unrealised = sum((last_close[p.symbol] - p.entry_price) * p.qty * p.side for p in positions.values())
        return cash + unrealised

    for t in timeline:
        risk.start_of_candle(t.date(), equity_now() if last_close else cash)
        for sym, df in candles.items():
            if t not in df.index:
                continue
            bar = df.loc[t]
            o, h, l, c = bar["open"], bar["high"], bar["low"], bar["close"]

            # 1. Fill orders decided at the previous close, at this candle's open.
            order = pending.pop(sym, None)
            if order and order[0] == "exit" and sym in positions:
                pos = positions[sym]
                close_position(pos, o * (1 - slip * pos.side), t, "signal")
            elif order and order[0] == "entry" and sym not in positions:
                _, side, tag, stop_dist = order
                ok, _ = risk.can_open(side, len(positions))
                if ok:
                    price = o * (1 + slip * side)
                    size = risk.size(equity_now() if last_close else cash, price, stop_dist)
                    if size.qty > 0:
                        entry_fee = size.qty * price * fee
                        cash -= entry_fee
                        positions[sym] = Position(sym, side, tag, size.qty, price,
                                                  price - side * stop_dist, t, entry_fee)

            # 2. Stop-loss: did this candle's range touch the stop?
            if sym in positions:
                pos = positions[sym]
                if pos.side > 0 and l <= pos.stop:
                    close_position(pos, min(o, pos.stop) * (1 - slip), t, "stop-loss")
                elif pos.side < 0 and h >= pos.stop:
                    close_position(pos, max(o, pos.stop) * (1 + slip), t, "stop-loss")

            last_close[sym] = c

            # 3. Read this candle's signal; act on it at the next open.
            sig = signals[sym].loc[t]
            if sym in positions:
                pos = positions[sym]
                col = f"exit_{'long' if pos.side > 0 else 'short'}_{pos.tag}"
                if bool(sig.get(col, False)):
                    pending[sym] = ("exit",)
            elif sig["entry"] != 0 and sig["stop_dist"] > 0:
                pending[sym] = ("entry", int(sig["entry"]), sig["tag"], float(sig["stop_dist"]))

        eq = equity_now()
        risk.check_daily_loss(eq)
        equity_curve.append((t, eq))

    for pos in list(positions.values()):
        close_position(pos, last_close[pos.symbol], timeline[-1], "end of test")

    equity = pd.Series(dict(equity_curve), name="equity")
    if len(equity):
        equity.iloc[-1] = cash
    buy_hold = {s: (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100 for s, df in candles.items()}
    return Result(equity, pd.DataFrame(trades), balance, buy_hold)
