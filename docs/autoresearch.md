# AutoResearch — Automated Trading Strategy Discovery

> *Inspired by Andrej Karpathy's approach to automated research: define the search space, automate the experiments, and let the machine grind through parameter combinations while you sleep.*

## What Is It?

AutoResearch is pyhood's built-in system for systematically discovering trading strategies that **generalise** — not just ones that look good on historical data.

The core problem with manual backtesting is **overfitting**: you keep tweaking parameters until the numbers look great on past data, then the strategy falls apart in live trading. AutoResearch solves this with a disciplined Train/Test/Validate methodology borrowed from machine learning.

## Train / Test / Validate

Your historical data is split into three non-overlapping periods:

| Split    | Default | Purpose                                    |
|----------|--------:|--------------------------------------------|
| Train    |     50% | Optimise parameters here                   |
| Test     |     25% | Confirm — does it work on unseen data?     |
| Validate |     25% | Final truth — touched only once at the end |

**The golden rule:** you only optimise on Train data. Test confirms. Validate is the final seal of approval.

```
|-------- Train (50%) --------|--- Test (25%) ---|-- Validate (25%) --|
         Optimise here          Confirm here        Final check
```

## Quick Start

```python
from pyhood.autoresearch import AutoResearcher
from pyhood.backtest.strategies import ema_crossover, macd_crossover

# Create researcher (fetches 10yr SPY data once)
researcher = AutoResearcher(ticker='SPY', total_period='10y')

# Sweep EMA crossover parameters
results = researcher.parameter_sweep(
    ema_crossover, 'fast', [5, 7, 9, 11, 13, 15],
    base_params={'slow': 21},
    strategy_name='EMA Crossover'
)

# Grid search MACD across multiple parameters
results = researcher.multi_param_sweep(
    macd_crossover,
    {'fast': [8, 10, 12, 14], 'slow': [20, 24, 26, 30], 'signal': [7, 9, 11]},
    strategy_name='MACD'
)

# Validate the best on held-out data
validated = researcher.validate_best(n=3)

# Print full report
researcher.report()

# Save for later
researcher.save('my_research.json')
```

## Using Pre-Loaded Data (No yfinance)

For testing or when you already have candle data:

```python
researcher = AutoResearcher(candles=my_candle_list, min_trades=5)
```

## API Reference

### `AutoResearcher.__init__`

| Parameter       | Default | Description                                |
|-----------------|--------:|--------------------------------------------|
| `ticker`        | `'SPY'` | Symbol to fetch via yfinance               |
| `total_period`  | `'10y'` | yfinance period string                     |
| `train_pct`     |   `0.5` | Fraction of data for training              |
| `test_pct`      |  `0.25` | Fraction for testing                       |
| `validate_pct`  |  `0.25` | Fraction for validation                    |
| `metric`        | `'sharpe_ratio'` | Metric to optimise             |
| `min_trades`    |    `10` | Minimum trades for a result to count       |
| `candles`       |  `None` | Pre-loaded candles (overrides ticker)      |
| `initial_capital` | `10000` | Starting capital for backtests          |
| `top_n`         |     `3` | Top train results forwarded to test        |

### `evaluate(strategy_fn, strategy_name, dataset)`

Run a single backtest on a specific data split (`'train'`, `'test'`, or `'validate'`).

### `run_experiment(strategy_fn, strategy_name, params)`

Full pipeline: train → test (if train beats best) → log.

### `parameter_sweep(factory, param_name, values, base_params, name)`

Sweep one parameter. All values tested on train, top N on test.

### `multi_param_sweep(factory, param_grid, name)`

Grid search. All combinations on train, top N on test.

### `validate_best(n=3)`

Run top N experiments on the held-out validate set.

### `report()`

Print formatted summary of all experiments.

### `save(path)` / `load(path)`

JSON persistence for experiment logs.

## Using program.md with a Coding Agent

The file `pyhood/autoresearch/program.md` contains instructions for an AI coding agent (Claude, GPT, etc.) to use AutoResearcher autonomously. Give it to your agent and let it:

1. Explore built-in strategies with parameter sweeps
2. Create new strategy combinations
3. Validate findings
4. Report results

This is the "Karpathy loop" — automated research driven by an AI agent that follows a disciplined experimental protocol.

## Overfitting Safeguards

AutoResearch includes several mechanisms to catch overfitting:

1. **Train/Test/Validate split** — the fundamental safeguard
2. **Minimum trade filter** — strategies with < N trades are rejected (avoids degenerate "one lucky trade" strategies)
3. **Overfitting gap detection** — if train Sharpe >> test Sharpe (gap > 30%), a warning is flagged
4. **Parameter stability** — use `parameter_sweep` to check if small parameter changes kill performance (a sign of curve fitting)

### Anti-Overfitting Checklist

Before declaring a strategy "found":

- [ ] Train Sharpe > 0.8
- [ ] Test Sharpe > 0.8
- [ ] Train–Test gap < 30%
- [ ] Validate Sharpe confirms (no big drop)
- [ ] Minimum 10 trades in each split
- [ ] Nearby parameters produce similar results
- [ ] Strategy makes economic sense

## Example Workflow

```
1. researcher = AutoResearcher('SPY', '10y')
2. Sweep EMA crossover fast period → find best = 9
3. Sweep EMA crossover slow period → find best = 25
4. Grid search around best: fast=[7,9,11], slow=[20,25,30]
5. Top 3 combos tested on Test data
6. Best combo: fast=9, slow=25 → test Sharpe 1.1
7. Validate: Sharpe 0.95 → ✅ Generalises
8. researcher.save('ema_research.json')
```

## Data Models

### ExperimentResult

```python
@dataclass
class ExperimentResult:
    experiment_id: int
    strategy_code: str        # Reproducible code string
    strategy_name: str
    params: dict
    train_result: BacktestResult
    test_result: BacktestResult | None
    validate_result: BacktestResult | None
    kept: bool
    reason: str
    timestamp: str
```

### ExperimentLog

```python
@dataclass
class ExperimentLog:
    experiments: list[ExperimentResult]
    best_train_sharpe: float
    best_test_sharpe: float
    ticker: str
    total_experiments: int
```
