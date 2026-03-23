#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Strategy 4: Mean Reversion Trading V1

Pine Script translation:
- RSI(7) with upper=80, lower=20
- Keltner Channel: EMA(17) ± 2.7 * ATR(17)
- MACD: EMA(16) - EMA(7), signal SMA(9), histogram * 10
- Long entry: RSI < 20 AND close < KC lower AND MACD histogram > 0 & rising
- Short entry: RSI > 80 AND close > KC upper AND MACD histogram < 0 & falling
- Long exit: SL at -1%, TP at +1.5%, or MACD histogram < 0 & falling
- Short exit: SL at +1%, TP at -1.5%, or MACD histogram > 0 & rising
- Position sizing: 100% of equity
- Only enter when flat

TV metrics: 21.6% CAGR, PF 1.79, 1.8% DD, 117 trades on NQ
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import ta


DEFAULT_PARAMS = {
    "rsi_upper": 80,
    "rsi_lower": 20,
    "rsi_length": 7,
    "kc_length": 17,
    "kc_mult": 2.7,
    "macd_short_len": 7,   # Note: Pine labels are swapped — "short" is the fast EMA
    "macd_long_len": 16,
    "macd_signal_len": 9,
    "stop_loss_pct": 0.01,   # 1%
    "take_profit_pct": 0.015,  # 1.5%
}


def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """
    Add 'signal' column: 1=long, -1=short, 0=flat.
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()

    # --- Indicators ---
    # RSI
    rsi = ta.momentum.RSIIndicator(df["close"], window=p["rsi_length"]).rsi()

    # Keltner Channel
    kc_mid = ta.trend.EMAIndicator(df["close"], window=p["kc_length"]).ema_indicator()
    atr = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=p["kc_length"]).average_true_range()
    kc_upper = kc_mid + p["kc_mult"] * atr
    kc_lower = kc_mid - p["kc_mult"] * atr

    # MACD (custom: long EMA - short EMA, which is reverse of typical)
    # Pine: MACD_Line = ta.ema(close, MACD_Lng_Len) - ta.ema(close, MACD_Sh_Len)
    ema_long = ta.trend.EMAIndicator(df["close"], window=p["macd_long_len"]).ema_indicator()
    ema_short = ta.trend.EMAIndicator(df["close"], window=p["macd_short_len"]).ema_indicator()
    macd_line = ema_long - ema_short
    macd_signal = macd_line.rolling(window=p["macd_signal_len"]).mean()
    macd_hist = 10 * (macd_line - macd_signal)
    macd_hist_prev = macd_hist.shift(1)

    # --- Entry conditions ---
    long_entry = (
        (rsi < p["rsi_lower"]) &
        (df["close"] < kc_lower) &
        (macd_hist > macd_hist_prev) & (macd_hist > 0)
    )

    short_entry = (
        (rsi > p["rsi_upper"]) &
        (df["close"] > kc_upper) &
        (macd_hist < macd_hist_prev) & (macd_hist < 0)
    )

    # --- Position management with SL/TP/MACD exit ---
    signal = pd.Series(0, index=df.index, dtype=int)
    pos = 0
    entry_price = 0.0

    for i in range(len(df)):
        price = df["close"].iloc[i]
        mh = macd_hist.iloc[i] if not np.isnan(macd_hist.iloc[i]) else 0
        mh_prev = macd_hist_prev.iloc[i] if not np.isnan(macd_hist_prev.iloc[i]) else 0

        # Check exits
        if pos == 1:
            sl_hit = price < entry_price * (1 - p["stop_loss_pct"])
            tp_hit = price > entry_price * (1 + p["take_profit_pct"])
            macd_exit = (mh < 0) and (mh < mh_prev)
            if sl_hit or tp_hit or macd_exit:
                pos = 0
                entry_price = 0.0

        elif pos == -1:
            sl_hit = price > entry_price * (1 + p["stop_loss_pct"])
            tp_hit = price < entry_price * (1 - p["take_profit_pct"])
            macd_exit = (mh > 0) and (mh > mh_prev)
            if sl_hit or tp_hit or macd_exit:
                pos = 0
                entry_price = 0.0

        # Check entries (only when flat)
        if pos == 0:
            if i < len(df) and long_entry.iloc[i]:
                pos = 1
                entry_price = price
            elif i < len(df) and short_entry.iloc[i]:
                pos = -1
                entry_price = price

        signal.iloc[i] = pos

    df["signal"] = signal
    return df
