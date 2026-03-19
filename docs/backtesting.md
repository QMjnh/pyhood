# Backtesting

pyhood includes a built-in backtesting engine for testing trading strategies against historical data. No external dependencies — pure Python.

## Quick Start

The recommended way to backtest is with Yahoo Finance data — 30+ years of history, no API key needed:

```python
from pyhood.backtest import Backtester, compare_backtests
from pyhood.backtest.strategies import ema_crossover, rsi_mean_reversion, bollinger_breakout

# Load 10 years of daily data from Yahoo Finance (recommended)
bt = Backtester.from_yfinance("AAPL", period="10y")

# Or use a specific date range
bt = Backtester.from_yfinance("GME", start="2019-01-01", end="2021-06-01")

# Run a strategy
result = bt.run(ema_crossover(fast=9, slow=21), "EMA 9/21")

# View results
print(f"Total Return:  {result.total_return:.1f}%")
print(f"Sharpe Ratio:  {result.sharpe_ratio:.2f}")
print(f"Max Drawdown:  {result.max_drawdown:.1f}%")
print(f"Win Rate:      {result.win_rate:.1f}%")
print(f"Total Trades:  {result.total_trades}")
print(f"vs Buy & Hold: {result.alpha:+.1f}%")
```

You can also use pyhood's own historical data (limited to 5 years):

```python
import pyhood

session = pyhood.refresh()
client = pyhood.PyhoodClient(session)
candles = client.get_stock_historicals("AAPL", interval="day", span="5year")
bt = Backtester(candles, initial_capital=10000)
```

!!! tip "Use `from_yfinance()` for backtesting"
    Yahoo Finance provides 30+ years of split/dividend-adjusted daily data with no API key. Robinhood only provides 5 years. For serious backtesting, always use `from_yfinance()`.

## Comparing Strategies

Run multiple strategies and compare them side by side:

```python
bt = Backtester.from_yfinance("AAPL", period="10y")

results = [
    bt.run(ema_crossover(fast=9, slow=21), "EMA 9/21"),
    bt.run(rsi_mean_reversion(oversold=30, overbought=70), "RSI Reversion"),
    bt.run(bollinger_breakout(period=20), "Bollinger Breakout"),
]

# Print comparison table
print(compare_backtests(results))

# Rank by Sharpe ratio
from pyhood.backtest import rank_backtests
ranked = rank_backtests(results, by="sharpe_ratio")
print(f"Best strategy: {ranked[0].strategy_name}")
```

## Performance Metrics

Every backtest produces a `BacktestResult` with these metrics:

| Metric | Description | Good | Bad |
|--------|-------------|------|-----|
| `total_return` | Total P/L as percentage | >20%/yr | <0% |
| `annual_return` | CAGR (compound annual growth) | >15% | <5% |
| `sharpe_ratio` | Return per unit of risk | >1.5 | <0.5 |
| `max_drawdown` | Worst peak-to-trough drop | >-15% | <-30% |
| `win_rate` | Percentage of profitable trades | >55% | <40% |
| `profit_factor` | Gross profit / gross loss | >1.5 | <1.0 |
| `total_trades` | Number of completed trades | >50 | <20 |
| `avg_trade_return` | Average P/L per trade | Positive | Negative |
| `avg_win` / `avg_loss` | Average winning/losing trade | Win > Loss | Loss > Win |
| `buy_hold_return` | What buy & hold would have returned | — | — |
| `alpha` | Strategy return minus buy & hold | Positive | Negative |

## Built-in Strategies

### EMA Crossover

Buys when the fast EMA crosses above the slow EMA. Sells when it crosses below.

```python
from pyhood.backtest.strategies import ema_crossover

strategy = ema_crossover(fast=9, slow=21)
result = bt.run(strategy, "EMA 9/21")

# Try different parameters
result2 = bt.run(ema_crossover(fast=5, slow=50), "EMA 5/50")
```

### RSI Mean Reversion

Buys when RSI drops below the oversold threshold. Sells when RSI rises above overbought.

```python
from pyhood.backtest.strategies import rsi_mean_reversion

strategy = rsi_mean_reversion(period=14, oversold=30, overbought=70)
result = bt.run(strategy, "RSI 30/70")

# More aggressive thresholds
result2 = bt.run(rsi_mean_reversion(oversold=20, overbought=80), "RSI 20/80")
```

### Bollinger Band Breakout

Buys when price closes above the upper Bollinger Band. Sells when price drops below the middle band (SMA).

```python
from pyhood.backtest.strategies import bollinger_breakout

strategy = bollinger_breakout(period=20, std_dev=2)
result = bt.run(strategy, "Bollinger 20/2")
```

## Writing Custom Strategies

A strategy is a function that receives the candles seen so far and the current position, then returns a signal:

```python
def my_strategy(candles, position):
    """Simple: buy if today's close > yesterday's close, sell otherwise.
    
    Args:
        candles: List of Candle objects seen so far
        position: 'long', 'short', or None
        
    Returns:
        'buy'   - enter long position
        'sell'  - exit long position
        'short' - enter short position (optional)
        'cover' - exit short position (optional)
        None    - do nothing
    """
    if len(candles) < 2:
        return None
        
    today = candles[-1].close_price
    yesterday = candles[-2].close_price
    
    if position is None and today > yesterday:
        return 'buy'
    elif position == 'long' and today < yesterday:
        return 'sell'
    
    return None

result = bt.run(my_strategy, "Momentum")
```

### Strategy Tips

- Return `None` when you don't want to act — don't force trades
- Check `len(candles)` before accessing historical data
- Check `position` before signaling — don't buy if already long
- Keep strategies simple — complex doesn't mean better

## Example: Comparing 3 Strategies on AAPL

Here's a complete example comparing all three built-in strategies on 5 years of AAPL data:

```python
from pyhood.backtest import Backtester, compare_backtests, rank_backtests
from pyhood.backtest.strategies import ema_crossover, rsi_mean_reversion, bollinger_breakout

# Load 5 years of AAPL history from Yahoo Finance
bt = Backtester.from_yfinance("AAPL", period="5y")

# Run all three strategies
results = [
    bt.run(ema_crossover(fast=9, slow=21), "EMA 9/21"),
    bt.run(rsi_mean_reversion(oversold=30, overbought=70), "RSI 30/70"),
    bt.run(bollinger_breakout(period=20), "Bollinger 20/2"),
]

# Compare side by side
print(compare_backtests(results))

# Find the best
ranked = rank_backtests(results, by="sharpe_ratio")
print(f"Best risk-adjusted strategy: {ranked[0].strategy_name}")
```

**Actual results (AAPL 2021-2026):**

- **EMA 9/21:** 63% return, 0.65 Sharpe, -25% drawdown, 33% win rate, 24 trades
- **RSI 30/70:** 55% return, 0.53 Sharpe, -30% drawdown, 73% win rate, 15 trades
- **Bollinger 20/2:** 54% return, 0.69 Sharpe, -13% drawdown, 46% win rate, 24 trades
- **Buy & hold:** 114% return (all strategies underperformed buy & hold)

**Key takeaways:**

- Bollinger had the best risk-adjusted return (highest Sharpe, lowest drawdown)
- RSI had the highest win rate (73%) but fewer trades and worse drawdown
- EMA had the highest total return but the worst drawdown
- None beat buy & hold — on a strong uptrend stock like AAPL, holding beats trading

## Example: Testing on a Volatile Stock (GME)

Different strategies perform differently on different stocks. Here's GME during the Roaring Kitty era:

```python
bt = Backtester.from_yfinance("GME", start="2019-06-01", end="2021-06-01")

ema = bt.run(ema_crossover(fast=9, slow=21), "EMA 9/21")
rsi = bt.run(rsi_mean_reversion(oversold=30, overbought=70), "RSI 30/70")

print(f"EMA 9/21:  {ema.total_return:.0f}% return, {ema.sharpe_ratio:.2f} Sharpe")
print(f"RSI 30/70: {rsi.total_return:.0f}% return, {rsi.sharpe_ratio:.2f} Sharpe")
print(f"Buy & Hold: {ema.buy_hold_return:.0f}%")
```

**Actual results (GME 2019-2021):**

- **EMA 9/21:** 597% return, 1.30 Sharpe, -86% drawdown, 11 trades
- **RSI 30/70:** 171% return, 0.88 Sharpe, -55% drawdown, 4 trades
- **Buy & hold:** 2,872% return

Even on GME, buy & hold crushed active trading. The squeeze was a one-time event that no technical strategy would have perfectly captured — it required the fundamental thesis (deep value + short squeeze catalyst) that Roaring Kitty identified.

## Example: Tuning Strategy Parameters

You can easily test different parameter combinations:

```python
bt = Backtester.from_yfinance("SPY", period="10y")

# Test different EMA speeds
for fast, slow in [(5, 20), (9, 21), (12, 50), (20, 100)]:
    result = bt.run(ema_crossover(fast=fast, slow=slow), f"EMA {fast}/{slow}")
    print(f"EMA {fast}/{slow}: {result.total_return:.0f}% | "
          f"Sharpe: {result.sharpe_ratio:.2f} | "
          f"Trades: {result.total_trades}")

# Test different RSI thresholds
for oversold, overbought in [(20, 80), (25, 75), (30, 70), (35, 65)]:
    result = bt.run(
        rsi_mean_reversion(oversold=oversold, overbought=overbought),
        f"RSI {oversold}/{overbought}"
    )
    print(f"RSI {oversold}/{overbought}: {result.total_return:.0f}% | "
          f"Win Rate: {result.win_rate:.0f}% | "
          f"Trades: {result.total_trades}")
```

## Verification Workflow

Use backtesting to verify strategies found on TradingView:

1. Find a top-rated strategy on TradingView
2. Note its backtest statistics (return, Sharpe, drawdown)
3. Translate the Pine Script logic to a Python strategy function
4. Run it through pyhood's backtester with the same symbol and timeframe
5. Compare results — if they match, the strategy is valid
6. If results differ significantly, investigate why before trading real money

```python
# TradingView claims: 34% return, 1.8 Sharpe, -12% drawdown
# Let's verify:
result = bt.run(translated_strategy, "TV Strategy X")

print(f"TV claims 34% return, we got {result.total_return:.1f}%")
print(f"TV claims 1.8 Sharpe, we got {result.sharpe_ratio:.2f}")
print(f"TV claims -12% drawdown, we got {result.max_drawdown:.1f}%")
```
