# TradingView Strategy Intelligence Engine — Status

## Current Phase: 1.5 — Metadata Enrichment (IN PROGRESS)

### Pipeline Overview

| Phase | Description | Status | Files |
|-------|-------------|--------|-------|
| 1 | Scrape strategy URLs + boosts | ✅ DONE | `tv_scrape.py` → `data/strategies.json` |
| 1.5 | Enrich with metadata (description, ticker, timeframe, tags) | 🔨 RUNNING | `tv_enrich.py` → `data/strategies_enriched.json` |
| 2 | Validate on author's ticker/timeframe | ⏳ NEXT | `tv_backtest.py` → `data/backtest_results.json` |
| 3 | Test generalization on similar instruments | ⏳ PLANNED | TBD |
| 4 | Build regime matcher + dynamic strategy selector | ⏳ PLANNED | TBD |

### Phase 1 — Scrape (DONE)
- **Completed:** 2026-03-20 ~10:03 PM
- **Result:** 1,000 strategies in `data/strategies.json`
- **Stats:** Boost range 0–2,000, avg 70. 248 with 50+ boosts, 131 with 100+ boosts
- **Script:** `tv_scrape.py` (Playwright, async, resume-safe, 100 pages)

### Phase 1.5 — Enrich (IN PROGRESS)
- **Started:** 2026-03-21 ~08:48 AM (test batch of 8)
- **Full run started:** 2026-03-21 ~08:55 AM
- **Script:** `tv_enrich.py` (Playwright, visits each strategy page)
- **Output:** `data/strategies_enriched.json`
- **Rate:** ~4 seconds per strategy, ~67 min for full 1,000
- **Extracts:**
  - ✅ Description text (100% success) — THE critical field for regime intelligence
  - ✅ Tags/categories (100%)
  - ✅ Strategy type: long_only / short_only / long_and_short (100%)
  - ⚠️ Default ticker (~33% via DOM selectors)
  - ⚠️ Default timeframe (~33% via DOM selectors)
  - ❌ Performance metrics (behind TradingView login wall)
  - ❌ Pine version / publish date (inconsistent)

### Known Issues & TODO
- **Ticker/timeframe extraction** — DOM selectors miss most pages because chart loads in iframe. Solution: post-processing step that parses ticker + timeframe from title + description text via regex. Much more reliable.
- **Performance metrics** — Strategy Tester tab requires TradingView login. Options: (a) use TV credentials, (b) extract from description/title, (c) do our own backtesting in Phase 2.
- **Description = regime gold** — Authors write things like "optimized for trending markets", "works best in high volatility", "designed for crypto scalping". This is the metadata we index for regime matching.

### Phase 2 — Validate (IN PROGRESS)
- Backtest each strategy on the author's own ticker/timeframe
- Python backtest engine: `backtest/engine.py`, `backtest/run.py`
- **Validated 2 strategies trade-by-trade against TradingView (2026-03-22)**

#### ⚠️ CRITICAL: Price Data Rules (Learned 2026-03-22)

**Adjusted vs Unadjusted Prices:**
- **TradingView uses UNADJUSTED prices** (raw traded prices, split-adjusted only)
- **yfinance defaults to dividend-adjusted** (`auto_adjust=True`) which retroactively lowers all historical prices to account for dividends
- **Fix applied:** `auto_adjust=False` in `backtest/data.py` for all yfinance fetches
- **Alpaca** returns unadjusted by default — no fix needed
- **Impact:** Adjusted prices shift relative indicators (IBS, RSI) at boundary values. Over 33 years of SPY data, dividend adjustment compounds to ~50% lower early prices. This causes different signal triggers, different trade counts, and wrong P&L.
- **Rule: ALWAYS use unadjusted prices when validating against TradingView**
- **Crypto has no dividends — unaffected**

**TradingView's Fill Price Model (±$0.03 on SPY):**
- TV applies a bid-ask spread simulation on every fill, even when Pine specifies no slippage
- **Entries** fill at close + $0.03 (ask side)
- **Exits** fill at close - $0.03 (bid side)
- Confirmed by comparing 10+ trades across multiple strategies — exactly $0.030 every time
- This is NOT a data source difference — underlying OHLC data is identical across yfinance (unadjusted), Alpaca, and TV
- On borderline signals (IBS within 0.005 of threshold), this $0.03 can flip a trade on/off
- **For SPY:** $0.03 / ~$650 = 0.0046% slippage per side
- **Expect ±1-2% trade count divergence** due to boundary effects — this is irreducible without using TV's exact fill model

**Data Source Summary:**
| Source | Prices | Intraday Depth | Cost |
|--------|--------|----------------|------|
| yfinance (`auto_adjust=False`) | Unadjusted, matches TV | Daily: 30yr+. 1h: 730d. 15m: 60d | Free |
| Alpaca (IEX feed) | Unadjusted, matches TV | 1min-1d: 5-7 years | Free |
| Binance US (ccxt) | Native, matches TV | 4h: back to Sep 2019 | Free |
| TradingView (ICE Data) | Reference (ground truth) | All timeframes, full history | Requires account |

#### Validation Results (2026-03-22)

**Strategy 1: RSI > 70 Buy/Exit (BTC/USDT 4h)**
- Trade rate: 39.1/yr (ours) vs 39.3/yr (TV) — ✅ identical
- 7 trades compared side-by-side: all match within 2hr timezone offset (Binance US vs Binance global)
- Trade count: 254 vs 334 — gap = Binance US starts 2019, global starts 2017

**Strategy 2: IBS Mean Reversion (SPY Daily)**
- Trades: 976 vs 961 — 15 extra from $0.03 boundary effects
- Win Rate: 68.5% vs 67.0% ✅
- PF: 1.926 vs 1.848 ✅
- 5 trades compared: dates match exactly, prices within $0.03

**Strategy 3: MACD Bounce (BTC/USD 4h) — BLOCKED: data source mismatch**
- TV uses INDEX:BTCUSD (composite index from multiple exchanges)
- Binance US, Alpaca, and yfinance all produce different BTC prices ($2,000-$3,000 off from TV)
- Strategy uses absolute MACD threshold (-350) which is exchange-specific
- Result: 94 trades vs TV's 56 — extra triggers from different MACD magnitudes
- Recent trades align on dates but price differences make exact matching impossible
- **Lesson: Strategies with absolute indicator thresholds (not relative) cannot be validated across different data sources. Only relative indicators (RSI, IBS, crossovers) are data-source-portable.**

#### ⚠️ NEW: Absolute vs Relative Thresholds
- **Relative thresholds** (RSI < 30, IBS < 0.2, EMA crossover): work across data sources because they're normalized or ratio-based
- **Absolute thresholds** (MACD < -350, price > $X, ATR > 50): tied to specific price scale. Different exchanges/feeds produce different values.
- **Rule: Only validate strategies with absolute thresholds if we have the EXACT same data feed as TV**
- INDEX:BTCUSD on TV is a composite — no public API matches it exactly

### Phase 3 — Generalize (PLANNED)
- Winners from Phase 2 get tested on similar instruments
- ETH 15m → BTC 15m, SOL 15m
- SPY daily → QQQ daily, IWM daily
- Strategies that generalize = real gold

### Phase 4 — Regime Matcher (PLANNED)
- Real-time market condition checker (VIX, trend, sector rotation)
- Query strategy DB: "strategies for high-vol bearish conditions"
- Rank by backtest performance in that regime
- Output: top 5 strategies to run today

### Architecture
```
strategies.json (1,000 URLs + boosts)
    ↓ tv_enrich.py
strategies_enriched.json (+ description, ticker, timeframe, tags)
    ↓ text parser (TODO)
strategies_classified.json (+ regime tags, asset class, parsed ticker/tf)
    ↓ tv_backtest.py
backtest_results.json (+ Sharpe, PF, win rate, drawdown)
    ↓ regime matcher (TODO)
daily_picks.json (top strategies for today's market)
```

### Existing Infrastructure
- **pyhood backtester:** 10+ built-in strategies, regime classifier (200-SMA: bull/bear/recovery/correction)
- **Autoresearch engine:** automated strategy discovery, SQLite memory, cross-validation
- **Nightly scanner:** Options scanner running midnight Mon-Fri via cron
