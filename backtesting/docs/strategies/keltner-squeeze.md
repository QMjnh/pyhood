# Keltner Channel Squeeze

A volatility breakout strategy that detects when Bollinger Bands contract inside Keltner Channels (a "squeeze"), then trades the breakout direction when volatility expands. Inspired by John Carter's TTM Squeeze indicator.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `keltner_period` | 20 | EMA/ATR period for Keltner Channel |
| `keltner_atr_mult` | 1.5 | ATR multiplier for Keltner bands |
| `bb_period` | 20 | Bollinger Bands period |
| `bb_std` | 2.0 | Bollinger Bands standard deviation multiplier |

## Entry / Exit Logic

**Keltner Channel:**
- Middle = EMA(close, 20)
- Upper = Middle + 1.5 * ATR(20)
- Lower = Middle - 1.5 * ATR(20)

**Squeeze Detection:**
- Squeeze ON = Bollinger lower > Keltner lower AND Bollinger upper < Keltner upper
- Squeeze OFF = Bollinger Bands expand outside Keltner Channels

**Signals:**
- **Buy:** Squeeze releases (was ON, now OFF) AND close > Keltner middle (upward breakout, no existing position)
- **Sell:** Close < Keltner middle (holding long)

The squeeze state is tracked across bars using a closure variable, making this a stateful strategy.

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import keltner_squeeze

bt = Backtester.from_yfinance("SPY", period="10y")
result = bt.run(keltner_squeeze(), "Keltner Squeeze")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

John Carter, *Mastering the Trade* (2005). Carter developed the TTM Squeeze indicator based on the observation that volatility is cyclical — periods of low volatility (squeeze) are followed by periods of high volatility (expansion). The underlying Keltner Channel was originally created by Chester Keltner in *How to Make Money in Commodities* (1960) and later refined by Linda Bradford Raschke to use ATR instead of average range.
