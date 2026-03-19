# Strategy Catalog

A catalog of built-in trading strategies with reproducible backtest results. All strategies are implemented in pure Python with no external dependencies.

Each strategy follows the same interface: a factory function that returns a callable `(candles, position) -> signal`. This makes them plug-and-play with the `Backtester` engine.

## Benchmark Comparison

All strategies benchmarked with default parameters, $10,000 initial capital, 10yr period.

### Trend Following

| Strategy | SPY | QQQ | AAPL | TSLA | BTC |
|---|---|---|---|---|---|
| [EMA Crossover](ema-crossover.md) | TBD | TBD | TBD | TBD | TBD |
| [MACD Crossover](macd-crossover.md) | TBD | TBD | TBD | TBD | TBD |
| [Golden Cross](golden-cross.md) | TBD | TBD | TBD | TBD | TBD |
| [Donchian Breakout](donchian-breakout.md) | TBD | TBD | TBD | TBD | TBD |

### Mean Reversion

| Strategy | SPY | QQQ | AAPL | TSLA | BTC |
|---|---|---|---|---|---|
| [RSI Mean Reversion](rsi-mean-reversion.md) | TBD | TBD | TBD | TBD | TBD |
| [RSI(2) Connors](rsi2-connors.md) | TBD | TBD | TBD | TBD | TBD |
| [MA+ATR Mean Reversion](ma-atr-mean-reversion.md) | TBD | TBD | TBD | TBD | TBD |

### Volatility

| Strategy | SPY | QQQ | AAPL | TSLA | BTC |
|---|---|---|---|---|---|
| [Bollinger Breakout](bollinger-breakout.md) | TBD | TBD | TBD | TBD | TBD |
| [Keltner Squeeze](keltner-squeeze.md) | TBD | TBD | TBD | TBD | TBD |

### Benchmark

| Strategy | SPY | QQQ | AAPL | TSLA | BTC |
|---|---|---|---|---|---|
| **SPY Buy & Hold** | TBD | TBD | TBD | TBD | TBD |

Each cell shows `Return% / Sharpe`. Run `examples/strategy_catalog.py` to reproduce these results with live data.

## Quick Start

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import ema_crossover, macd_crossover, golden_cross

bt = Backtester.from_yfinance("SPY", period="10y")

result = bt.run(ema_crossover(), "EMA Crossover")
print(f"Return: {result.total_return:.2f}%  Sharpe: {result.sharpe_ratio:.2f}")

result = bt.run(macd_crossover(), "MACD Crossover")
print(f"Return: {result.total_return:.2f}%  Sharpe: {result.sharpe_ratio:.2f}")

result = bt.run(golden_cross(), "Golden Cross")
print(f"Return: {result.total_return:.2f}%  Sharpe: {result.sharpe_ratio:.2f}")
```
