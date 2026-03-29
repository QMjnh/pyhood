# Parameter Sensitivity Testing

Tools for measuring how sensitive a strategy's performance is to parameter choices. Essential for detecting overfitting — the most common trap in backtesting.

## Why It Matters

A strategy that returns 50% with `fast=9` but -10% with `fast=11` is likely overfit to noise. A robust strategy should perform reasonably well across a range of parameter values. The 370K chart pattern study found that many published "optimal" parameters were artifacts of curve-fitting rather than genuine market edges.

## Functions

### `sensitivity_test(backtester, strategy_factory, param_name, param_values, base_params=None, strategy_name='Strategy')`

Sweeps a single parameter while holding all others constant.

| Parameter | Description |
|---|---|
| `backtester` | A `Backtester` instance with loaded data |
| `strategy_factory` | Strategy factory function (e.g. `ema_crossover`) |
| `param_name` | Name of the parameter to sweep |
| `param_values` | List of values to test |
| `base_params` | Dict of other parameters to hold constant (optional) |
| `strategy_name` | Base name for labelling results (optional) |

Returns a list of `BacktestResult` objects, one per parameter value.

### `sensitivity_report(results, param_name)`

Formats results from `sensitivity_test` into a readable report with a stability score.

## Example

```python
from pyhood.backtest import Backtester, sensitivity_test, sensitivity_report
from pyhood.backtest.strategies import ema_crossover

bt = Backtester.from_yfinance("SPY", period="10y")
results = sensitivity_test(bt, ema_crossover, "fast", [5, 7, 9, 11, 13, 15, 17, 20])
print(sensitivity_report(results, "fast"))
```

Output:

```
=== Sensitivity Analysis: fast ===

fast          Return %      Sharpe        Win Rate %    Trades
------------  ------------  ------------  ------------  ------------
5             138.2         0.85          48.3          42
7             141.5         0.87          49.1          38
9             144.1         0.88          50.2          34
11            139.8         0.86          49.8          30
13            135.4         0.84          48.5          28
15            130.1         0.82          47.9          25
17            125.3         0.80          47.2          22
20            118.7         0.77          46.1          19

Stability score (Sharpe std dev): 0.0365
Good: Low variance — parameter choice is robust.
```

## Interpreting the Stability Score

The stability score is the standard deviation of Sharpe ratios across all tested parameter values:

| Score | Interpretation |
|---|---|
| < 0.10 | **Robust** — strategy works across parameter range |
| 0.10 – 0.30 | **Moderate** — somewhat sensitive, use with caution |
| > 0.30 | **Unstable** — likely overfit, results are noise |

## Source

Overfitting insights from the 370K chart pattern study. Parameter sensitivity testing is a standard technique in quantitative finance for distinguishing genuine edges from data-mined artifacts.
