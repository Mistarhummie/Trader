# Trader

A risk-first crypto trading bot for Binance, built in Python on
[ccxt](https://github.com/ccxt/ccxt) so other exchanges can be added later.

> **No trading bot guarantees profit.** This bot trades real money only after
> it has passed backtests and several weeks of paper trading. Never put in
> money you can't afford to lose.

## What works today

| Step | Status |
|---|---|
| Binance connection and price download | ✅ |
| Strategies: trend (EMA + ADX, Donchian breakout), sideways (Bollinger + RSI), auto-switch | ✅ |
| Risk manager: 1% per trade, 3% daily stop, max 3 trades, 2x leverage cap | ✅ |
| Backtester with fees, slippage and stop-losses | ✅ |
| Grid strategy | next |
| Paper trading + Telegram alerts and /stop | next |
| Web dashboard | later |
| Live trading + VPS guide | later |

## Setup (step by step)

You only do this once.

1. **Install Python 3.11 or newer** from <https://www.python.org/downloads/>.
   On Windows, tick **"Add Python to PATH"** during install.
2. **Download this code.** On the GitHub page click **Code → Download ZIP** and
   unzip it, or if you have git: `git clone https://github.com/Mistarhummie/Trader`.
3. **Open a terminal in the folder.** Windows: open the folder, click the
   address bar, type `cmd`, press Enter. Mac: right-click the folder →
   *New Terminal at Folder*.
4. **Install the bot's libraries:**
   ```
   python -m pip install -r requirements.txt
   ```
   (On Mac, use `python3` instead of `python` in every command.)
5. **Make your settings file:** copy `config.example.yaml` to `config.yaml`.
   Edit `config.yaml` to change coins, timeframe, strategy or risk limits.

No API keys are needed for backtesting. You'll add them for paper trading later.

## Running a backtest

```
python -m tradebot check        # connect to Binance and show prices + minimum order sizes
python -m tradebot download     # download price history (a few minutes)
python -m tradebot backtest     # test the strategy on that history
```

Try each strategy to compare them:

```
python -m tradebot backtest --strategy auto
python -m tradebot backtest --strategy ema_adx
python -m tradebot backtest --strategy donchian
python -m tradebot backtest --strategy bb_rsi
```

No internet? `python -m tradebot backtest --synthetic` runs on made-up prices
just to show the bot working. Those numbers mean nothing about real profit.

### Reading the results

- **Return** vs **Buy and hold**: did the bot beat simply holding the coins?
- **Worst drop**: the biggest fall from a high point. Expect live to be worse.
- **Profit factor**: money won ÷ money lost. Below 1 loses money; 1.3+ is promising.
- **Fees paid**: with a small balance, fees can eat most of the profit.

A good backtest is necessary but not enough: strategies often look better on
past data than they do live. That's why paper trading comes next.

## API key safety (for paper and live trading)

- Copy `.env.example` to `.env` and put the keys there. `.env` is never uploaded to GitHub.
- On Binance, **turn withdrawals OFF** for the key. Trading only.
- When running on a VPS, restrict the key to that server's IP address.
- Use one key for paper trading and a different one for live.
- Never paste keys into a chat, an email or a screenshot.

## How it's organised

```
tradebot/
  config.py        loads config.yaml and .env
  exchange.py      ccxt connection (swap exchange in config.yaml)
  data.py          downloads and caches candles in data/
  indicators.py    EMA, RSI, ATR, ADX, Bollinger Bands, Donchian channels
  strategies/      one file per strategy, plus auto.py which switches between them
  risk.py          position sizing and loss limits (shared by backtest and live)
  backtest.py      replays history through strategies + risk manager
tests/             automated checks: run `python -m pytest`
```
