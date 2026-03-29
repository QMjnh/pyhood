# Volume Confirmed Breakout

A trend-following strategy that uses **Net Distribution** — a volume direction indicator — to confirm SMA breakouts. Based on the key finding from Rene Haase's analysis of 370,000 chart patterns: volume *direction* matters more than volume magnitude.

## Net Distribution

Traditional volume analysis focuses on whether volume is high or low. Net Distribution instead asks: *on the days with the highest volume, was the stock going up or down?*

- Look at the last N bars (default 20)
- Find the top 25% highest-volume bars
- Count how many were up days (close > open) vs down days
- Ratio > 0.5 = bullish volume direction, < 0.5 = bearish

This filters out false breakouts where price moves up on low conviction (low-volume up days, high-volume down days).

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `volume_period` | 20 | Lookback period for Net Distribution |
| `top_pct` | 0.25 | Fraction of bars considered high-volume |
| `threshold` | 0.6 | Net Distribution level required for buy (0.0–1.0) |
| `sma_period` | 50 | SMA period for trend filter |

## Entry / Exit Logic

- **Buy:** Close crosses above SMA AND Net Distribution > threshold (default 0.6 — 60%+ of high-volume days were up)
- **Sell:** Close crosses below SMA OR Net Distribution < (1 - threshold) (volume turns bearish)

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import volume_confirmed_breakout

bt = Backtester.from_yfinance("SPY", period="10y")
result = bt.run(volume_confirmed_breakout(), "Volume Confirmed Breakout")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

Rene Haase's 370,000 chart pattern analysis. The core insight: when high-volume bars are predominantly up days, breakouts are far more likely to follow through. Volume direction is a stronger predictor than volume magnitude.
