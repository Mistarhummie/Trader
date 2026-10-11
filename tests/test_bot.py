import pandas as pd
import pytest

from tradebot import backtest
from tradebot.config import Config, RiskSettings, load_config
from tradebot.risk import RiskManager
from tradebot.sample import synthetic_candles
from tradebot.strategies import STRATEGIES


def candles(prices, opens=None, lows=None, highs=None):
    idx = pd.date_range("2024-01-01", periods=len(prices), freq="1h", tz="UTC")
    opens = opens or prices
    return pd.DataFrame({
        "open": opens, "close": prices,
        "low": lows or [min(o, c) for o, c in zip(opens, prices)],
        "high": highs or [max(o, c) for o, c in zip(opens, prices)],
        "volume": 1.0,
    }, index=idx)


def scripted(entries, exits, stop_dist=1.0):
    """A fake strategy that enters/exits on the candle numbers given."""
    def strat(df, **_):
        out = pd.DataFrame(index=df.index)
        out["entry"] = [entries.get(i, 0) for i in range(len(df))]
        out["tag"] = "test"
        out["stop_dist"] = stop_dist
        out["exit_long_test"] = [i in exits for i in range(len(df))]
        out["exit_short_test"] = [i in exits for i in range(len(df))]
        return out
    return strat


def cfg_for(monkeypatch, strat, **risk):
    monkeypatch.setitem(STRATEGIES, "test", strat)
    return Config(strategy="test", symbols=["X/USDT"], risk=RiskSettings(**risk))


def test_example_config_loads_and_is_safe():
    cfg = load_config("config.example.yaml")
    assert cfg.market == "spot"
    assert cfg.risk.futures_enabled is False
    assert cfg.risk.max_leverage <= 2
    assert cfg.starting_usdt == pytest.approx(5000 / 129)


def test_config_refuses_unsafe_settings():
    with pytest.raises(ValueError):
        Config(market="future").validate()
    with pytest.raises(ValueError):
        Config(risk=RiskSettings(max_leverage=5)).validate()


def test_size_risks_one_percent_and_respects_slots():
    rm = RiskManager(RiskSettings(risk_per_trade=0.01, max_open_positions=3))
    # 1% of 1000 = 10 USDT risk; stop 5 away -> 2 coins = 200 USDT, under the 333 slot
    assert rm.size(1000, 100, 5).qty == pytest.approx(2)
    # Tight stop would want 1000 coins; capped at one slot (1000/3 USDT)
    assert rm.size(1000, 100, 0.01).qty * 100 == pytest.approx(1000 / 3)
    # Too small for the exchange minimum
    assert rm.size(10, 100, 5).qty == 0


def test_spot_never_shorts_and_daily_limit_blocks():
    rm = RiskManager(RiskSettings(), "spot")
    assert rm.can_open(-1, 0)[0] is False
    rm.start_of_candle("d1", 100)
    rm.check_daily_loss(96.9)
    assert rm.can_open(1, 0) == (False, "daily loss limit reached")
    rm.start_of_candle("d2", 96.9)
    assert rm.can_open(1, 0)[0] is True


def test_entry_fills_at_next_open(monkeypatch):
    cfg = cfg_for(monkeypatch, scripted({1: 1}, {3}, stop_dist=5))
    cfg.backtest.fee_rate = 0
    cfg.backtest.slippage = 0
    df = candles([100, 100, 110, 120, 130], opens=[100, 100, 105, 115, 125])
    res = backtest.run(cfg, {"X/USDT": df}, start_balance=1000)
    trade = res.trades.iloc[0]
    assert trade["entry_price"] == 105          # open of candle 2, not close of candle 1
    assert trade["exit_price"] == 125           # exit signal on 3 -> open of candle 4
    assert trade["exit_reason"] == "signal"


def test_stop_loss_limits_loss_to_about_one_percent(monkeypatch):
    cfg = cfg_for(monkeypatch, scripted({0: 1}, set(), stop_dist=5))
    cfg.backtest.fee_rate = 0
    cfg.backtest.slippage = 0
    df = candles([100, 100, 90, 90], opens=[100, 100, 99, 90], lows=[100, 99, 80, 90])
    res = backtest.run(cfg, {"X/USDT": df}, start_balance=1000)
    trade = res.trades.iloc[0]
    assert trade["exit_reason"] == "stop-loss"
    assert trade["exit_price"] == 95
    assert trade["pnl"] == pytest.approx(-10)   # 1% of 1000
    assert res.equity.iloc[-1] == pytest.approx(990)


def test_all_strategies_run_on_sample_data():
    df = synthetic_candles(n=1500)
    cfg = load_config("config.example.yaml")
    for name in ["auto", "ema_adx", "donchian", "bb_rsi"]:
        cfg.strategy = name
        res = backtest.run(cfg, {"ETH/USDT": df})
        s = res.summary()
        assert s["end_balance"] > 0
        assert set(res.trades["side"]) <= {"long"} if len(res.trades) else True  # spot: longs only
