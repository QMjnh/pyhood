#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Validate MACD Bounce Strategy against TradingView benchmark.

INDEX:BTCUSD, 4H, Jan 1 2021 → Jan 5 2026
TV results: 56 trades, WR 51.79%, PF 1.594, P&L +81.39%
"""
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime, timezone
from pathlib import Path

from data import fetch_crypto, fetch_alpaca_resampled
from strategies.macd_bounce import generate_signals, compute_macd
from engine import run_backtest, BacktestConfig, print_results


# ============================================================
# TV Benchmark trades for comparison
# ============================================================
TV_TRADES = [
    # (trade_num, entry_date, entry_price, exit_date, exit_price, pnl_pct)
    (45, "2025-03-11 12:00", 81763.33, "2025-03-16 12:00", 82459.97, 0.85),
    (46, "2025-04-08 00:00", 79146.53, "2025-04-13 20:00", 83947.68, 6.07),
    (54, "2025-10-31 12:00", 110430.67, "2025-11-11 20:00", 103144.45, -6.60),
    (55, "2025-11-15 20:00", 95970.96, "2025-11-29 04:00", 90720.48, -5.47),
    (56, "2025-12-15 12:00", 89661.02, "2025-12-23 04:00", 88138.25, -1.70),
]


def run_validation(df: pd.DataFrame, source_name: str):
    """Run the full validation pipeline on a given dataset."""
    print(f"\n{'=' * 70}")
    print(f"DATA SOURCE: {source_name}")
    print(f"{'=' * 70}")
    print(f"  Total bars: {len(df)}")
    print(f"  Date range: {df.index[0]} → {df.index[-1]}")
    
    # Compare a few prices to TV
    # TV Trade 56 entry: Dec 15, 2025 12:00 @ 89,661.02
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    target_ts = pd.Timestamp("2025-12-15 12:00", tz="UTC")
    try:
        close_matches = df.index.get_indexer([target_ts], method="nearest")
        if len(close_matches) > 0 and close_matches[0] >= 0:
            nearest = df.iloc[close_matches[0]]
            print(f"  Price at ~2025-12-15 12:00 UTC: O={nearest['open']:.2f} C={nearest['close']:.2f}")
            print(f"    (TV shows entry @ 89,661.02)")
    except Exception as e:
        print(f"  Could not look up price: {e}")

    params = {
        "fast": 12, "slow": 26, "signal_len": 9,
        "threshold": -350.0, "bounce": 100.0,
    }
    df_signals = generate_signals(df, params)

    # Trim to backtest range
    start_dt = pd.Timestamp("2021-01-01", tz="UTC")
    end_dt = pd.Timestamp("2026-01-05 23:59:59", tz="UTC")
    
    if df_signals.index.tz is None:
        df_signals.index = df_signals.index.tz_localize("UTC")
    df_bt = df_signals[(df_signals.index >= start_dt) & (df_signals.index <= end_dt)].copy()
    print(f"  Backtest bars: {len(df_bt)}")
    print(f"  Buy signals: {df_bt['buy_signal'].sum()}, Sell signals: {df_bt['sell_signal'].sum()}")

    # ---- Extract trades with BOTH fill modes ----
    for fill_mode in ["next_bar_open", "signal_bar_close"]:
        trades = extract_trades(df_bt, fill_mode)
        print_trade_results(trades, fill_mode)
    
    return df_bt


def extract_trades(df_bt, fill_mode="next_bar_open"):
    """Extract trades from signal dataframe."""
    trades = []
    in_pos = False
    equity = 10000.0
    entry_price = None
    entry_date = None
    
    for i in range(len(df_bt)):
        row = df_bt.iloc[i]
        
        if row["buy_signal"] and not in_pos:
            if fill_mode == "next_bar_open" and i + 1 < len(df_bt):
                next_row = df_bt.iloc[i + 1]
                entry_price = next_row["open"]
                entry_date = df_bt.index[i + 1]
                in_pos = True
            elif fill_mode == "signal_bar_close":
                entry_price = row["close"]
                entry_date = df_bt.index[i]
                in_pos = True
        
        elif row["sell_signal"] and in_pos:
            if fill_mode == "next_bar_open" and i + 1 < len(df_bt):
                next_row = df_bt.iloc[i + 1]
                exit_price = next_row["open"]
                exit_date = df_bt.index[i + 1]
            elif fill_mode == "signal_bar_close":
                exit_price = row["close"]
                exit_date = df_bt.index[i]
            else:
                continue
            
            pnl_pct = (exit_price - entry_price) / entry_price * 100
            pnl_dollar = equity * (exit_price - entry_price) / entry_price
            equity += pnl_dollar
            
            trades.append({
                "num": len(trades) + 1,
                "entry_date": entry_date,
                "entry_price": entry_price,
                "exit_date": exit_date,
                "exit_price": exit_price,
                "pnl_pct": pnl_pct,
                "pnl_dollar": pnl_dollar,
                "equity_after": equity,
            })
            in_pos = False
    
    return trades


def print_trade_results(trades, fill_mode):
    """Print trade summary and comparison."""
    print(f"\n  --- Fill mode: {fill_mode} ---")
    print(f"  Total trades: {len(trades)}  (TV target: 56)")
    
    if not trades:
        return
    
    wins = [t for t in trades if t["pnl_pct"] > 0]
    losses = [t for t in trades if t["pnl_pct"] <= 0]
    wr = len(wins) / len(trades) * 100
    gp = sum(t["pnl_dollar"] for t in wins) if wins else 0
    gl = abs(sum(t["pnl_dollar"] for t in losses)) if losses else 0
    pf = gp / gl if gl > 0 else float("inf")
    
    equity = trades[-1]["equity_after"]
    net_pnl = equity - 10000.0
    net_pnl_pct = net_pnl / 100.0
    
    print(f"  Win Rate:      {wr:.2f}% (TV: 51.79%)")
    print(f"  Wins/Losses:   {len(wins)}/{len(losses)} (TV: 29/27)")
    print(f"  Profit Factor: {pf:.3f} (TV: 1.594)")
    print(f"  Net P&L:       ${net_pnl:,.2f} ({net_pnl_pct:.2f}%) (TV: +$8,138.70 / +81.39%)")
    
    # Max drawdown
    eq_arr = np.array([10000.0] + [t["equity_after"] for t in trades])
    peak = np.maximum.accumulate(eq_arr)
    dd = (eq_arr - peak) / peak
    max_dd = abs(dd.min()) * 100
    print(f"  Max Drawdown:  {max_dd:.2f}% (TV: 27.80%)")
    
    # First 5
    print(f"\n  First 5 trades:")
    for t in trades[:5]:
        print(f"    #{t['num']:>3d}: {t['entry_date']} @ {t['entry_price']:>12,.2f} → "
              f"{t['exit_date']} @ {t['exit_price']:>12,.2f}  ({t['pnl_pct']:+.2f}%)")
    
    # Last 5
    print(f"\n  Last 5 trades:")
    for t in trades[-5:]:
        print(f"    #{t['num']:>3d}: {t['entry_date']} @ {t['entry_price']:>12,.2f} → "
              f"{t['exit_date']} @ {t['exit_price']:>12,.2f}  ({t['pnl_pct']:+.2f}%)")
    
    # TV comparison
    print(f"\n  TV Trade Comparison:")
    for tv_num, tv_entry_dt, tv_entry_px, tv_exit_dt, tv_exit_px, tv_pnl in TV_TRADES:
        # Find trade by matching date (within 8h) rather than number
        tv_entry_ts = pd.Timestamp(tv_entry_dt, tz="UTC")
        matched = None
        for t in trades:
            entry_ts = t["entry_date"]
            if hasattr(entry_ts, 'tz') and entry_ts.tz is None:
                entry_ts = entry_ts.tz_localize("UTC")
            if abs((entry_ts - tv_entry_ts).total_seconds()) < 8 * 3600:
                matched = t
                break
        
        if matched:
            ed = abs(matched["entry_price"] - tv_entry_px)
            xd = abs(matched["exit_price"] - tv_exit_px)
            match = "✅" if ed < 500 and xd < 500 else "⚠️"
            print(f"    TV#{tv_num}: {tv_entry_dt} @ {tv_entry_px:,.2f} → {tv_exit_dt} @ {tv_exit_px:,.2f} ({tv_pnl:+.2f}%)")
            print(f"    Us#{matched['num']}: {matched['entry_date']} @ {matched['entry_price']:,.2f} → {matched['exit_date']} @ {matched['exit_price']:,.2f} ({matched['pnl_pct']:+.2f}%)")
            print(f"    Δ entry: ${ed:.2f}, Δ exit: ${xd:.2f} {match}")
        else:
            print(f"    TV#{tv_num}: {tv_entry_dt} @ {tv_entry_px:,.2f} — NO MATCH FOUND ❌")


def main():
    print("=" * 70)
    print("MACD Bounce Strategy Validation vs TradingView")
    print("INDEX:BTCUSD 4H | Jan 1 2021 → Jan 5 2026")
    print("=" * 70)

    # ---- Source 1: Binance US BTC/USDT ----
    print("\n[1] Fetching Binance US BTC/USDT 4H...")
    df_binance = fetch_crypto(
        symbol="BTC/USDT",
        exchange="binanceus",
        start="2020-11-01",
        end="2026-01-06",
        timeframe="4h",
    )
    run_validation(df_binance, "Binance US BTC/USDT 4H")

    # ---- Source 2: Alpaca BTC/USD (closer to composite index) ----
    print("\n\n[2] Fetching Alpaca BTC/USD 1H → resampled 4H...")
    try:
        df_alpaca = fetch_alpaca_resampled(
            ticker="BTC/USD",
            base_interval="1h",
            target_interval="4h",
            start="2020-11-01",
            end="2026-01-06",
        )
        run_validation(df_alpaca, "Alpaca BTC/USD 4H (resampled)")
    except Exception as e:
        print(f"  Alpaca fetch failed: {e}")

    # ---- Debug: dump MACD values around a known TV trade ----
    print(f"\n\n{'=' * 70}")
    print("DEBUG: MACD values around TV trade 56 entry (Dec 15 2025)")
    print(f"{'=' * 70}")
    
    params = {"fast": 12, "slow": 26, "signal_len": 9, "threshold": -350.0, "bounce": 100.0}
    df_dbg = generate_signals(df_binance, params)
    if df_dbg.index.tz is None:
        df_dbg.index = df_dbg.index.tz_localize("UTC")
    
    t56_range = df_dbg["2025-12-10":"2025-12-25"]
    print(f"{'Date':>25s} {'Close':>12s} {'MACD':>10s} {'Signal':>10s} {'Buy':>5s} {'Sell':>5s}")
    for idx, row in t56_range.iterrows():
        buy = "BUY" if row.get("buy_signal", False) else ""
        sell = "SELL" if row.get("sell_signal", False) else ""
        print(f"{str(idx):>25s} {row['close']:>12,.2f} {row['macd']:>10.2f} {row['macd_signal']:>10.2f} {buy:>5s} {sell:>5s}")


if __name__ == "__main__":
    main()
