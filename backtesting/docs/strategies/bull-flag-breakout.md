# Bull Flag Breakout

A pattern-based strategy that detects **bull flag** continuation patterns and trades the breakout. The bull flag was identified as the highest-performing continuation pattern in the 370K chart pattern study.

## How It Works

A bull flag has two parts:

1. **The Pole:** A sharp upward move (at least 5% gain by default) over a short period — this represents strong buying pressure.
2. **The Flag:** A consolidation or slight pullback that retraces no more than 50% of the pole, lasting no more than 15 bars — this represents a pause, not a reversal.

The strategy buys when price breaks above the flag's upper boundary, signaling that the prior trend is resuming.

## Volume Confirmation

When `volume_confirm=True` (default), the strategy also requires that Net Distribution > 0.5 during the flag period. This ensures that the consolidation is happening on healthy volume (more up-volume than down-volume), filtering out patterns where distribution is occurring.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `pole_min_pct` | 5.0 | Minimum pole gain percentage |
| `flag_max_bars` | 15 | Maximum bars the flag may last |
| `flag_retrace_max` | 0.5 | Maximum retracement as fraction of pole height |
| `volume_confirm` | True | Require bullish volume during flag |

## Entry / Exit Logic

- **Buy:** Bull flag detected AND close > flag high (breakout)
- **Sell (stop loss):** Close < flag low
- **Sell (time exit):** 20 bars after entry
- **Sell (profit target):** Close > entry price * 1.10 (10% gain)

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import bull_flag_breakout

bt = Backtester.from_yfinance("AAPL", period="10y")
result = bt.run(bull_flag_breakout(), "Bull Flag Breakout")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

Classic technical analysis (bull flag is a well-known continuation pattern) combined with findings from Rene Haase's 370K chart pattern analysis, which confirmed the bull flag as the highest win-rate continuation pattern across large-cap equities.
