# Fundamental Data Integration

Pyhood provides fundamental data integration via the `FundamentalData` class,
allowing you to screen stocks by financial ratios.

## FundamentalData Class

```python
from pyhood.fundamentals import FundamentalData

fd = FundamentalData('AAPL')

# Access individual ratios
print(fd.pe_ratio)         # Trailing P/E ratio
print(fd.revenue_growth)   # Revenue growth (decimal, e.g. 0.15 = 15%)
print(fd.market_cap)       # Market capitalization in dollars
print(fd.sector)           # e.g. 'Technology'

# Get all available data as a dict
summary = fd.summary()
# {'ticker': 'AAPL', 'pe_ratio': 28.5, 'market_cap': 2800000000000, ...}
```

Data is fetched lazily from yfinance on first access and cached for the
lifetime of the object.

## Available Properties

| Property | yfinance Key | Description |
|---|---|---|
| `pe_ratio` | trailingPE | Trailing price-to-earnings ratio |
| `forward_pe` | forwardPE | Forward P/E based on analyst estimates |
| `pb_ratio` | priceToBook | Price-to-book ratio |
| `debt_to_equity` | debtToEquity | Total debt / total equity |
| `revenue_growth` | revenueGrowth | YoY revenue growth (decimal) |
| `profit_margin` | profitMargins | Net profit margin (decimal) |
| `market_cap` | marketCap | Market capitalisation in USD |
| `beta` | beta | Beta coefficient vs market |
| `dividend_yield` | dividendYield | Annual dividend yield (decimal) |
| `sector` | sector | GICS sector name |
| `industry` | industry | Industry classification |
| `insider_buy_pct` | heldPercentInsiders | % held by insiders |
| `institutional_pct` | heldPercentInstitutions | % held by institutions |
| `short_ratio` | shortRatio | Days to cover short interest |
| `earnings_growth` | earningsGrowth | YoY earnings growth (decimal) |
| `current_ratio` | currentRatio | Current assets / current liabilities |
| `free_cash_flow` | freeCashflow | Free cash flow in USD |

All properties return `None` if the data is not available from yfinance.

## Fundamental Filtering

Check whether a stock passes a set of criteria:

```python
fd = FundamentalData('AAPL')
passes = fd.passes_filter({
    'pe_ratio': {'max': 30},
    'revenue_growth': {'min': 0.05},
    'market_cap': {'min': 100_000_000_000},
    'beta': {'min': 0.5, 'max': 2.0},
})
```

Each key is a property name. The value is a dict with `'min'` and/or `'max'`.
If data for a property is missing (None), that filter is skipped (not failed).

