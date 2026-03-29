#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
RSI > 70 Buy / Exit on Cross Below 70
Exact replication of Pine Script v6 strategy.

Pine logic:
    longCondition = rsiValue > rsiLevel and rsiValue[1] <= rsiLevel
    exitCondition = ta.crossunder(rsiValue, rsiLevel)
    
    if longCondition → strategy.entry('Long', strategy.long)
    if exitCondition → strategy.close('Long')
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _rsi_wilder(close: pd.Series, length: int = 14) -> pd.Series:
    """
    RSI using Wilder's smoothing (RMA / exponential moving average with alpha=1/length).
    This matches Pine Script's ta.rsi() exactly.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = np.full(len(close), np.nan)
    avg_loss = np.full(len(close), np.nan)

    # Seed: SMA over first `length` changes (indices 1..length)
    avg_gain[length] = gain.iloc[1:length + 1].mean()
    avg_loss[length] = loss.iloc[1:length + 1].mean()

    # Wilder smoothing from length+1 onward
    for i in range(length + 1, len(close)):
        avg_gain[i] = (avg_gain[i - 1] * (length - 1) + gain.iloc[i]) / length
        avg_loss[i] = (avg_loss[i - 1] * (length - 1) + loss.iloc[i]) / length

    rs = avg_gain / np.where(avg_loss == 0, 1e-10, avg_loss)
    rsi = 100 - (100 / (1 + rs))

    return pd.Series(rsi, index=close.index)


def generate_signals(df: pd.DataFrame, params=None) -> pd.DataFrame:
    """
    Generate signals matching Pine Script logic exactly.
    
    Signal = 1 means "be long", 0 means "be flat".
    Signal transitions drive entries/exits.
    """
    df = df.copy()
    
    rsi = _rsi_wilder(df["close"], 14)
    df["rsi"] = rsi
    
    # Pine: longCondition = rsiValue > rsiLevel and rsiValue[1] <= rsiLevel
    # This is a crossover above 70
    long_entry = (rsi > 70) & (rsi.shift(1) <= 70)
    
    # Pine: exitCondition = ta.crossunder(rsiValue, rsiLevel) 
    # crossunder = current < level AND previous >= level
    exit_signal = (rsi < 70) & (rsi.shift(1) >= 70)
    
    # Build position state: Pine strategy.entry only enters if not already long
    # strategy.close only closes if long
    signal = pd.Series(0, index=df.index, dtype=int)
    pos = 0
    for i in range(len(df)):
        if pd.isna(long_entry.iloc[i]) or pd.isna(exit_signal.iloc[i]):
            signal.iloc[i] = pos
            continue
        if long_entry.iloc[i] and pos == 0:
            pos = 1
        elif exit_signal.iloc[i] and pos == 1:
            pos = 0
        signal.iloc[i] = pos
    
    # Pine: signal fires on bar N's close, order fills at bar N+1's open.
    # Engine with enter_at_open=True enters at current bar's open.
    # So shift signal forward by 1 to align: signal computed at bar N → applied at bar N+1.
    df["signal"] = signal.shift(1).fillna(0).astype(int)
    return df
