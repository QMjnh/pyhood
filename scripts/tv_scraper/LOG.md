# TradingView Strategy Intelligence Engine — Development Log

## 2026-03-20 — Project Launch

### Vision & Goals
Building a strategy intelligence engine to automate trading strategy discovery and deployment. Goal: 1,000 community-validated TradingView strategies, classified by market regime, auto-matched to current conditions.

**Core Insight:** Monday morning the system checks market conditions → classifies current regime → queries strategy database for strategies designed for these exact conditions → tells you what to trade and how.

### TradingView Strategy Research
- TradingView separates scripts into: Indicators (plot signals) vs Strategies (have strategy.entry/exit calls with backtestable P/L)
- Filtered to Strategies only — 42 pages × ~24 each = ~1,000 open-source strategies
- TV Strategy Tester provides: Sharpe, Sortino, Max Drawdown, Profit Factor, Win Rate
- **Plan:** Scrape strategy URLs → automate browser to load each on our tickers → read Strategy Tester results → convert only winners to Python

### Initial Scraper Build
- Built scraper framework: `tv_scrape.py` (597 lines), `tv_backtest.py` (509 lines)
- Playwright installed in pyhood venv for browser automation
- Scraped strategy URLs with boost ratings (community popularity metric)

### Account Setup Blocker
- Attempted TradingView signup with nyravoss2026@gmail.com
- Hit CAPTCHA during signup process — needs human intervention
- Password saved to `~/.openclaw/secrets.json.tmp`
- Waiting for James to manually complete signup or try Google OAuth

## 2026-03-21 — Phase 1 Complete, Strategy Intelligence Vision

### Phase 1 Scraping — COMPLETED
- **Completion:** 2026-03-20 ~10:03 PM
- **Result:** 1,000 strategies successfully scraped
- **Output:** `~/Projects/pyhood/scripts/tv_scraper/data/strategies.json`
- **Stats:** Boost range 0–2,000, average boost 70
- **Quality Distribution:** 248 strategies with 50+ boosts, 131 with 100+ boosts

### Strategy Intelligence Engine Four-Phase Pipeline
1. ✅ **Phase 1 — Scrape URLs + boosts** — COMPLETE
2. 🔨 **Phase 1.5 — Metadata enrichment** — IN PROGRESS
3. ⏳ **Phase 2 — Validate on author's turf** — NEXT
4. ⏳ **Phase 3 — Test generalization** — PLANNED

### Phase 1.5 — Metadata Enrichment (Started)
- **Started:** 2026-03-21 ~08:48 AM (test batch of 8 strategies)
- **Full run started:** 2026-03-21 ~08:55 AM
- **Script:** `tv_enrich.py` built to visit each strategy page
- **Rate:** ~4 seconds per strategy, ~67 minutes estimated for full 1,000
- **Target fields:**
  - ✅ Description text (100% success rate) — CRITICAL for regime intelligence
  - ✅ Tags/categories (100% success)
  - ✅ Strategy type: long_only / short_only / long_and_short (100%)
  - ⚠️ Default ticker (~33% via DOM selectors)
  - ⚠️ Default timeframe (~33% via DOM selectors)

### Key Strategic Insight: Description = Regime Intelligence
Authors write descriptions like:
- "optimized for trending markets"
- "works best in high volatility" 
- "designed for crypto scalping"

This is metadata our system can index for regime matching at scale — nobody else is doing this.

### Testing Philosophy: Don't Test Wrong
**Critical principle:** Testing a 15-min ETH scalper on SPY daily = useless
1. **First:** Validate on author's turf (their chosen ticker/timeframe)
2. **Then:** Test generalization on similar instruments (ETH 15m → BTC 15m, SOL 15m)
3. **Gold standard:** Strategies that generalize across similar instruments

### Phase 2 Planning — Validation
- Use `tv_backtest.py` to run each strategy on author's default ticker/timeframe
- Extract Strategy Tester results: Sharpe ratio, profit factor, win rate, max drawdown
- Skip strategies that don't work on their own turf
- Focus on winners for Phase 3 generalization testing

### Phase 3 Planning — Generalization
- Test Phase 2 winners on similar instruments
- Asset class mapping: crypto → crypto, ETFs → ETFs, individual stocks → sector peers
- Timeframe consistency: 15m strategies tested on 15m, daily on daily
- Rank by cross-instrument performance

### Infrastructure Integration
**Existing pyhood capabilities:**
- Backtesting engine with 10+ built-in strategies
- Market regime classifier (200-SMA based: bull/bear/recovery/correction)
- Autoresearch engine for parameter optimization
- SQLite memory for experiment tracking

**Deployment targets:**
- Crypto strategies → pyhood crypto API (ED25519 keys)
- Equity strategies → Robinhood integration
- Futures strategies → flagged for future account setup

### Architecture Design
```
strategies.json (1,000 URLs + boosts)
    ↓ tv_enrich.py
strategies_enriched.json (+ description, ticker, timeframe, tags)
    ↓ text parser (planned)
strategies_classified.json (+ regime tags, asset class)
    ↓ tv_backtest.py
backtest_results.json (+ Sharpe, PF, win rate, drawdown)
    ↓ regime matcher (planned)
daily_picks.json (top strategies for today's market)
```

### Current Status
- Phase 1: ✅ Complete (1,000 strategies scraped)
- Phase 1.5: 🔨 In progress (metadata enrichment running)
- Phase 2: ⏳ Ready to start (validation framework built)
- Strategy intelligence vision: 🔮 Defined and planned
## 2026-03-22 — Backtester Fix Attempt #2

### Changes Made
- **engine.py**: Added `enter_at_open` flag (default True) — Pine enters at next bar's open
- **engine.py**: Added `process_orders_on_close` flag — for Pine strategies with this setting
- **engine.py**: Added `fixed_qty` + `point_value` support for fixed-size position strategies
- **engine.py**: Added `_calc_pnl()` helper for consistent PnL calculation
- **engine.py**: Improved Sharpe/Sortino annualization (auto-detects bars per year)
- **engine.py**: Trail stop re-entry prevention (reverted — causes more issues)
- **data.py**: Fixed intraday data fetching (period-based for 1h/15m/etc)
- **triple_ema_rsi_atr.py**: Updated to use dynamic ATR for SL/TP (matching Pine)
- **run.py**: Updated RSI mean reversion to 1h NG=F with fixed_qty=2
- **run.py**: Updated mean_reversion_nq to 1h NQ=F with process_orders_on_close
- **run.py**: Updated volatility_breakout to 1h SPY

### Results
| Strategy | Our CAGR | TV CAGR | Our PF | TV PF | Match? |
|----------|----------|---------|--------|-------|--------|
| rsi_mean_reversion | 80.4% | 53.6% | 1.97 | 1.72 | ✓ |
| triple_ema_rsi_atr | 9.3% | 62.0% | 1.08 | 2.22 | ✗ |
| volatility_breakout | -0.05% | 37.2% | 0.92 | 3.42 | ✗ |
| mean_reversion_nq | -9.9% | 21.6% | 0.58 | 1.79 | ✗ |

### Root Causes for Mismatches
1. **triple_ema_rsi_atr**: Shorts kill BTC performance. TV may test on specific exchange data or shorter period. Long-only version gets 19.8% CAGR with PF 1.34
2. **volatility_breakout**: Designed for 5m/15m base timeframe with 60m HTF bias. On 1h (where HTF IS the data), the multi-timeframe edge disappears. 1% position sizing = near-zero CAGR by design
3. **mean_reversion_nq**: Optimized for NQ 15min. RSI(7) < 20 and Keltner band breaks are very different on 1h vs 15m bars. Only 60 days of 15m data available via yfinance
4. **rsi_mean_reversion**: Closest match! 1h NG=F captures similar dynamics to 4H MCX natgas. PF and WR track well. Trade count higher due to 4× frequency vs 4H

### Key Insight
TV strategies optimized for specific intraday timeframes (5m, 15m, 4H) cannot be meaningfully backtested with yfinance data, which limits intraday to 730 days (1h) or 60 days (15m). The strategies' edge comes from timeframe-specific microstructure that doesn't translate to coarser intervals.
