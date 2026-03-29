"""
Strategy: Donchian Channel Breakout (Pine Script replication)

Pine Script:
- Donchian channel: upper = highest(high, 20), lower = lowest(low, 20)
- Long entry: ta.crossover(close, upper[1])  → close > upper[1] AND close[1] <= upper[2]
- Short entry: ta.crossunder(close, lower[1]) → close < lower[1] AND close[1] >= lower[2]
- Exit long (option 1): ta.crossunder(close, lower[1]) — same as short signal
- Exit short (option 1): ta.crossover(close, upper[1]) — same as long signal
- strategy.entry reverses: short signal while long → close long + open short
- Result: strategy is always in position after first entry, just flips direction
- 100% of equity, no commission, no slippage
- Pine default: fills at next bar open
"""
from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_PARAMS = {
    "length": 20,
}


def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()
    length = p["length"]

    # Donchian channel
    upper = df["high"].rolling(window=length).max()
    lower = df["low"].rolling(window=length).min()

    close = df["close"]

    # Pine: ta.crossover(close, upper[1])
    #   = close > upper.shift(1) AND close.shift(1) <= upper.shift(2)
    long_signal = (close > upper.shift(1)) & (close.shift(1) <= upper.shift(2))

    # Pine: ta.crossunder(close, lower[1])
    #   = close < lower.shift(1) AND close.shift(1) >= lower.shift(2)
    short_signal = (close < lower.shift(1)) & (close.shift(1) >= lower.shift(2))

    # State machine: start flat, flip on signals
    # Since exit conditions == opposite entry conditions, strategy never goes flat
    n = len(df)
    signal = np.zeros(n, dtype=int)
    pos = 0

    for i in range(n):
        if long_signal.iloc[i] and not short_signal.iloc[i]:
            pos = 1
        elif short_signal.iloc[i] and not long_signal.iloc[i]:
            pos = -1
        elif long_signal.iloc[i] and short_signal.iloc[i]:
            # Both fire on same bar — Pine processes in order: long entry first, then short
            # But strategy.entry("Short") would reverse the just-opened long
            # In practice this is extremely rare; keep current position
            pass
        signal[i] = pos

    # Pine: signal fires at bar close, fills at NEXT bar's open.
    # Shift signal forward by 1: signal computed from close[i] → applied at bar i+1.
    # Engine enters at open[i+1] (enter_at_open=True) ✓
    # For exits (reversals), Pine also fills at open[i+1]. Set exit_price = open
    # on bars where signal changes so engine exits at open too.
    signal_series = pd.Series(signal, index=df.index)
    shifted = signal_series.shift(1).fillna(0).astype(int)
    
    # Mark bars where signal changes — exit should be at open, not close
    exit_prices = pd.Series(np.nan, index=df.index)
    signal_changed = shifted != shifted.shift(1)
    exit_prices[signal_changed] = df["open"][signal_changed]
    
    df["signal"] = shifted
    df["exit_price"] = exit_prices
    return df
