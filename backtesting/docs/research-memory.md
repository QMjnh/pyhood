# Research Memory

Persistent SQLite-backed intelligence layer for the autoresearch system. Each overnight run gets smarter by learning from every experiment ever run.

## Why It Matters

Without memory, every overnight run starts from zero. The same bad parameter combos get tested repeatedly, the same overfitting patterns go undetected, and promising strategies never get explored further.

Research memory fixes this by building three layers of intelligence:

1. **Raw Facts** — Every experiment result stored permanently (the `experiments` table)
2. **Learned Rules** — Auto-generated insights from patterns in the data (the `insights` table)
3. **Priorities** — What to test next, derived from insights (the `priorities` table)

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 OvernightRunner                  │
│                                                  │
│  ┌──────────────┐    ┌────────────────────────┐ │
│  │ AutoResearcher│───>│    ResearchMemory       │ │
│  │               │    │                        │ │
│  │ run_experiment│    │ ┌──────────────────┐   │ │
│  │ param_sweep   │    │ │  experiments     │   │ │
│  │ multi_sweep   │    │ │  (raw facts)     │   │ │
│  └──────────────┘    │ ├──────────────────┤   │ │
│                       │ │  insights        │   │ │
│                       │ │  (learned rules) │   │ │
│                       │ ├──────────────────┤   │ │
│                       │ │  priorities      │   │ │
│                       │ │  (what to test)  │   │ │
│                       │ ├──────────────────┤   │ │
│                       │ │  runs            │   │ │
│                       │ │  (run history)   │   │ │
│                       │ └──────────────────┘   │ │
│                       └────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

## SQLite Schema

### `experiments` — Raw Experiment Data

Every single experiment result, whether kept or discarded. Fields include train/test/validate metrics, regime breakdowns, cross-validation results, and overfitting flags.

Key fields:
- `params_json` — JSON-serialized parameter dict (sorted keys for dedup)
- `overfit_flagged` — 1 if train/test gap > 50%
- `overfit_gap` — The actual train/test performance gap ratio
- `regime_breakdown_json` — Per-regime P&L breakdown
- `cross_validation_json` — Cross-validation results across tickers

### `insights` — Auto-Generated Intelligence

Patterns detected from experiment data. Each insight has:
- `category` — One of: `strategy_performance`, `overfitting`, `regime`, `ticker`, `parameter`
- `confidence` — `high`, `medium`, or `low`
- `still_valid` — Can be invalidated when new evidence contradicts
- `source_experiment_ids` — JSON array linking back to evidence

### `priorities` — What to Test Next

Research priorities derived from insights:
- `priority_level` — `high`, `medium`, or `low`
- `status` — `pending`, `in_progress`, `completed`, or `abandoned`
- `source_insight_id` — Links back to the insight that generated it

### `runs` — Run History

Track every overnight run with start/end times, experiment counts, and outcomes.

## Insight Categories

### 1. Strategy Performance

**"X strategy consistently fails on Y ticker"**
- Trigger: Average test Sharpe < 0.3 across 3+ tickers
- Confidence: `high` if 5+ experiments, `medium` if 3-4
- Effect: `should_skip()` will block this strategy on that ticker

**"X strategy shows promise on Y ticker"**
- Trigger: Test Sharpe > 0.7 on a ticker
- Confidence: `high` if validated + cross-validated, `medium` otherwise
- Effect: Generates high-priority "explore nearby params" priority

### 2. Overfitting Detection

**"X strategy with params Y is likely overfitted"**
- Trigger: Train/test gap > 50%
- Confidence: Always `high`
- Effect: `should_skip()` will block exact same params

**"X strategy family tends to overfit on Y ticker"**
- Trigger: >60% of experiments for that strategy/ticker are overfit-flagged
- Confidence: `high` if 5+ experiments, `medium` if 3-4

### 3. Regime Insights

**"X strategy is regime-dependent"**
- Trigger: 80%+ of P&L from one regime
- Confidence: `high`

**"X strategy performs well across regimes"**
- Trigger: Profitable in 3+ regimes
- Confidence: `medium`

### 4. Parameter Insights

**"For X strategy on Y ticker, optimal param is around Z"**
- Trigger: Top 3 results have similar parameter values (within 30% of mean)
- Confidence: `medium`

### 5. Ticker Insights

**"Y ticker responds well to trend-following strategies"**
- Trigger: 2+ trend strategies have test Sharpe > 0.7
- Confidence: `medium`

## How the Overnight Runner Uses Memory

### Run Flow

```python
# 1. Initialize
memory = ResearchMemory('autoresearch_memory.db')
run_id = memory.start_run('SPY')

# 2. Before each experiment
skip, reason = memory.should_skip('SPY', strategy_name, params)
if skip:
    print(f"Skipping: {reason}")
    continue

# 3. After each experiment
memory.store_experiment(experiment, run_id, 'SPY')

# 4. Run priority experiments
for suggestion in memory.get_suggested_experiments('SPY'):
    # Run the suggested experiment
    ...

# 5. After all sweeps
insights = memory.generate_insights(run_id)
priorities = memory.generate_priorities(run_id)

# 6. Finalize
memory.end_run(run_id)
print(memory.get_run_summary(run_id))
```

### Skip Logic

`should_skip()` checks three things:
1. **Dedupe** — Has this exact ticker/strategy/params combo been run before?
2. **Failure insight** — Is there a high-confidence insight saying this strategy fails on this ticker?
3. **Overfit flag** — Is this exact strategy/params combo flagged as overfitted?

## Querying the Database Directly

The database is a standard SQLite file. You can query it directly:

```sql
-- Top strategies by test Sharpe
SELECT strategy_name, ticker, test_sharpe, train_sharpe, overfit_gap
FROM experiments
WHERE test_sharpe IS NOT NULL AND kept = 1
ORDER BY test_sharpe DESC
LIMIT 20;

-- Overfitting rates by strategy family
SELECT
    SUBSTR(strategy_name, 1, INSTR(strategy_name || '(', '(') - 1) as family,
    COUNT(*) as total,
    SUM(overfit_flagged) as overfitted,
    ROUND(100.0 * SUM(overfit_flagged) / COUNT(*), 1) as overfit_pct
FROM experiments
WHERE test_sharpe IS NOT NULL
GROUP BY family
ORDER BY overfit_pct DESC;

-- Active insights
SELECT category, confidence, insight_text
FROM insights
WHERE still_valid = 1
ORDER BY confidence, created_date DESC;

-- Pending priorities
SELECT priority_level, description
FROM priorities
WHERE status = 'pending'
ORDER BY CASE priority_level
    WHEN 'high' THEN 1
    WHEN 'medium' THEN 2
    WHEN 'low' THEN 3
END;
```

## Inspecting and Overriding Insights

```python
from pyhood.autoresearch.memory import ResearchMemory

mem = ResearchMemory('autoresearch_memory.db')

# View all active insights
for insight in mem.get_insights():
    print(f"[{insight['confidence']}] {insight['category']}: {insight['insight_text']}")

# Invalidate a wrong insight
mem.invalidate_insight(insight_id=5, reason="New data shows this was incorrect")

# Check what's being skipped
skip, reason = mem.should_skip('SPY', 'EMA (fast=5, slow=20)', {'fast': 5, 'slow': 20})
print(f"Skip: {skip}, Reason: {reason}")
```

## Code Examples

### Basic Usage

```python
from pyhood.autoresearch.memory import ResearchMemory

# Create or connect to database
mem = ResearchMemory('my_research.db')

# Start a run
run_id = mem.start_run('SPY')

# Store experiments (after running them via AutoResearcher)
exp_id = mem.store_experiment(experiment_result, run_id, 'SPY')

# Generate intelligence
insights = mem.generate_insights(run_id)
priorities = mem.generate_priorities(run_id)

# End run
mem.end_run(run_id)

# Get summary
print(mem.get_run_summary(run_id))
print(mem.stats())
```

### With OvernightRunner

```python
from pyhood.autoresearch.overnight import OvernightRunner

# Memory is auto-initialized
runner = OvernightRunner(
    ticker='SPY',
    memory_db='my_research.db',  # default: autoresearch_memory.db
)
result = runner.run()
print(result.get('memory_stats'))
```

### With AutoResearcher

```python
from pyhood.autoresearch.memory import ResearchMemory
from pyhood.autoresearch.runner import AutoResearcher

mem = ResearchMemory('my_research.db')
researcher = AutoResearcher(ticker='SPY', memory=mem)

# Experiments are auto-stored when memory is provided
researcher.run_experiment(strategy_fn, 'EMA 5/20', params={'fast': 5, 'slow': 20})
```

## Building on Top

The SQLite database is a foundation for:

- **Dashboard** — Query experiments/insights for a web UI
- **Visualization** — Plot parameter landscapes, overfitting gaps, regime breakdowns
- **Cross-run analysis** — Compare performance across different tickers/timeframes
- **Strategy lifecycle** — Track a strategy from discovery through validation to deployment
- **Automated reports** — Generate nightly summaries from `get_run_summary()`
