"""Backtesting engine for trading strategies."""

from backtest.compare import (
    benchmark_spy,
    compare_backtests,
    rank_backtests,
    regime_report,
    sensitivity_report,
    sensitivity_test,
)
from backtest.engine import Backtester
from backtest.models import BacktestResult, Candle, Trade
from backtest.strategies import (
    bollinger_breakout,
    bull_flag_breakout,
    donchian_breakout,
    ema_crossover,
    golden_cross,
    keltner_squeeze,
    ma_atr_mean_reversion,
    macd_crossover,
    rsi2_connors,
    rsi_mean_reversion,
    volume_confirmed_breakout,
)

__all__ = [
    "Backtester",
    "BacktestResult",
    "Candle",
    "Trade",
    "benchmark_spy",
    "compare_backtests",
    "rank_backtests",
    "regime_report",
    "sensitivity_report",
    "sensitivity_test",
    "bollinger_breakout",
    "bull_flag_breakout",
    "donchian_breakout",
    "ema_crossover",
    "golden_cross",
    "keltner_squeeze",
    "ma_atr_mean_reversion",
    "macd_crossover",
    "rsi2_connors",
    "rsi_mean_reversion",
    "volume_confirmed_breakout",
]
