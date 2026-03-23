#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Strategy 1: Volatility Expansion Breakout

Pine Script translation:
- Higher timeframe bias: close > 200 EMA (on resampled hourly) → bullish
- ATR(14) must be rising (atr > atr[1])
- Breakout levels: highest high / lowest low over 20 bars
- Long: bull bias AND atr rising AND close > prev range high
- Short: bear bias AND atr rising AND close < prev range low
- Exit: ATR trailing stop (2x ATR) managed inside signal generation
- Position sizing: 100% of equity

TV metrics: 37.2% CAGR, PF 3.42, 0.6% DD, 575 trades
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import ta


DEFAULT_PARAMS = {
    "htf_ema_len": 200,
    "atr_len": 14,
    "atr_trail_mult": 2.0,
    "range_len": 20,
    "htf_resample": "1h",
}


def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()

    # --- Higher timeframe bias ---
    if len(df) > 2:
        median_gap = (df.index[1:] - df.index[:-1]).median()
        is_intraday = median_gap < pd.Timedelta(hours=12)
    else:
        is_intraday = False

    if is_intraday:
        htf = df["close"].resample(p["htf_resample"]).last().dropna()
        htf_ema = ta.trend.EMAIndicator(htf, window=p["htf_ema_len"]).ema_indicator()
        bias_df = pd.DataFrame({"htf_close": htf, "htf_ema": htf_ema})
        bias_df = bias_df.reindex(df.index, method="ffill")
        bull_bias = (bias_df["htf_close"] > bias_df["htf_ema"]).values
        bear_bias = (bias_df["htf_close"] < bias_df["htf_ema"]).values
    else:
        ema200 = ta.trend.EMAIndicator(df["close"], window=p["htf_ema_len"]).ema_indicator()
        bull_bias = (df["close"] > ema200).values
        bear_bias = (df["close"] < ema200).values

    # --- ATR ---
    atr_ind = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=p["atr_len"])
    atr = atr_ind.average_true_range()
    df["atr"] = atr
    atr_vals = atr.values
    atr_rising = np.zeros(len(df), dtype=bool)
    atr_rising[1:] = atr_vals[1:] > atr_vals[:-1]

    # --- Breakout levels ---
    range_high = df["high"].rolling(window=p["range_len"]).max().shift(1).values
    range_low = df["low"].rolling(window=p["range_len"]).min().shift(1).values

    closes = df["close"].values
    highs = df["high"].values
    lows = df["low"].values

    # --- Signal generation with internal trailing stop ---
    n = len(df)
    signal = np.zeros(n, dtype=int)
    pos = 0
    trail_stop = 0.0

    for i in range(n):
        c = closes[i]
        h = highs[i]
        lo = lows[i]
        a = atr_vals[i]

        if np.isnan(a) or np.isnan(range_high[i]):
            signal[i] = 0
            continue

        # Check trailing stop exit
        if pos == 1 and lo <= trail_stop:
            pos = 0
        elif pos == -1 and h >= trail_stop:
            pos = 0

        # Update trailing stop
        if pos == 1:
            new_stop = h - p["atr_trail_mult"] * a
            trail_stop = max(trail_stop, new_stop)
        elif pos == -1:
            new_stop = lo + p["atr_trail_mult"] * a
            trail_stop = min(trail_stop, new_stop)

        # Entry triggers (only when flat)
        if pos == 0:
            if bull_bias[i] and atr_rising[i] and c > range_high[i]:
                pos = 1
                trail_stop = h - p["atr_trail_mult"] * a
            elif bear_bias[i] and atr_rising[i] and c < range_low[i]:
                pos = -1
                trail_stop = lo + p["atr_trail_mult"] * a

        signal[i] = pos

    df["signal"] = signal
    return df
