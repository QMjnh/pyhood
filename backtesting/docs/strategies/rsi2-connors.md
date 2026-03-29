# RSI(2) Connors Strategy

A short-term mean reversion strategy that uses an ultra-short RSI(2) to detect extreme oversold conditions while a 200-day SMA filters for the long-term uptrend. Designed to buy sharp pullbacks in strong uptrends.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `rsi_period` | 2 | RSI calculation period (ultra-short) |
| `sma_period` | 200 | Trend filter SMA period |
| `oversold` | 10 | RSI level for buy signal |
| `overbought` | 90 | RSI level for sell signal |

## Entry / Exit Logic

- **Buy:** Close > 200 SMA (uptrend) AND RSI(2) < 10 (oversold) AND no existing position
- **Sell:** RSI(2) > 90 (overbought) AND holding long

The key insight is using RSI with a period of 2 instead of the traditional 14. This makes the indicator extremely sensitive to short-term price movements, catching 1-2 day pullbacks that often snap back quickly in trending markets.

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import rsi2_connors

bt = Backtester.from_yfinance("SPY", period="10y")
result = bt.run(rsi2_connors(), "RSI(2) Connors")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

Larry Connors, *Short-Term Trading Strategies That Work* (2008). Connors demonstrated that RSI with a period of 2 significantly outperformed the traditional RSI(14) for mean-reversion entries on S&P 500 stocks, particularly when combined with a trend filter.
