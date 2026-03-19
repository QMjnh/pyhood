# MACD Crossover

A trend-following strategy using the Moving Average Convergence Divergence (MACD) indicator. Trades crossovers between the MACD line and its signal line to capture momentum shifts.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `fast` | 12 | Fast EMA period |
| `slow` | 26 | Slow EMA period |
| `signal` | 9 | Signal line EMA period |

## Entry / Exit Logic

- **MACD Line:** EMA(close, 12) - EMA(close, 26)
- **Signal Line:** EMA(MACD, 9)
- **Buy:** MACD line crosses above signal line (no existing position)
- **Sell:** MACD line crosses below signal line (holding long)

The MACD measures the convergence and divergence of two moving averages. When the faster average pulls away from the slower one (MACD rising), momentum is bullish. The signal line smooths the MACD to reduce whipsaws.

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import macd_crossover

bt = Backtester.from_yfinance("SPY", period="10y")
result = bt.run(macd_crossover(fast=12, slow=26, signal=9), "MACD Crossover")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

Gerald Appel (1979). Appel created the MACD indicator and introduced it in his book *The Moving Average Convergence-Divergence Trading Method*. The 12/26/9 parameter set has become the de facto standard across virtually all charting platforms.
