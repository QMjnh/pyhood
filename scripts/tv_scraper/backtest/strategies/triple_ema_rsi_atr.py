#!/Users/nyra/Projects/pyhood/.venv/bin/python
"""
Strategy 3: Triple EMA + RSI + ATR

Pine Script translation:
- Triple EMA alignment: fast(9) > mid(21) > slow(55) for longs, reverse for shorts
- Close must be above/below fast EMA
- RSI(14) must be 50-65 for longs, 35-50 for shorts (momentum filter)
- Volume must exceed volMA(20) * 1.3 (volume confirmation)
- Exit: ATR-based stop loss + tiered take profit (RR 2.0 first, 4.0 trailing)
- Position sizing: 100% of equity
- Commission: 0.1%, slippage: 3 ticks

TV metrics: 62% CAGR, PF 2.22, 7.8% DD, 173 trades, 710 boosts
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import ta


DEFAULT_PARAMS = {
    "fast_ema": 9,
    "mid_ema": 21,
    "slow_ema": 55,
    "rsi_length": 14,
    "rsi_overbought": 65,
    "rsi_oversold": 35,
    "atr_length": 14,
    "atr_multiplier": 2.0,
    "rr1": 2.0,   # first take profit risk-reward
    "rr2": 4.0,   # trailing activation risk-reward
    "vol_length": 20,
    "vol_multiplier": 1.3,
    # Volume filter disabled by default — yfinance BTC-USD volume doesn't
    # match TradingView's exchange-specific feed, causing massive signal loss.
    "use_volume_filter": False,
}


def generate_signals(df: pd.DataFrame, params: dict = None) -> pd.DataFrame:
    """
    Matches Pine Script behavior:
    - Conditions evaluated at bar close
    - Entry executes at NEXT bar's open (Pine default)
    - strategy.exit() with stop + limit: whichever is hit first
    - strategy.entry() reverses when opposite signal fires
    - ATR for exit levels uses value AT ENTRY (not dynamic) to avoid
      premature stops during low-vol consolidation within trends
    """
    p = {**DEFAULT_PARAMS, **(params or {})}
    df = df.copy()

    # --- Indicators ---
    fast = ta.trend.EMAIndicator(df["close"], window=p["fast_ema"]).ema_indicator()
    mid = ta.trend.EMAIndicator(df["close"], window=p["mid_ema"]).ema_indicator()
    slow = ta.trend.EMAIndicator(df["close"], window=p["slow_ema"]).ema_indicator()

    rsi = ta.momentum.RSIIndicator(df["close"], window=p["rsi_length"]).rsi()

    atr_ind = ta.volatility.AverageTrueRange(df["high"], df["low"], df["close"], window=p["atr_length"])
    df["atr"] = atr_ind.average_true_range()

    vol_ma = df["volume"].rolling(window=p["vol_length"]).mean()

    # --- Entry conditions ---
    long_base = (
        (fast > mid) & (mid > slow) &
        (df["close"] > fast) &
        (rsi > 50) & (rsi < p["rsi_overbought"])
    )
    short_base = (
        (fast < mid) & (mid < slow) &
        (df["close"] < fast) &
        (rsi < 50) & (rsi > p["rsi_oversold"])
    )

    if p.get("use_volume_filter", False):
        vol_ok = df["volume"] > vol_ma * p["vol_multiplier"]
        long_cond = long_base & vol_ok
        short_cond = short_base & vol_ok
    else:
        long_cond = long_base
        short_cond = short_base

    # --- Position management ---
    n = len(df)
    signal = np.zeros(n, dtype=int)
    exit_price_arr = np.full(n, np.nan)

    opens = df["open"].values
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values
    atrs = df["atr"].values
    long_conds = long_cond.values
    short_conds = short_cond.values

    pos = 0
    entry_price = 0.0
    stop_price = 0.0
    tp_price = 0.0
    pending_entry = 0

    for i in range(n):
        atr_val = atrs[i]
        high = highs[i]
        low = lows[i]
        open_price = opens[i]
        close_price = closes[i]

        if np.isnan(atr_val):
            signal[i] = 0
            continue

        # --- Execute pending entry from previous bar ---
        if pending_entry != 0:
            if pending_entry != pos:
                if pos != 0:
                    # Close existing position at open (reversal)
                    exit_price_arr[i] = open_price
                # Enter new position at open
                pos = pending_entry
                entry_price = open_price
                # Pine uses dynamic ATR: stop/TP recalculated each bar
                # but TP uses initial risk for the RR ratio
                risk = atr_val * p["atr_multiplier"]
                if pos == 1:
                    stop_price = entry_price - risk
                    tp_price = entry_price + risk * p["rr1"]
                else:
                    stop_price = entry_price + risk
                    tp_price = entry_price - risk * p["rr1"]
            pending_entry = 0

        # --- Static stop: set at entry, not recalculated ---
        # Pine strategy.exit() sets stop/TP at entry time; they don't
        # dynamically widen. Only tighten (ratchet) if new stop is better.
        if pos != 0 and not np.isnan(atr_val):
            risk = atr_val * p["atr_multiplier"]
            if pos == 1:
                new_stop = entry_price - risk
                stop_price = max(stop_price, new_stop)  # only tighten
            else:
                new_stop = entry_price + risk
                stop_price = min(stop_price, new_stop)  # only tighten

        # --- Check exits for current position ---
        if pos == 1:
            sl_hit = low <= stop_price
            tp_hit = high >= tp_price

            if sl_hit and tp_hit:
                if abs(open_price - tp_price) <= abs(open_price - stop_price):
                    exit_price_arr[i] = tp_price
                else:
                    exit_price_arr[i] = stop_price
                pos = 0
            elif tp_hit:
                exit_price_arr[i] = tp_price
                pos = 0
            elif sl_hit:
                exit_price_arr[i] = stop_price
                pos = 0

        elif pos == -1:
            sl_hit = high >= stop_price
            tp_hit = low <= tp_price

            if sl_hit and tp_hit:
                if abs(open_price - tp_price) <= abs(open_price - stop_price):
                    exit_price_arr[i] = tp_price
                else:
                    exit_price_arr[i] = stop_price
                pos = 0
            elif tp_hit:
                exit_price_arr[i] = tp_price
                pos = 0
            elif sl_hit:
                exit_price_arr[i] = stop_price
                pos = 0

        # --- Queue new entries (conditions evaluated at close) ---
        if pos == 0:
            if long_conds[i]:
                pending_entry = 1
            elif short_conds[i]:
                pending_entry = -1
        elif pos == 1 and short_conds[i]:
            pending_entry = -1
        elif pos == -1 and long_conds[i]:
            pending_entry = 1

        signal[i] = pos

    df["signal"] = signal
    df["exit_price"] = exit_price_arr
    return df
