# Overnight Research Execution

## Overview

The Overnight Runner automates pyhood's full strategy discovery program — all 11 built-in strategies, ~632 parameter combinations, train/test/validate splits, cross-validation — in a single unattended run. Start it before bed, wake up with results.

It's built for resilience: per-experiment error handling, configurable timeouts, automatic resume on crash, and incremental saves so you never lose more than one experiment.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Cron (optional)                       │
│  */30 * * * * /path/to/scripts/watchdog.sh              │
└──────────────────────┬──────────────────────────────────┘
                       │ checks if runner is alive
                       ▼
┌─────────────────────────────────────────────────────────┐
│              scripts/run_overnight.py                    │
│  Parses CLI args, creates OvernightRunner, calls .run() │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                  OvernightRunner                         │
│  For each strategy × parameter combo:                   │
│    1. Check if already completed (resume)               │
│    2. Create strategy_fn from factory + params           │
│    3. Run AutoResearcher.run_experiment()                │
│    4. Save results (every N experiments)                 │
│    5. Catch errors/timeouts, log, continue               │
│  After all experiments:                                  │
│    6. validate_best(n=5) on held-out data               │
│    7. Generate summary + best_strategies.json            │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│              autoresearch_results/                        │
│  experiments.json  — full machine-readable log           │
│  errors.log        — failed experiments with tracebacks  │
│  summary.md        — human-readable progress             │
│  best_strategies.json — top strategies found             │
│  run_log.txt       — timestamped log of every action     │
│  final_report.txt  — full AutoResearcher report          │
└─────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
cd ~/Projects/pyhood
python scripts/run_overnight.py
```

That's it. Default settings: SPY, 10 years of data, 0.01% slippage, 60-second timeout per experiment.

## CLI Arguments

```bash
python scripts/run_overnight.py [OPTIONS]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `--ticker` | `SPY` | Ticker symbol to research |
| `--period` | `10y` | yfinance data period (`5y`, `10y`, `max`, etc.) |
| `--results-dir` | `autoresearch_results` | Output directory for all results |
| `--timeout` | `60` | Per-experiment timeout in seconds |
| `--slippage` | `0.01` | Slippage percentage per trade |
| `--continuous` | `false` | Enable continuous mode (cycles through tickers forever) |
| `--tickers` | `SPY,QQQ,AAPL,TSLA,BTC-USD` | Comma-separated tickers for continuous mode |

### Examples

```bash
# Research QQQ with 5 years of data
python scripts/run_overnight.py --ticker QQQ --period 5y

# Longer timeout for slower machine
python scripts/run_overnight.py --timeout 120

# Custom results directory
python scripts/run_overnight.py --results-dir results/spy_march_2026

# Full custom run
python scripts/run_overnight.py \
    --ticker DIA \
    --period 10y \
    --results-dir results/dia_research \
    --timeout 90 \
    --slippage 0.02
```

## Resume Behavior

The runner is **resume-safe**. If it crashes, gets killed, or you restart your machine:

```bash
# Just run it again — it picks up where it left off
python scripts/run_overnight.py
# → "Resuming from experiment #342"
```

### How Resume Works

1. On startup, the runner checks for `experiments.json` in the results directory
2. It loads all previously completed experiments and builds a set of `strategy_name + params` keys
3. When iterating through the parameter grid, it skips any experiment that matches a completed key
4. New experiments are appended to the existing log

This means you can safely `Ctrl+C` and restart at any time.

## Error Handling

The runner wraps every experiment in a try/catch:

- **Exceptions**: Logged to `errors.log` with full traceback, then the runner moves to the next experiment
- **Timeouts**: If an experiment exceeds `--timeout` seconds, it's killed and logged as a timeout
- **Data issues**: If yfinance returns bad data or a strategy throws a math error, it's caught and logged

One bad experiment never kills the entire run. At the end, check `errors.log` to see what failed and why.

## Results Directory Structure

After a complete run, `autoresearch_results/` contains:

| File | Format | Contents |
|------|--------|----------|
| `experiments.json` | JSON | Full experiment log — every strategy tested, with train/test results, params, and timestamps. Machine-readable for further analysis. |
| `errors.log` | Text | Failed experiments with tracebacks. Check this if error count > 0. |
| `summary.md` | Markdown | Human-readable progress report. Best Sharpe found, kept strategies, progress stats. |
| `best_strategies.json` | JSON | Top strategies that passed the train→test pipeline. Quick reference for the best findings. |
| `run_log.txt` | Text | Timestamped log of every action — starts, completions, errors. The full play-by-play. |
| `final_report.txt` | Text | AutoResearcher's formatted report with all experiments, kept strategies, and validation results. |
| `watchdog.log` | Text | (If using cron watchdog) Watchdog activity log. |

## Cron Watchdog Setup

For truly unattended overnight runs, use the watchdog script. It checks every 30 minutes if the runner is still alive and restarts it if it died.

### What `watchdog.sh` Does

1. Checks if a PID file exists at `/tmp/autoresearch.pid`
2. If the PID is still running → does nothing (logs "still alive")
3. If the PID is dead (stale pidfile) → cleans up and restarts
4. If no PID file → starts the runner
5. Logs all activity to `autoresearch_results/watchdog.log`

### Installing the Cron Job

```bash
# Edit your crontab
crontab -e

# Add this line (adjust the path to your project):
*/30 * * * * /Users/you/Projects/pyhood/scripts/watchdog.sh
```

The watchdog passes through any additional arguments to `run_overnight.py`, so you can customize:

```bash
*/30 * * * * /Users/you/Projects/pyhood/scripts/watchdog.sh --ticker QQQ --period 5y
```

### Verifying the Watchdog

```bash
# Check if the cron job is installed
crontab -l | grep watchdog

# Check watchdog logs
tail -f autoresearch_results/watchdog.log

# Check if the runner is currently active
cat /tmp/autoresearch.pid && ps aux | grep run_overnight
```

## What Gets Tested

The runner tests all 11 built-in strategies with full parameter grids:

| Strategy | Parameters | Combinations |
|----------|-----------|--------------|
| EMA Crossover | fast × slow | 49 |
| MACD | fast × slow × signal | 125 |
| RSI Mean Reversion | period × oversold × overbought | 100 |
| RSI(2) Connors | rsi_period × sma_period × oversold × overbought | 192 |
| Bollinger Breakout | period × std_dev | 20 |
| Donchian Breakout | entry_period × exit_period | 30 |
| MA+ATR Mean Reversion | ma_period × entry_mult × exit_mult | 100 |
| Golden Cross | fast_period × slow_period | 16 |
| Keltner Squeeze | keltner_period × keltner_atr_mult | 16 |
| Volume Confirmed | sma_period × threshold | 16 |
| Bull Flag | pole_min_pct × flag_max_bars | 16 |
| **Total** | | **~632** |

### Expected Runtime

On a modern machine (M1 Mac, decent CPU):
- **~30 minutes** for a full run with default settings
- ~3 seconds per experiment on average
- Timeout (60s) catches runaway experiments

## Monitoring a Running Job

```bash
# Watch the log in real-time
tail -f autoresearch_results/run_log.txt

# Check progress
grep -c "Experiment" autoresearch_results/run_log.txt

# Check for errors
grep "ERROR\|TIMEOUT" autoresearch_results/run_log.txt

# Quick summary of what's been found
cat autoresearch_results/summary.md
```

## Interpreting Results

### `summary.md` — Quick Overview

Look for:
- **Best train/test Sharpe**: The highest Sharpe ratios found
- **Kept strategies**: Strategies that passed the train → test gate
- **Error/timeout counts**: Should be low (< 5% of total)

### `best_strategies.json` — Actionable Output

```json
[
    {
        "strategy_name": "EMA Crossover (fast=9, slow=25)",
        "params": {"fast": 9, "slow": 25},
        "train_sharpe": 1.2345,
        "test_sharpe": 0.9876,
        "reason": "KEPT: train=1.2345, test=0.9876"
    }
]
```

If this file is empty (`[]`), no strategy beat the baseline — which is actually the most common outcome. The market is efficient.

### What to Do Next

1. Check `best_strategies.json` — any keepers?
2. Read `summary.md` for the full picture
3. For each kept strategy, check regime breakdown and cross-validation in `final_report.txt`
4. Run the best candidates through `benchmark_spy()` manually
5. Test parameter stability with `sensitivity_test()` before trading

## Troubleshooting

| Problem | Cause | Fix |
|---------|-------|-----|
| "No historical data returned" | yfinance can't find the ticker | Check ticker symbol, try `yf.Ticker("SPY").history(period="1mo")` manually |
| All experiments timeout | Machine too slow or data too large | Increase `--timeout` to 120+ seconds |
| Empty `best_strategies.json` | No strategy beat the baseline | Normal — most strategies don't beat SPY. Try different tickers. |
| Runner dies on startup | Missing dependencies | `pip install yfinance` |
| High error count | Strategy bugs or data issues | Check `errors.log` for specific tracebacks |
| Stale PID file | Runner crashed without cleanup | Delete `/tmp/autoresearch.pid` manually |

## Custom Overnight Run (Python API)

For more control than the CLI provides:

```python
from pyhood.autoresearch.overnight import OvernightRunner, STRATEGY_SWEEPS

# Use only a subset of strategies
my_sweeps = [s for s in STRATEGY_SWEEPS if s['name'] in ['EMA Crossover', 'MACD']]

runner = OvernightRunner(
    ticker='QQQ',
    total_period='10y',
    results_dir='results/qqq_ema_macd',
    experiment_timeout=90,
    slippage_pct=0.01,
    cross_validate_tickers=['SPY', 'DIA'],
    strategy_sweeps=my_sweeps,
)

result = runner.run()
print(f"Completed: {result['total_experiments']} experiments")
print(f"Errors: {result['errors']}, Timeouts: {result['timeouts']}")
print(f"Kept: {result['kept_strategies']} strategies")
```

## Timezone Handling for Cron Scheduling

When scheduling overnight runs with `openclaw cron add --at`, **the time is interpreted as UTC by default**, not your local timezone. This can cause runs to start at unexpected times.

### The Problem

```bash
# ❌ WRONG — this runs at 1 AM UTC, which is 9 PM EDT (8 PM EST)
openclaw cron add --at "2026-03-20T01:00:00" -- python scripts/run_overnight.py
```

If you're in `America/New_York` and want the run to start at 1 AM local time, you need to either convert to UTC or specify the timezone explicitly.

### The Fix

**Option 1: Specify timezone explicitly (recommended)**

```bash
# ✅ Runs at 1 AM Eastern time, regardless of DST
openclaw cron add --at "2026-03-20T01:00:00" --tz "America/New_York" -- python scripts/run_overnight.py
```

**Option 2: Convert to UTC manually**

```bash
# ✅ 1 AM EDT = 5 AM UTC (during DST, Mar–Nov)
openclaw cron add --at "2026-03-20T05:00:00" -- python scripts/run_overnight.py

# ✅ 1 AM EST = 6 AM UTC (outside DST, Nov–Mar)
openclaw cron add --at "2026-11-20T06:00:00" -- python scripts/run_overnight.py
```

> **Tip:** Always use `--tz` to avoid DST confusion. UTC offsets change twice a year for most US timezones.

## Continuous Mode

Continuous mode runs the full strategy discovery program across multiple tickers in an infinite loop, refining results with each cycle until you stop it.

### How It Works

1. **Cycle 1 (Full Sweep):** Runs the complete ~632-combination parameter sweep for every ticker — same as a normal single-ticker run, but repeated for each ticker in sequence.
2. **Cycle 2+ (Refinement):** For each ticker, generates ~20–50 parameter variations around previous winners (±20% on each parameter), runs those, and skips combinations that memory says have already been tested or are likely to fail.
3. **Repeat forever** until you stop it.

Each cycle through all tickers generates new insights and priorities that feed into subsequent cycles. The research memory database is shared across all tickers and cycles, so the system gets smarter over time.

### Starting Continuous Mode

```bash
# Default tickers (SPY, QQQ, AAPL, TSLA, BTC-USD)
python scripts/run_overnight.py --continuous

# Custom tickers
python scripts/run_overnight.py --continuous --tickers SPY,QQQ,MSFT

# With custom timeout and results dir
python scripts/run_overnight.py --continuous --tickers SPY,QQQ --timeout 120 --results-dir results/multi
```

### Stopping Gracefully

Press **Ctrl+C** or send `kill -TERM <pid>`. The runner will:

1. Finish the current experiment (not mid-backtest)
2. Save all results for every ticker
3. Close the memory database
4. Exit cleanly

**Never lose data on Ctrl+C.** Results are saved after every single experiment.

### Results Directory Structure (Continuous)

```
autoresearch_results/
├── autoresearch_memory.db    # Shared across all tickers
├── summary.md                # Overall summary across all tickers
├── run_log.txt               # Timestamped log of everything
├── spy/
│   ├── experiments.json
│   ├── best_strategies.json
│   └── summary.md
├── qqq/
│   ├── experiments.json
│   ├── best_strategies.json
│   └── summary.md
├── aapl/
│   └── ...
├── tsla/
│   └── ...
└── btc_usd/
    └── ...
```

### Expected Runtime

- **First cycle:** ~2 hours for 5 tickers (5 × ~23 min each)
- **Subsequent cycles:** Faster — memory skips already-tested combinations, refinement generates fewer experiments per strategy
- **Overnight (8 hours):** Typically completes 3–5 full cycles, discovering increasingly refined parameter sets

### Python API

```python
from pyhood.autoresearch.overnight import OvernightRunner

runner = OvernightRunner(
    continuous=True,
    tickers=['SPY', 'QQQ', 'AAPL'],
    total_period='10y',
    results_dir='results/continuous_research',
)
result = runner.run()  # Runs until Ctrl+C
print(f"Cycles completed: {result['cycles_completed']}")
print(f"Total experiments: {result['total_experiments']}")
```

## Related Docs

- [AutoResearch](autoresearch.md) — The underlying research engine
- [Slippage](slippage.md) — How slippage is applied during overnight runs
- [Cross-Validation](cross-validation.md) — Multi-ticker validation (runs automatically)
- [Benchmarking](benchmarking.md) — Benchmark results against SPY
- [Strategies](strategies/index.md) — All 11 built-in strategies
