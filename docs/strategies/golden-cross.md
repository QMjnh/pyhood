# Golden Cross / Death Cross (50/200 SMA)

A long-term trend-following strategy based on the crossover of the 50-day and 200-day simple moving averages. The golden cross (50 SMA crossing above 200 SMA) is one of the most widely watched technical signals in financial markets.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `fast_period` | 50 | Fast SMA period |
| `slow_period` | 200 | Slow SMA period |

## Entry / Exit Logic

- **Buy (Golden Cross):** 50 SMA crosses above 200 SMA (no existing position)
- **Sell (Death Cross):** 50 SMA crosses below 200 SMA (holding long)

Because both moving averages are long-period, this strategy generates very few signals — typically only a handful per decade. It is designed to capture major trend shifts rather than short-term movements.

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import golden_cross

bt = Backtester.from_yfinance("SPY", period="10y")
result = bt.run(golden_cross(), "Golden Cross")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

Classic technical analysis. The golden cross and death cross have been used by market technicians since the mid-20th century. The 50/200 SMA combination became standard due to its alignment with quarterly and annual business cycles.
