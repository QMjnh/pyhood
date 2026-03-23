"""
IBS (Internal Bar Strength) Strategy — "ES cuh"
Exact replication of 13-line Pine Script.

Pine logic:
    ibs = (close - low) / (high - low)
    enter_long = ibs < 0.2 and position_size == 0
    exit_long = ibs > 0.8 or (bars_in_trade > 30)

Long only. SPY daily. 10% of equity per trade.
TV benchmark: 961 trades, 67% win rate, PF 1.848, +2330% P&L
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def generate_signals(df: pd.DataFrame, params=None) -> pd.DataFrame:
    p = params or {}
    low_ibs = p.get("low_ibs", 0.2)
    high_ibs = p.get("high_ibs", 0.8)
    max_bars = p.get("max_bars", 30)

    df = df.copy()
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    n = len(df)

    ibs = (closes - lows) / np.where((highs - lows) == 0, 1e-10, (highs - lows))

    signal = np.zeros(n, dtype=int)
    pos = 0
    entry_bar = 0

    for i in range(n):
        if pos == 0:
            # Entry: IBS < 0.2 and flat
            if ibs[i] < low_ibs:
                pos = 1
                entry_bar = i
        else:
            # Exit: IBS > 0.8 OR held > 30 bars
            bars_held = i - entry_bar
            if ibs[i] > high_ibs or bars_held > max_bars:
                pos = 0

        signal[i] = pos

    # No shift: engine handles fill timing via enter_at_open
    df["signal"] = signal
    return df
