# TradingView Strategy Enrichment Scraper

This enrichment scraper visits each strategy's page and extracts rich metadata for building a strategy intelligence engine.

## What it does

The `tv_enrich.py` script takes the strategies from `data/strategies.json` and enriches each one with:

1. **Description text** - Full author description containing regime information
2. **Default ticker** - Symbol shown on the strategy's chart  
3. **Default timeframe** - Timeframe displayed (15m, 1H, 1D, etc.)
4. **Strategy type** - long_only, short_only, or long_and_short
5. **Performance metrics** - Net profit, trades, win rate, etc. from Strategy Tester
6. **Tags/categories** - Author-applied tags and extracted keywords
7. **Pine Script version** - v5, v4, etc.
8. **Publish date** - When the strategy was published

## Usage

```bash
# Basic usage - enrich all strategies
python tv_enrich.py

# Test with a small batch
python tv_enrich.py --limit 5 --delay 4

# Resume from a specific index
python tv_enrich.py --start-from 100 --limit 50

# Debug mode (visible browser)
python tv_enrich.py --limit 1 --debug
```

## CLI Arguments

- `--limit N` - Maximum number of strategies to enrich
- `--delay SECONDS` - Delay between page loads (default: 3.0, respect rate limits)
- `--start-from INDEX` - Start from a specific strategy index (for resuming)
- `--debug` - Run with visible browser for debugging

## Resume Safety

The script automatically:
- Loads existing enriched data from `data/strategies_enriched.json`
- Skips strategies already enriched
- Saves progress every 10 strategies
- Handles errors gracefully and continues

## Output

Enriched data is saved to `data/strategies_enriched.json` with this format:

```json
{
  "title": "Strategy Name",
  "author": "author_name",
  "boost_count": 123,
  "script_url": "https://...",
  "scraped_at": "2026-03-20T...",
  "enriched_at": "2026-03-21T...",
  "description": "Full strategy description with regime info...",
  "default_ticker": "BTCUSDT",
  "default_timeframe": "15m", 
  "strategy_type": "long_and_short",
  "tags": ["trend-following", "crypto"],
  "pine_version": "v5",
  "publish_date": "2025-06-15",
  "performance": {
    "net_profit_pct": 125.5,
    "total_trades": 340,
    "win_rate": 58.2,
    "profit_factor": 1.65,
    "max_drawdown_pct": -15.3,
    "sharpe_ratio": 1.42
  }
}
```

## Rate Limiting

- Default 3-second delay between requests
- Respects TradingView's servers
- Use `--delay` to adjust if needed
- TradingView may rate limit aggressive scraping

## Logging

All activity is logged to `data/enrich.log`:
- Progress updates every strategy
- Error details for debugging
- Summary statistics

## Performance Notes

- Each strategy takes ~3-10 seconds to process
- 1000 strategies ≈ 1-3 hours total
- Performance metrics may require login (often returns null)
- Some fields depend on page structure (TradingView changes CSS frequently)

## Success Indicators

The enricher successfully extracts:
- ✅ Description text (critical for regime analysis)
- ✅ Strategy type (long/short/both) 
- ✅ Tags and keywords
- ✅ Some tickers and timeframes
- ⚠️ Performance metrics (hit/miss, depends on page structure)
- ⚠️ Pine version (hit/miss)
- ⚠️ Publish date (hit/miss)

The description text is the most valuable field - it contains the author's insights about market regimes, volatility preferences, and strategy behavior.