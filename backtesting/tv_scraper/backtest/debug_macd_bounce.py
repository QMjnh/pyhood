#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Debug: analyze why we get 95 trades vs TV's 56.
Check if the extra trades come from MACD barely crossing threshold.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from data import fetch_crypto, fetch_alpaca_resampled
from strategies.macd_bounce import generate_signals, compute_macd


def main():
    print("Fetching Alpaca BTC/USD 1H → 4H...")
    df = fetch_alpaca_resampled(
        ticker="BTC/USD",
        base_interval="1h",
        target_interval="4h",
        start="2020-11-01",
        end="2026-01-06",
    )
    
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
    
    params = {"fast": 12, "slow": 26, "signal_len": 9, "threshold": -350.0, "bounce": 100.0}
    df_s = generate_signals(df, params)
    
    start_dt = pd.Timestamp("2021-01-01", tz="UTC")
    end_dt = pd.Timestamp("2026-01-05 23:59:59", tz="UTC")
    df_bt = df_s[(df_s.index >= start_dt) & (df_s.index <= end_dt)].copy()
    
    # Extract all buy signals with context
    buy_bars = df_bt[df_bt["buy_signal"]]
    
    print(f"\nAll {len(buy_bars)} buy signals:")
    print(f"{'#':>3s} {'Date':>25s} {'Close':>12s} {'MACD':>10s} {'Signal':>10s}")
    
    for i, (idx, row) in enumerate(buy_bars.iterrows()):
        print(f"{i+1:>3d} {str(idx):>25s} {row['close']:>12,.2f} {row['macd']:>10.2f} {row['macd_signal']:>10.2f}")
    
    # Check: how many trades have MACD that BARELY crosses threshold?
    # The key insight: with a threshold of -350, some MACD dips are shallow
    print("\n\n=== MACD min values per arming cycle ===")
    
    macd_vals = df_bt["macd"].values
    threshold = -350.0
    bounce = 100.0
    
    armed = False
    lowest = np.nan
    cycles = []
    
    for i in range(len(df_bt)):
        ml = macd_vals[i]
        if ml < threshold and not armed:
            armed = True
            lowest = ml
            arm_date = df_bt.index[i]
        if armed and ml < threshold:
            lowest = min(lowest, ml)
        if armed and ml >= lowest + bounce:
            cycles.append({
                "arm_date": arm_date,
                "buy_date": df_bt.index[i],
                "lowest_macd": lowest,
                "macd_at_buy": ml,
                "bounce_size": ml - lowest,
            })
            armed = False
    
    print(f"\n{len(cycles)} arming cycles found:")
    print(f"{'#':>3s} {'Arm Date':>25s} {'Buy Date':>25s} {'Lowest MACD':>12s} {'MACD@Buy':>10s} {'Bounce':>8s}")
    for i, c in enumerate(cycles):
        # Mark shallow dips
        shallow = " ← SHALLOW" if c["lowest_macd"] > -500 else ""
        print(f"{i+1:>3d} {str(c['arm_date']):>25s} {str(c['buy_date']):>25s} {c['lowest_macd']:>12.2f} {c['macd_at_buy']:>10.2f} {c['bounce_size']:>8.2f}{shallow}")
    
    # Compare with TV: TV only has 56 trades, so many of our shallow dips don't occur on INDEX:BTCUSD
    shallow_count = sum(1 for c in cycles if c["lowest_macd"] > -500)
    deep_count = sum(1 for c in cycles if c["lowest_macd"] <= -500)
    print(f"\nShallow dips (lowest > -500): {shallow_count}")
    print(f"Deep dips (lowest <= -500): {deep_count}")
    
    # Also check: Does the state machine allow re-arming while in a position?
    # The Pine code says armed=false on sell, but can it re-arm before sell?
    # Looking at Pine: "if macdLine < threshold and not armed" - yes, armed can only be set 
    # when not already armed. But armed stays true until sell. So we can't have overlapping arms.
    # BUT: after sell, armed is reset. If MACD drops below threshold immediately after sell,
    # we get a new cycle. This seems correct.


if __name__ == "__main__":
    main()
