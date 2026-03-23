#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Strategy 2: RSI Mean Reversion

Pine Script translation:
- RSI(3) with oversold=40, overbought=70
- Long: RSI crosses back above oversold level
- Short: RSI crosses back below overbought level
- Direction: configurable (Long Only, Short Only, Both)
- Optimized for Natural Gas Mini (MCX) on 4H timeframe

TV metrics: 53.6% CAGR, PF 1.72, 26.6% DD, 380 trades on NATURALGAS
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import ta


DEFAULT_PARAMS = {
    "rsi_length": 3,
    "oversold": 40,
    "overbought": 70,
    "direction": "Both",  # "Long Only", "Short Only", "Both"
    "await_bar_confirmation": True,
}


def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """
    Add 'signal' column: 1=long, -1=short, 0=flat.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()

    # RSI
    rsi_ind = ta.momentum.RSIIndicator(df["close"], window=p["rsi_length"])
    df["rsi"] = rsi_ind.rsi()

    # Crossover/crossunder detection
    # Long signal: RSI crosses above oversold (was below, now above)
    rsi = df["rsi"]
    prev_rsi = rsi.shift(1)
    long_cross = (prev_rsi < p["oversold"]) & (rsi >= p["oversold"])
    short_cross = (prev_rsi > p["overbought"]) & (rsi <= p["overbought"])

    can_long = p["direction"] in ("Long Only", "Both")
    can_short = p["direction"] in ("Short Only", "Both")

    # Build signal with position holding
    signal = pd.Series(0, index=df.index, dtype=int)
    pos = 0
    for i in range(len(df)):
        if long_cross.iloc[i] and can_long:
            pos = 1
        elif short_cross.iloc[i] and can_short:
            pos = -1
        # If a long signal fires and we're short, close short first
        if long_cross.iloc[i] and pos == -1 and can_long:
            pos = 1
        if short_cross.iloc[i] and pos == 1 and can_short:
            pos = -1
        signal.iloc[i] = pos

    df["signal"] = signal
    df.drop(columns=["rsi"], inplace=True, errors="ignore")
    return df
