#!/usr/bin/env python
"""
Validate Donchian Breakout strategy on SPY daily.
Replicates Pine Script behavior: 100% equity, no costs, fills at next bar open.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backtest.data import fetch_equity
from backtest.engine import BacktestConfig, run_backtest, print_results
from backtest.strategies.donchian_breakout import generate_signals

# Fetch SPY daily — unadjusted, max history
print("Fetching SPY daily data...")
df = fetch_equity("SPY", interval="1d", years=35)
print(f"  Got {len(df)} bars from {df.index[0]} to {df.index[-1]}")
print(f"  First bar: O={df.iloc[0]['open']:.2f} H={df.iloc[0]['high']:.2f} L={df.iloc[0]['low']:.2f} C={df.iloc[0]['close']:.2f}")
print(f"  Last bar:  O={df.iloc[-1]['open']:.2f} H={df.iloc[-1]['high']:.2f} L={df.iloc[-1]['low']:.2f} C={df.iloc[-1]['close']:.2f}")

# Generate signals
print("\nGenerating signals...")
df = generate_signals(df)
n_long = (df["signal"] == 1).sum()
n_short = (df["signal"] == -1).sum()
n_flat = (df["signal"] == 0).sum()
print(f"  Signal bars: {n_long} long, {n_short} short, {n_flat} flat")

# Show first few signal transitions
print("\nFirst 10 signal transitions:")
prev_sig = 0
count = 0
for i in range(len(df)):
    sig = df["signal"].iloc[i]
    if sig != prev_sig:
        date = df.index[i]
        c = df["close"].iloc[i]
        o = df["open"].iloc[i]
        direction = {1: "LONG", -1: "SHORT", 0: "FLAT"}[sig]
        print(f"  {date.strftime('%Y-%m-%d')} → {direction} (close={c:.2f}, open={o:.2f})")
        prev_sig = sig
        count += 1
        if count >= 10:
            break

# Config: match Pine defaults exactly
config = BacktestConfig(
    initial_capital=1_000_000,
    position_size_pct=100.0,
    slippage_pct=0.0,
    commission_per_trade=0.0,
    commission_pct=0.0,
    enter_at_open=True,  # Pine default: fill at next bar open
)

print("\nRunning backtest...")
print(f"  Initial capital: ${config.initial_capital:,.0f}")
print(f"  Position size: {config.position_size_pct}% of equity")
print(f"  Enter at: next bar open")
print(f"  Slippage: {config.slippage_pct}%")
print(f"  Commission: ${config.commission_per_trade}")

result = run_backtest(df, config=config)
print_results(result, "Donchian Breakout (SPY Daily)")

# P&L %
pnl_pct = result.net_profit / config.initial_capital * 100
print(f"\n  P&L %:         {pnl_pct:>10.2f}%")

# Last 10 trades
print(f"\n{'='*80}")
print("LAST 10 TRADES")
print(f"{'='*80}")
print(f"  {'Entry Date':<12} {'Exit Date':<12} {'Dir':>5} {'Entry$':>10} {'Exit$':>10} {'PnL$':>12} {'PnL%':>8}")
print(f"  {'-'*12} {'-'*12} {'-'*5} {'-'*10} {'-'*10} {'-'*12} {'-'*8}")
for t in result.trades[-10:]:
    d = "LONG" if t.direction == 1 else "SHORT"
    print(f"  {t.entry_date.strftime('%Y-%m-%d'):<12} {t.exit_date.strftime('%Y-%m-%d'):<12} {d:>5} "
          f"{t.entry_price:>10.2f} {t.exit_price:>10.2f} {t.pnl:>12,.2f} {t.pnl_pct:>7.2f}%")

# Summary stats
print(f"\n{'='*80}")
print("SUMMARY FOR TV COMPARISON")
print(f"{'='*80}")
print(f"  Total Trades:  {result.total_trades}")
print(f"  Win Rate:      {result.win_rate:.1f}%")
print(f"  Profit Factor: {result.profit_factor:.2f}")
print(f"  Net Profit:    ${result.net_profit:,.2f}")
print(f"  P&L %:         {pnl_pct:.2f}%")
print(f"  Max Drawdown:  {result.max_drawdown:.2f}%")
print(f"  CAGR:          {result.cagr:.2f}%")
print(f"  Sharpe:        {result.sharpe:.2f}")

# Also run long-only for comparison
print(f"\n\n{'='*80}")
print("LONG-ONLY VERSION")
print(f"{'='*80}")
from backtest.strategies.donchian_breakout import generate_signals as gen_sig_orig

df2 = fetch_equity("SPY", interval="1d", years=35)
# Manually generate long-only signals
import numpy as np
length = 20
upper2 = df2["high"].rolling(window=length).max()
lower2 = df2["low"].rolling(window=length).min()
close2 = df2["close"]

long_signal2 = (close2 > upper2.shift(1)) & (close2.shift(1) <= upper2.shift(2))
short_signal2 = (close2 < lower2.shift(1)) & (close2.shift(1) >= lower2.shift(2))

n2 = len(df2)
signal2 = np.zeros(n2, dtype=int)
pos2 = 0
for i in range(n2):
    if long_signal2.iloc[i]:
        pos2 = 1
    elif short_signal2.iloc[i] and pos2 == 1:
        pos2 = 0  # Exit long, go flat (no shorts)
    signal2[i] = pos2

import pandas as pd
sig_series2 = pd.Series(signal2, index=df2.index)
shifted2 = sig_series2.shift(1).fillna(0).astype(int)
exit_prices2 = pd.Series(np.nan, index=df2.index)
signal_changed2 = shifted2 != shifted2.shift(1)
exit_prices2[signal_changed2] = df2["open"][signal_changed2]
df2["signal"] = shifted2
df2["exit_price"] = exit_prices2

result2 = run_backtest(df2, config=config)
print_results(result2, "Donchian Breakout LONG ONLY (SPY Daily)")
pnl_pct2 = result2.net_profit / config.initial_capital * 100
print(f"\n  P&L %:         {pnl_pct2:>10.2f}%")
