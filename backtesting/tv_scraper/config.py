"""Configuration settings for TradingView scraper."""

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
STRATEGIES_FILE = DATA_DIR / "strategies.json"
BACKTEST_RESULTS_FILE = DATA_DIR / "backtest_results.json"

# TradingView URLs
TRADINGVIEW_BASE_URL = "https://www.tradingview.com"
STRATEGIES_URL = f"{TRADINGVIEW_BASE_URL}/scripts/?script_type=strategies"

# Scraping settings
DEFAULT_PAGE_DELAY = 2.5  # seconds between page loads
DEFAULT_MIN_BOOSTS = 5    # minimum boost count filter
MAX_RETRIES = 3          # max retry attempts for failed requests
REQUEST_TIMEOUT = 30000  # milliseconds

# Default tickers for backtesting
DEFAULT_TICKERS = ["SPY", "QQQ", "AAPL", "TSLA", "BTC-USD"]

# TradingView credentials (from environment variables)
TV_USERNAME = os.getenv("TV_USERNAME")
TV_PASSWORD = os.getenv("TV_PASSWORD")

# Browser settings
BROWSER_LAUNCH_SETTINGS = {
    "headless": True,
}

BROWSER_CONTEXT_SETTINGS = {
    "viewport": {"width": 1920, "height": 1080},
}

# Logging configuration
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"
LOG_LEVEL = "INFO"