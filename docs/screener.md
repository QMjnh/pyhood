# Stock Universe Screener

The `StockScreener` class screens for stocks matching fundamental criteria
against pre-built universes or custom ticker lists.

## Quick Start

```python
from pyhood.screener import StockScreener

screener = StockScreener('sp500')
results = screener.screen(
    filters={'pe_ratio': {'max': 20}, 'revenue_growth': {'min': 0.10}},
    max_results=10,
    sort_by='revenue_growth',
    sort_desc=True,
)
for r in results:
    print(f"{r['ticker']}: PE={r.get('pe_ratio')}, Growth={r.get('revenue_growth')}")
```

## Pre-built Universes

| Universe | Constant | Tickers |
|---|---|---|
| S&P 500 | `StockScreener.SP500` / `'sp500'` | ~100 top stocks by market cap |
| Nasdaq 100 | `StockScreener.NASDAQ100` / `'nasdaq100'` | ~90 top Nasdaq stocks |

```python
# Use a pre-built universe
screener = StockScreener('nasdaq100')

# Or pass custom tickers
screener = StockScreener(['AAPL', 'MSFT', 'GOOGL', 'AMZN'])
```

Ticker lists are hardcoded for reliability — no web scraping required.

## Filter Syntax

Filters use the same format as `FundamentalData.passes_filter`:

```python
filters = {
    'pe_ratio': {'max': 25},           # PE ratio ≤ 25
    'revenue_growth': {'min': 0.10},    # Revenue growth ≥ 10%
    'market_cap': {'min': 1e9},         # Market cap ≥ $1B
    'beta': {'min': 0.5, 'max': 2.0},   # Beta between 0.5 and 2.0
    'debt_to_equity': {'max': 100},     # D/E ratio ≤ 100
    'profit_margin': {'min': 0.10},     # Profit margin ≥ 10%
}
```

Missing data for a filter causes it to be skipped (not failed).

## Sorting

Sort results by any fundamental property:

```python
results = screener.screen(
    filters={'market_cap': {'min': 1e10}},
    sort_by='revenue_growth',
    sort_desc=True,   # Highest growth first
    max_results=20,
)
```

## Rate Limiting

The screener includes a 0.1 second delay between yfinance API calls to
avoid rate limiting (HTTP 429 errors). For large universes, screening
may take several minutes.
