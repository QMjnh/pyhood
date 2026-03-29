# TradingView Strategy Scraper & Backtester

A powerful automation tool to scrape TradingView community strategies and backtest them against multiple tickers. Built with Python and Playwright for robust web automation.

## Features

🔍 **Strategy Scraper (Phase 1)**
- Scrapes TradingView's community strategies page (42+ pages)
- Supports Editors' picks tab scraping
- Collects title, author, boost count, URLs for each strategy
- Resume-safe: continues from where it left off
- Rate limiting and pagination handling
- Configurable filters (minimum boost count)

🔍 **Strategy Enricher (Phase 2)**
- Visits each strategy page and extracts rich metadata
- Full description text with regime information
- Default ticker, timeframe, and strategy type (long/short/both)
- Tags, Pine Script version, and publish date
- Performance metrics from Strategy Tester (when available)
- Resume-safe with progress tracking and error handling

📊 **Strategy Backtester (Phase 3)**  
- Automated backtesting on multiple tickers (SPY, QQQ, AAPL, TSLA, BTC-USD)
- Extracts comprehensive performance metrics:
  - Net Profit & Percentage
  - Maximum Drawdown
  - Sharpe/Sortino Ratios
  - Profit Factor, Win Rate
  - Total Trades & Average Trade
  - Buy & Hold comparison
- Resume functionality for long-running tests
- Optional TradingView login support

## Quick Start

### 1. Installation

```bash
cd ~/Projects/pyhood
.venv/bin/pip install playwright
.venv/bin/playwright install chromium
```

### 2. Scrape Strategies (Phase 1)

```bash
# Scrape all strategies (default: min 5 boosts)
cd scripts/tv_scraper
~/Projects/pyhood/.venv/bin/python tv_scrape.py

# Scrape first 5 pages only
~/Projects/pyhood/.venv/bin/python tv_scrape.py --pages 5

# Scrape editors' picks with minimum 50 boosts
~/Projects/pyhood/.venv/bin/python tv_scrape.py --editors-picks --min-boosts 50

# Custom rate limiting (3 seconds between pages)
~/Projects/pyhood/.venv/bin/python tv_scrape.py --delay 3.0
```

### 3. Enrich Strategies (Phase 2)

```bash
# Enrich all scraped strategies with metadata
~/Projects/pyhood/.venv/bin/python tv_enrich.py

# Test with small batch first
~/Projects/pyhood/.venv/bin/python tv_enrich.py --limit 10 --delay 4

# Resume from specific index
~/Projects/pyhood/.venv/bin/python tv_enrich.py --start-from 100 --limit 50
```

### 4. Backtest Strategies (Phase 3)

```bash
# Backtest all scraped strategies on default tickers
~/Projects/pyhood/.venv/bin/python tv_backtest.py

# Test on specific tickers
~/Projects/pyhood/.venv/bin/python tv_backtest.py --tickers "SPY,QQQ,NVDA"

# Limit to first 10 strategies
~/Projects/pyhood/.venv/bin/python tv_backtest.py --limit 10

# With TradingView login (for premium features)
~/Projects/pyhood/.venv/bin/python tv_backtest.py --login
```

## Configuration

Edit `config.py` to customize:

```python
# Rate limiting
DEFAULT_PAGE_DELAY = 2.5  # seconds between scrapes

# Filters  
DEFAULT_MIN_BOOSTS = 5    # minimum popularity threshold

# Default tickers for backtesting
DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "TSLA", "BTC-USD"]

# Browser settings
BROWSER_SETTINGS = {
    "headless": True,  # Set to False for debugging
    "viewport": {"width": 1920, "height": 1080},
    "timeout": 30000,
}
```

## Authentication

For login-required features, set environment variables:

```bash
export TV_USERNAME="your_username"
export TV_PASSWORD="your_password"
```

Or the script will prompt you when using `--login` flag.

## Output Files

```
data/
├── strategies.json      # Scraped strategy metadata
└── backtest_results.json   # Performance metrics for each strategy+ticker
```

### Strategy Data Structure

```json
{
  "title": "SuperTrend Strategy",
  "url": "https://www.tradingview.com/script/ABC123-SuperTrend/",
  "author": "johndoe",
  "boost_count": 245,
  "type_label": "Strategy",
  "script_url": "https://www.tradingview.com/script/ABC123-SuperTrend/",
  "scraped_at": "2024-03-20T16:22:00"
}
```

### Backtest Results Structure

```json
{
  "strategy_url": "https://www.tradingview.com/script/ABC123-SuperTrend/",
  "strategy_title": "SuperTrend Strategy",
  "ticker": "SPY",
  "success": true,
  "tested_at": "2024-03-20T16:25:00",
  "metrics": {
    "net_profit": 12500.50,
    "net_profit_percent": 0.125,
    "max_drawdown": -2500.00,
    "max_drawdown_percent": -0.08,
    "sharpe_ratio": 1.45,
    "sortino_ratio": 1.78,
    "profit_factor": 1.65,
    "total_trades": 127,
    "win_rate_percent": 0.58,
    "avg_trade": 98.43,
    "buy_hold_return": 0.095
  }
}
```

## Advanced Usage

### Resume Functionality

Both tools support automatic resume:
- **Scraper**: Skips already-scraped strategy URLs
- **Backtester**: Skips already-tested strategy+ticker combinations

### Error Handling

The backtester creates error records for failed tests:

```json
{
  "success": false,
  "error_message": "Could not find 'Add to Chart' button",
  "metrics": {}
}
```

### Monitoring Progress

Both tools provide detailed logging:

```
2024-03-20 16:22:15 - INFO - Starting TradingView strategy scraper
2024-03-20 16:22:16 - INFO - Loaded 150 existing strategies
2024-03-20 16:22:20 - INFO - Scraping page 1
2024-03-20 16:22:23 - INFO - Page 1: Found 42 strategies, 12 new
```

## Technical Notes

### Web Scraping Challenges

- **Rate Limiting**: Built-in delays prevent getting blocked
- **Dynamic Content**: Waits for JavaScript to load strategies
- **Pagination**: Handles TradingView's complex pagination system
- **Resume Safety**: Avoids re-scraping existing data

### Backtesting Automation

- **Headless Browser**: Uses Playwright for full browser automation
- **Chart Integration**: Simulates clicking "Add to Chart" buttons  
- **Symbol Switching**: Automatically changes tickers for each test
- **Metric Extraction**: Parses Strategy Tester performance data
- **Error Recovery**: Continues testing even if individual strategies fail

### Browser Automation Tips

For debugging, set `headless: False` in config.py to watch the browser:

```python
BROWSER_SETTINGS = {
    "headless": False,  # See browser in action
    "viewport": {"width": 1920, "height": 1080},
    "timeout": 30000,
}
```

## Troubleshooting

### Common Issues

**Scraper Issues:**
- **Empty results**: Check if TradingView changed their page structure
- **Rate limiting**: Increase `--delay` parameter
- **Pagination errors**: Run with fewer `--pages` first

**Backtester Issues:**
- **Login required**: Use `--login` flag for premium features
- **Button not found**: TradingView may have updated their UI
- **Metrics extraction fails**: Strategy might not have full backtest data

### Debug Mode

Run with Python directly to see full error traces:

```bash
cd ~/Projects/pyhood/scripts/tv_scraper
~/Projects/pyhood/.venv/bin/python -u tv_scrape.py --pages 1
```

## Performance Tips

### For Large-Scale Scraping

1. **Batch Processing**: Use `--pages` to scrape in chunks
2. **Rate Limiting**: Increase delays if getting blocked  
3. **Resume Runs**: Scripts automatically resume from interruptions
4. **Filter Early**: Use `--min-boosts` to focus on popular strategies

### For Backtesting

1. **Limit Tests**: Use `--limit` for initial testing
2. **Select Tickers**: Focus on specific markets with `--tickers`
3. **Monitor Progress**: Check `data/backtest_results.json` periodically
4. **Parallel Runs**: Run multiple instances on different strategy subsets

## Data Analysis

After collecting data, you can analyze results:

```python
import json
from collections import defaultdict

# Load results
with open('data/backtest_results.json') as f:
    results = json.load(f)

# Find top performers
profitable = [r for r in results if r['success'] and 
              r['metrics'].get('net_profit_percent', 0) > 0.1]

# Group by strategy
by_strategy = defaultdict(list)
for r in profitable:
    by_strategy[r['strategy_title']].append(r)

# Find consistently profitable strategies
consistent = {k: v for k, v in by_strategy.items() if len(v) >= 3}
```

## License

This tool is for educational and research purposes. Respect TradingView's terms of service and use appropriate rate limiting.

## Contributing

Found a bug or want to add features? The codebase is modular:

- `models.py`: Data structures
- `config.py`: Configuration settings  
- `tv_scrape.py`: Scraping logic
- `tv_backtest.py`: Backtesting automation

Each component can be extended independently.