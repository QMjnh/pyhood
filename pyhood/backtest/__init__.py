"""Backtesting engine for pyhood strategies."""

from pyhood.backtest.compare import benchmark_spy, compare_backtests, rank_backtests
from pyhood.backtest.engine import Backtester
from pyhood.backtest.models import BacktestResult, Trade
from pyhood.backtest.strategies import (
    bollinger_breakout,
    donchian_breakout,
    ema_crossover,
    golden_cross,
    keltner_squeeze,
    ma_atr_mean_reversion,
    macd_crossover,
    rsi2_connors,
    rsi_mean_reversion,
)

__all__ = [
    "Backtester",
    "BacktestResult",
    "Trade",
    "benchmark_spy",
    "compare_backtests",
    "rank_backtests",
    "bollinger_breakout",
    "donchian_breakout",
    "ema_crossover",
    "golden_cross",
    "keltner_squeeze",
    "ma_atr_mean_reversion",
    "macd_crossover",
    "rsi2_connors",
    "rsi_mean_reversion",
]
