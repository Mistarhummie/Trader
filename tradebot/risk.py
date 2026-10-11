"""The risk manager sits between the strategies and the exchange. It decides
how big each trade is and can block any trade that breaks your limits.
The backtester and the live bot both use this same code."""

from __future__ import annotations

from dataclasses import dataclass

from .config import RiskSettings


@dataclass
class SizeDecision:
    qty: float
    reason: str = ""


class RiskManager:
    def __init__(self, settings: RiskSettings, market: str = "spot"):
        self.s = settings
        self.market = market
        self.day = None
        self.day_start_equity = None
        self.halted_for_day = False

    @property
    def shorts_allowed(self) -> bool:
        return self.market == "future" and self.s.futures_enabled

    @property
    def leverage(self) -> float:
        return min(self.s.max_leverage, 2.0) if self.market == "future" else 1.0

    def start_of_candle(self, day, equity: float) -> None:
        """Reset the daily loss counter when a new (UTC) day begins."""
        if day != self.day:
            self.day = day
            self.day_start_equity = equity
            self.halted_for_day = False

    def check_daily_loss(self, equity: float) -> None:
        if self.day_start_equity and equity <= self.day_start_equity * (1 - self.s.max_daily_loss):
            self.halted_for_day = True

    def can_open(self, side: int, open_positions: int) -> tuple[bool, str]:
        if self.halted_for_day:
            return False, "daily loss limit reached"
        if open_positions >= self.s.max_open_positions:
            return False, "max open positions"
        if side < 0 and not self.shorts_allowed:
            return False, "shorts need futures enabled"
        return True, ""

    def size(self, equity: float, price: float, stop_dist: float) -> SizeDecision:
        """Size the trade so hitting the stop-loss loses ~risk_per_trade of the
        balance, capped at one slot of the balance (times leverage on futures)."""
        if stop_dist <= 0 or price <= 0:
            return SizeDecision(0, "invalid stop")
        qty = equity * self.s.risk_per_trade / stop_dist
        max_notional = equity / self.s.max_open_positions * self.leverage
        notional = min(qty * price, max_notional)
        if notional < self.s.min_order_usdt:
            return SizeDecision(0, f"order {notional:.2f} USDT below exchange minimum")
        return SizeDecision(notional / price)
