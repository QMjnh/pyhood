#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Standalone Pine Script v6 strategy replicator.

Precisely replicates TradingView's execution model:
- Signals computed at bar close
- Orders fill at NEXT bar's OPEN
- strategy.entry('Long', strategy.long) — enters if not already long
- strategy.close('Long') — closes if long
- No slippage, no commission (Pine defaults)
"""
from __future__ import annotations

import sys
from pathlib import Path
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))


def rsi_wilder(close: pd.Series, length: int = 14) -> pd.Series:
    """RSI with Wilder's smoothing — matches Pine's ta.rsi() exactly."""
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    
    avg_gain = np.full(len(close), np.nan)
    avg_loss = np.full(len(close), np.nan)
    
    # First value: SMA over first `length` periods
    avg_gain[length] = gain.iloc[1:length+1].mean()
    avg_loss[length] = loss.iloc[1:length+1].mean()
    
    for i in range(length + 1, len(close)):
        avg_gain[i] = (avg_gain[i-1] * (length - 1) + gain.iloc[i]) / length
        avg_loss[i] = (avg_loss[i-1] * (length - 1) + loss.iloc[i]) / length
    
    rs = np.where(avg_loss == 0, 100.0, avg_gain / avg_loss)
    rsi = np.where(np.isnan(avg_gain), np.nan, 100 - (100 / (1 + rs)))
    
    return pd.Series(rsi, index=close.index)


def fetch_binance_4h(end_date: str = None) -> pd.DataFrame:
    """Load BTC/USDT 4h data from cached Binance download."""
    cache_file = Path(__file__).parent / "cache" / "btcusdt_4h_binance_full.csv"
    if not cache_file.exists():
        raise FileNotFoundError(f"Run fetch_binance_data.py first")
    
    df = pd.read_csv(cache_file, parse_dates=["timestamp"], index_col="timestamp")
    if end_date:
        df = df[df.index <= end_date]
    
    print(f"Data: {len(df)} bars from {df.index[0]} to {df.index[-1]}")
    return df


def run_pine_backtest(df: pd.DataFrame, initial_capital: float = 1_000_000,
                       sizing: str = "percent_equity") -> dict:
    """
    Run exact Pine Script backtest.
    
    Pine execution model:
    1. Bar N: compute RSI from close, check entry/exit conditions
    2. If condition met, order is placed
    3. Order fills at bar N+1's OPEN
    4. strategy.entry — if already long, does nothing
    5. strategy.close — if not in position, does nothing
    """
    close = df["close"].values
    open_ = df["open"].values
    
    rsi = rsi_wilder(df["close"], 14).values
    
    equity = initial_capital
    position = 0  # 0 = flat, 1 = long
    entry_price = 0.0
    qty = 0.0
    
    trades = []
    equity_curve = []
    
    pending_entry = False
    pending_exit = False
    
    for i in range(len(df)):
        # Step 1: Execute pending orders at this bar's OPEN
        if pending_exit and position == 1:
            exit_price = open_[i]
            pnl = qty * (exit_price - entry_price)
            equity = qty * exit_price
            trades.append({
                'entry_price': entry_price,
                'exit_price': exit_price,
                'qty': qty,
                'pnl': pnl,
                'pnl_pct': (exit_price / entry_price - 1) * 100,
            })
            position = 0
            qty = 0.0
            entry_price = 0.0
        
        if pending_entry and position == 0:
            entry_price = open_[i]
            if sizing == "percent_equity":
                qty = equity / entry_price
            else:
                qty = 1.0
            position = 1
        
        pending_entry = False
        pending_exit = False
        
        # Step 2: Mark to market
        if position == 1:
            current_equity = qty * close[i]
        else:
            current_equity = equity
        equity_curve.append(current_equity)
        
        # Step 3: Compute signals at this bar's close
        if i >= 1 and not np.isnan(rsi[i]) and not np.isnan(rsi[i-1]):
            if rsi[i] > 70 and rsi[i-1] <= 70:
                pending_entry = True
            if rsi[i] < 70 and rsi[i-1] >= 70:
                pending_exit = True
    
    # Close any open position at last bar's close
    if position == 1:
        exit_price = close[-1]
        pnl = qty * (exit_price - entry_price)
        equity = qty * exit_price
        trades.append({
            'entry_price': entry_price,
            'exit_price': exit_price,
            'qty': qty,
            'pnl': pnl,
            'pnl_pct': (exit_price / entry_price - 1) * 100,
        })
        equity_curve[-1] = equity
    
    eq = pd.Series(equity_curve, index=df.index)
    peak = eq.cummax()
    dd = (eq - peak) / peak
    max_dd = abs(dd.min()) * 100
    
    total_trades = len(trades)
    if total_trades == 0:
        return {'total_trades': 0}
    
    wins = [t for t in trades if t['pnl'] > 0]
    losses = [t for t in trades if t['pnl'] <= 0]
    gross_profit = sum(t['pnl'] for t in wins)
    gross_loss = abs(sum(t['pnl'] for t in losses))
    
    pf = gross_profit / gross_loss if gross_loss > 0 else float('inf')
    wr = len(wins) / total_trades * 100
    total_pnl_pct = (equity / initial_capital - 1) * 100
    
    return {
        'total_pnl_pct': total_pnl_pct,
        'max_drawdown': max_dd,
        'total_trades': total_trades,
        'win_rate': wr,
        'winning_trades': len(wins),
        'losing_trades': len(losses),
        'profit_factor': pf,
        'net_profit': equity - initial_capital,
        'final_equity': equity,
        'gross_profit': gross_profit,
        'gross_loss': gross_loss,
        'equity_curve': eq,
        'trades': trades,
    }


def print_comparison(result: dict, label: str = ""):
    if label:
        print(f"\n  [{label}]")
    print(f"    Total P&L:      {result['total_pnl_pct']:>10.2f}%  (TV: +176.74%)")
    print(f"    Max Drawdown:   {result['max_drawdown']:>10.2f}%  (TV: 16.30%)")
    print(f"    Total Trades:   {result['total_trades']:>10d}    (TV: 334)")
    print(f"    Win Rate:       {result['win_rate']:>10.2f}%  (TV: 34.43%)")
    print(f"    Winning:        {result['winning_trades']:>10d}    (TV: 115)")
    print(f"    Losing:         {result['losing_trades']:>10d}    (TV: 219)")
    print(f"    Profit Factor:  {result['profit_factor']:>10.3f}   (TV: 1.743)")
    print(f"    Net Profit:     ${result['net_profit']:>14,.2f}")
    
    trade_diff = abs(result['total_trades'] - 334) / 334 * 100
    pnl_diff = abs(result['total_pnl_pct'] - 176.74) / 176.74 * 100
    dd_diff = abs(result['max_drawdown'] - 16.30) / 16.30 * 100
    wr_diff = abs(result['win_rate'] - 34.43) / 34.43 * 100
    pf_diff = abs(result['profit_factor'] - 1.743) / 1.743 * 100
    
    print(f"\n    Deltas vs TV:")
    print(f"      Trades:  {trade_diff:>6.1f}% off  {'✓' if trade_diff < 5 else '✗'}")
    print(f"      P&L:     {pnl_diff:>6.1f}% off  {'✓' if pnl_diff < 10 else '✗'}")
    print(f"      DD:      {dd_diff:>6.1f}% off  {'✓' if dd_diff < 20 else '✗'}")
    print(f"      WR:      {wr_diff:>6.1f}% off  {'✓' if wr_diff < 5 else '✗'}")
    print(f"      PF:      {pf_diff:>6.1f}% off  {'✓' if pf_diff < 10 else '✗'}")


def main():
    print("=" * 60)
    print("Pine Script Replication: RSI > 70 Buy / Exit Cross Below 70")
    print("Instrument: BTC/USDT 4h (Binance)")
    print("=" * 60)
    
    df = fetch_binance_4h()
    
    result = run_pine_backtest(df, sizing="percent_equity")
    print_comparison(result, "100% equity sizing — full data range")
    
    # Print first and last few trades for debugging
    print(f"\n  First 3 trades:")
    for t in result['trades'][:3]:
        print(f"    Entry: {t['entry_price']:.2f} → Exit: {t['exit_price']:.2f}  PnL: {t['pnl_pct']:.2f}%")
    print(f"  Last 3 trades:")
    for t in result['trades'][-3:]:
        print(f"    Entry: {t['entry_price']:.2f} → Exit: {t['exit_price']:.2f}  PnL: {t['pnl_pct']:.2f}%")


if __name__ == "__main__":
    main()
