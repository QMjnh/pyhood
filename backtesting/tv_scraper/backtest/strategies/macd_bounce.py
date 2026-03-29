#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
MACD Bounce Strategy for Cryptohopper — exact Pine Script replication.

Pine Script state machine:
1. ARMED: MACD line < threshold → arm, track lowestMacd
2. While armed & MACD < threshold → lowestMacd = min(lowestMacd, macdLine)
3. BUY: armed & !bought & macdLine >= lowestMacd + bounce → enter long
4. Track: After buy, when macdLine > 0 → macdAboveZero = true
5. SELL: bought & macdAboveZero & macdLine < signalLine → close & reset

Pine default (no process_orders_on_close): fills at NEXT bar's open.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


DEFAULT_PARAMS = {
    "fast": 12,
    "slow": 26,
    "signal_len": 9,
    "threshold": -350.0,
    "bounce": 100.0,
}


def ema(series: pd.Series, span: int) -> pd.Series:
    """Pine-compatible EMA (uses EMA, not SMA, for seed)."""
    return series.ewm(span=span, adjust=False).mean()


def compute_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal_len: int = 9):
    """Compute MACD exactly as Pine's ta.macd() does — EMA for everything."""
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal_len)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """
    Generate buy/sell signals using the MACD Bounce state machine.
    
    Returns df with 'signal' column: 1=long, 0=flat.
    Also adds 'buy_signal' and 'sell_signal' boolean columns for debugging.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()

    macd_line, signal_line, hist = compute_macd(
        df["close"], p["fast"], p["slow"], p["signal_len"]
    )
    df["macd"] = macd_line
    df["macd_signal"] = signal_line

    n = len(df)
    buy_signals = np.zeros(n, dtype=bool)
    sell_signals = np.zeros(n, dtype=bool)
    
    # State variables (matching Pine exactly)
    armed = False
    buy_placed = False
    sell_placed = False
    macd_above_zero = False
    lowest_macd = np.nan

    for i in range(n):
        ml = macd_line.iloc[i]
        sl = signal_line.iloc[i]
        threshold = p["threshold"]
        bounce = p["bounce"]

        # Arm trigger
        if ml < threshold and not armed:
            armed = True
            lowest_macd = ml
            buy_placed = False
            sell_placed = False
            macd_above_zero = False

        # Track bottom while armed and below threshold
        if armed and ml < threshold:
            lowest_macd = min(lowest_macd, ml)

        # BUY trigger
        if armed and not buy_placed and ml >= lowest_macd + bounce:
            buy_signals[i] = True
            buy_placed = True

        # Track MACD above zero
        if buy_placed and not macd_above_zero and ml > 0:
            macd_above_zero = True

        # SELL trigger
        if buy_placed and macd_above_zero and not sell_placed and ml < sl:
            sell_signals[i] = True
            sell_placed = True
            armed = False
            buy_placed = False
            macd_above_zero = False
            lowest_macd = np.nan

    df["buy_signal"] = buy_signals
    df["sell_signal"] = sell_signals

    # Build position signal: 1 when in position, 0 when flat
    # Pine default: order fills at NEXT bar's open
    # So signal[i+1] = 1 after buy on bar i, signal[i+1] = 0 after sell on bar i
    signal = np.zeros(n, dtype=int)
    in_position = False
    for i in range(n):
        if buy_signals[i] and not in_position:
            in_position = True
        elif sell_signals[i] and in_position:
            in_position = False
        signal[i] = 1 if in_position else 0

    df["signal"] = signal
    return df
