# Donchian Channel Breakout (Turtle Trading)

A trend-following breakout strategy based on Richard Dennis's famous Turtle Trading experiment. Buys when price breaks above the highest high of the last N bars and sells when price breaks below the lowest low of a shorter lookback period.

## Parameters

| Parameter | Default | Description |
|---|---|---|
| `entry_period` | 20 | Lookback for entry channel (highest high) |
| `exit_period` | 10 | Lookback for exit channel (lowest low) |

## Entry / Exit Logic

- **Buy:** Close breaks above the previous bar's entry-period high channel (no existing position)
- **Sell:** Close breaks below the previous bar's exit-period low channel (holding long)

The asymmetry between entry (20-bar) and exit (10-bar) periods is intentional — a wider entry channel filters out noise while a tighter exit channel protects profits faster.

## Code Example

```python
from pyhood.backtest import Backtester
from pyhood.backtest.strategies import donchian_breakout

bt = Backtester.from_yfinance("SPY", period="10y")
result = bt.run(donchian_breakout(entry_period=20, exit_period=10), "Donchian Breakout")

print(f"Total Return: {result.total_return:.2f}%")
print(f"Sharpe Ratio: {result.sharpe_ratio:.2f}")
print(f"Win Rate: {result.win_rate:.1f}%")
print(f"Total Trades: {result.total_trades}")
```

## Source

Richard Dennis and the Turtle Trading Experiment (1983). Dennis recruited and trained a group of novice traders ("Turtles") using a mechanical breakout system based on Donchian Channels. The experiment demonstrated that trading could be taught through systematic rules. This implementation is a simplified version — the original Turtles also used position sizing based on ATR and pyramiding rules.
