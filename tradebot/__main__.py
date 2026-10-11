"""Command line entry point. Run `python -m tradebot --help` to see commands.

  python -m tradebot check       test the connection to Binance
  python -m tradebot download    download price history for your coins
  python -m tradebot backtest    test the strategy on that history
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import backtest, data
from .config import ROOT, load_config
from .exchange import connect, min_order_usdt
from .sample import synthetic_candles


def cmd_check(cfg, args):
    ex = connect(cfg)
    ex.load_markets()
    print(f"Connected to {cfg.exchange} ({cfg.market}).")
    for sym in cfg.symbols:
        ticker = ex.fetch_ticker(sym)
        print(f"  {sym:<12} price {ticker['last']:>12,.4f}   minimum order {min_order_usdt(ex, sym):.2f} USDT")


def cmd_download(cfg, args):
    ex = connect(cfg)
    for sym in cfg.symbols:
        print(f"Downloading {sym} {cfg.timeframe} candles from {cfg.backtest.start} ...")
        df = data.download(ex, sym, cfg.timeframe, cfg.backtest.start, cfg.backtest.end)
        path = data.candle_file(cfg.exchange, cfg.market, sym, cfg.timeframe)
        data.save(df, path)
        print(f"  saved {len(df):,} candles to {path.relative_to(ROOT)}")


def cmd_backtest(cfg, args):
    if args.strategy:
        cfg.strategy = args.strategy
    if args.synthetic:
        print("Using MADE-UP sample prices (no internet needed). Results mean nothing about real profit.\n")
        candles = {sym: synthetic_candles(seed=i, freq=cfg.timeframe) for i, sym in enumerate(cfg.symbols)}
    else:
        candles = {sym: data.load(data.candle_file(cfg.exchange, cfg.market, sym, cfg.timeframe))
                   for sym in cfg.symbols}

    result = backtest.run(cfg, candles)
    s = result.summary()
    kes = cfg.kes_per_usdt
    first = min(df.index[0] for df in candles.values()).date()
    last = max(df.index[-1] for df in candles.values()).date()

    print(f"Backtest: strategy '{cfg.strategy}', {cfg.market}, {cfg.timeframe} candles, {first} to {last}")
    print(f"Coins: {', '.join(cfg.symbols)}\n")
    print(f"  Start balance     {s['start_balance']:>10.2f} USDT  ({s['start_balance'] * kes:,.0f} KES)")
    print(f"  End balance       {s['end_balance']:>10.2f} USDT  ({s['end_balance'] * kes:,.0f} KES)")
    print(f"  Return            {s['return_pct']:>10.1f} %")
    print(f"  Buy and hold      {s['buy_hold_return_pct']:>10.1f} %   (average of the coins, for comparison)")
    print(f"  Worst drop        {s['max_drawdown_pct']:>10.1f} %   (largest fall from a high point)")
    print(f"  Trades            {s['trades']:>10d}")
    print(f"  Winning trades    {s['win_rate_pct']:>10.1f} %")
    print(f"  Profit factor     {s['profit_factor']:>10.2f}     (above 1.3 is promising; below 1 loses money)")
    print(f"  Fees paid         {s['fees_paid']:>10.2f} USDT")

    if len(result.trades):
        by = result.trades.groupby("strategy")["pnl"].agg(["count", "sum"])
        print("\n  Profit by strategy (USDT):")
        for name, row in by.iterrows():
            print(f"    {name:<10} {int(row['count']):>4} trades  {row['sum']:>8.2f}")

    out = ROOT / "results"
    out.mkdir(exist_ok=True)
    result.trades.to_csv(out / "trades.csv", index=False)
    result.equity.to_csv(out / "equity.csv")
    print(f"\nTrade list saved to results/trades.csv, balance history to results/equity.csv")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tradebot", description="Crypto trading bot")
    parser.add_argument("--config", type=Path, help="settings file (default: config.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="test the connection and show prices")
    sub.add_parser("download", help="download price history")
    bt = sub.add_parser("backtest", help="test the strategy on price history")
    bt.add_argument("--strategy", help="override the strategy in config.yaml")
    bt.add_argument("--synthetic", action="store_true", help="use made-up prices (no internet)")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
        {"check": cmd_check, "download": cmd_download, "backtest": cmd_backtest}[args.command](cfg, args)
    except (ValueError, FileNotFoundError, RuntimeError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
