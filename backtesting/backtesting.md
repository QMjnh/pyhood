# Pyhood Backtesting

## Status

- **Engine:** Built-in backtester at `pyhood/backtest/engine.py`
- **Strategies:** 10+ implemented (EMA crossover, RSI mean reversion, Bollinger breakout, MACD, Golden Cross, Donchian, Keltner Squeeze, RSI(2) Connors, Volume Confirmed Breakout, Bull Flag, MA+ATR Mean Reversion)
- **Autoresearch:** 3,719 experiments run across SPY, QQQ, AAPL, TSLA, BTC-USD — 20 keepers
- **Data source:** yfinance (`from_yfinance()`) with `auto_adjust=False`
- **Revalidation script:** `revalidate_strategies.py` at project root

## Best Results (Autoresearch Keepers)

| Ticker | Strategy | Test Sharpe | Notes |
|--------|----------|-------------|-------|
| TSLA | EMA(7/20) | 1.37 | Beats train Sharpe — rare, suggests real signal not overfit |
| AAPL | EMA(8/9) | 1.21 | DD -15.8%, Return 69.9%, WR 57%, PF 2.99 |
| SPY | MACD(8/30/11) | 0.60 | DD -11.8%, Return 16.8% |
| QQQ | EMA(3/29) | 0.59 | Best of 5 QQQ keepers |
| BTC-USD | MACD(16/24/13) | 0.12 | All BTC strategies failed out-of-sample |

## Issues & Lessons Learned

### 1. Ticker Isolation Bug in Autoresearch
- **What:** `_experiment_key()` didn't include the ticker symbol. All tickers shared a single `_completed_keys` set, so only SPY got experiments — AAPL, TSLA, QQQ, BTC-USD were silently skipped.
- **Why it matters:** Silent failures are the worst kind. The autoresearch appeared to run successfully but 4 out of 5 tickers produced no results. No error, no warning.
- **Fix:** Added ticker to the experiment key and updated all callers.
- **Lesson:** Any caching or deduplication key must include ALL dimensions that define uniqueness. Always verify that multi-asset runs actually produced results for every asset.

### 2. BTC-USD: 94-99% Overfit Gap
- **What:** All 5 BTC-USD keepers had massive train-vs-test divergence. Strategies that looked great in-sample (high Sharpe, strong returns) collapsed to near-zero or negative performance out-of-sample.
- **Why it matters:** Crypto's regime shifts are more extreme than equities. Strategies trained on a bull run don't survive the next bear cycle.
- **Lesson:** A strategy that only works in one regime isn't a strategy — it's a coincidence. Overfit gap (train Sharpe minus test Sharpe, as a percentage of train) is the single most important diagnostic. Anything above 50% is suspect. Above 80% is noise.

### 3. yfinance `auto_adjust` Data Contamination
- **What:** The original autoresearch ran with yfinance's default `auto_adjust=True`, which retroactively adjusts historical prices for splits and dividends. This changes the actual OHLCV values strategies trade against.
- **Why it matters:** Adjusted prices can create phantom gaps and moves that never existed intraday. A strategy optimized on adjusted data may be fitting to adjustment artifacts, not real price action. The `revalidate_strategies.py` script was built specifically to re-run all 20 keepers with `auto_adjust=False` and compare.
- **Fix:** `Backtester.from_yfinance()` now explicitly passes `auto_adjust=False`.
- **Lesson:** Always know what your data represents. Adjusted vs. unadjusted is a silent default that can invalidate an entire research pipeline. Validate by running the same strategy on both and comparing.

### 4. TSLA experiments.json Corrupted
- **What:** JSON parse error at line 59398 in the TSLA experiments file.
- **Why it matters:** Overnight autoresearch runs can produce large output files. If the process is killed mid-write (OOM, crash, Ctrl-C), the JSON is truncated and unparseable. All results in that file are lost.
- **Lesson:** Use JSONL (one JSON object per line) instead of monolithic JSON for experiment logs. Each line is independently parseable — a crash only loses the last incomplete line, not the entire file. The autoresearch audit trail already uses JSONL for this reason.

### 5. MACD Signal Line Computed Over None-Padded Data
- **What:** In `strategies.py`, the MACD signal line replaces `None` values with `0.0` before computing the EMA. During the warm-up period (first `slow` bars), the MACD line is `None`, but the signal EMA sees `0.0` instead, which pulls the signal line toward zero.
- **Why it matters:** This creates phantom crossover signals in the early bars. The strategy might enter/exit trades based on indicator values that are mathematically wrong. For short backtests or strategies with small `slow` periods, this could materially affect results.
- **Lesson:** Never substitute `None`/`NaN` with `0.0` for indicator calculations. Either skip the warm-up period entirely or start the downstream EMA calculation only after the upstream values are valid.

### 6. Keltner Squeeze Strategy Leaks State Between Runs
- **What:** The `keltner_squeeze()` strategy uses a `nonlocal was_squeezing` variable in a closure. If the returned strategy function is reused across multiple `Backtester.run()` calls (e.g., in autoresearch parameter sweeps), the squeeze state from the previous run carries into the next.
- **Why it matters:** The first bar of run N inherits the squeeze state from the last bar of run N-1. This means results depend on execution order — running the same strategy on the same data can produce different results depending on what ran before it.
- **Lesson:** Strategy functions must be stateless between runs. Either reset mutable state at the start of each run, or use a dict/object that gets freshly created per call rather than a closure variable.

### 7. Autoresearch Results Accidentally Committed
- **What:** 300K+ lines of autoresearch result data were committed to git before `.gitignore` was updated.
- **Why it matters:** Bloats the repo permanently (git history keeps deleted files). Makes cloning slow.
- **Fix:** Added `autoresearch_results/` to `.gitignore`.
- **Lesson:** Add output/data directories to `.gitignore` BEFORE the first run, not after.

## Open Questions

- [ ] Should the MACD `None` → `0.0` padding be fixed? Would it change any of the 20 keeper results?
- [ ] Should `keltner_squeeze` be refactored to reset state per run?
- [ ] Pine Script integration (Phase 2): PyneSys converter vs. custom AST codegen — which path?
- [ ] Is the revalidation (`auto_adjust=False`) complete? Were any keepers invalidated?

## Pipeline Architecture

```
yfinance / Robinhood API
        │
        ▼
   Candle data (OHLCV)
        │
        ▼
   Backtester.run(strategy_fn)
        │
        ├── Slippage modeling
        ├── Regime classification (200-SMA)
        └── Train/Test/Validate split (50/25/25)
        │
        ▼
   BacktestResult
        ├── Sharpe, Sortino, Max DD, Profit Factor
        ├── Trade list with per-trade P&L
        ├── Equity curve
        └── Regime breakdown
        │
        ▼
   Autoresearch (parameter sweeps)
        ├── SQLite memory (experiment tracking)
        ├── JSONL audit trail
        └── Overnight continuous mode
```
