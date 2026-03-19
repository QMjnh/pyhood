# Robinhood API Endpoints Reference

Robinhood does not publish official API documentation for stocks/options. This reference is based on reverse engineering and live testing. Endpoints may change without notice.

Base URL: `https://api.robinhood.com`

## Batch Limits

| Endpoint | Max Batch Size | Limiting Factor |
|----------|---------------|-----------------|
| `/fundamentals/` | **100 symbols** | Hard count limit |
| `/quotes/` | **~1,220 symbols** | URL length (~5,700 chars) |
| `/marketdata/options/` | **17 instruments** | URL length |

Use 100 for fundamentals and 1,000 for quotes as safe defaults.

## Market Data

### Quotes

```
GET /quotes/?symbols=AAPL,MSFT,TSLA
```

Returns: `last_trade_price`, `previous_close`, `bid_price`, `ask_price`, `last_trade_volume`, `updated_at`

Batch: ✅ Up to ~1,220 symbols (comma-separated)

### Fundamentals

```
GET /fundamentals/?symbols=AAPL,MSFT,TSLA
GET /fundamentals/AAPL/
```

Returns: `high_52_weeks`, `low_52_weeks`, `market_cap`, `pb_ratio`, `pe_ratio`, `shares_outstanding`, `float`, `volume`, `average_volume`, `average_volume_2_weeks`, `average_volume_30_days`, `sector`, `industry`, `description`, `ceo`, `num_employees`, `year_founded`, `dividend_yield`

Batch: ✅ Up to 100 symbols

### Historical Data

```
GET /marketdata/historicals/?symbols=AAPL&interval=day&span=year&bounds=regular
```

| Param | Values |
|-------|--------|
| `interval` | `5minute`, `10minute`, `hour`, `day`, `week` |
| `span` | `day`, `week`, `month`, `3month`, `year`, `5year` |
| `bounds` | `regular`, `extended`, `trading` |

Returns: OHLCV candles with `begins_at`, `open_price`, `close_price`, `high_price`, `low_price`, `volume`

Batch: ❌ Single symbol only

### Earnings

```
GET /marketdata/earnings/?symbol=AAPL
```

Returns: Earnings dates, EPS estimates, EPS actuals, timing (am/pm)

Batch: ❌ Single symbol

### Ratings

```
GET /midlands/ratings/?symbol=AAPL
```

Returns: Analyst ratings and price targets

Batch: ❌ Single symbol

### News

```
GET /midlands/news/?symbol=AAPL
```

Returns: Recent news articles for the symbol

Batch: ❌ Single symbol

## Discovery & Lists

### S&P 500 Movers

```
GET /midlands/movers/sp500/?direction=up
GET /midlands/movers/sp500/?direction=down
```

Returns: Top 10 daily movers with `symbol`, `price_movement`, `description`

### Sector / Category Lists

```
GET /midlands/tags/tag/{tag-name}/
```

Returns: `instruments` (list of instrument URLs), `name`, `description`

| Tag | Stocks | Description |
|-----|--------|-------------|
| `most-popular-under-25` | ~24 | Retail-popular cheap stocks |
| `upcoming-earnings` | ~70 | Stocks with earnings in next 2 weeks |
| `new-on-robinhood` | ~172 | Recently added stocks |
| `etf` | ~500 | ETFs |
| `technology` | ~500 | Tech stocks |
| `finance` | ~500 | Financial stocks |
| `energy` | ~386 | Energy stocks |
| `healthcare` | ~212 | Healthcare stocks |

## Instruments

### List All Instruments

```
GET /instruments/?active_instruments_only=true
```

Returns: Paginated list of all instruments. Each has `symbol`, `name`, `tradeable`, `state`, `type`, `tradable_chain_id`, `sector`, `industry`

Paginated: ✅ (100 per page, ~50 pages for all stocks)

### Search

```
GET /instruments/?query=apple
```

Returns: Instruments matching the search query

## Options

### Chains

```
GET /options/chains/?equity_instrument_ids={instrument_id}
```

Returns: `expiration_dates`, `trade_value_multiplier`, `underlying_instruments`

Note: Use `equity_instrument_ids` param, not `symbol`. Get the instrument ID from `/instruments/?symbol=AAPL` first.

### Options Instruments

```
GET /options/instruments/?chain_symbol=AAPL&expiration_dates=2026-04-17&state=active&type=call
```

Returns: Paginated list of option contracts with `strike_price`, `expiration_date`, `type`, `url`, `id`

### Options Market Data

```
GET /marketdata/options/?instruments={url1},{url2},...
```

Returns: `adjusted_mark_price`, `bid_price`, `ask_price`, `implied_volatility`, `delta`, `gamma`, `theta`, `vega`, `volume`, `open_interest`

**Important:** Pass full instrument URLs, not IDs. Max ~17 per request.

## Orders

### Stock Orders

```
GET /orders/
POST /orders/
```

### Options Orders

```
GET /options/orders/
POST /options/orders/
```

## Account

### Positions

```
GET /positions/?nonzero=true
```

Returns: Current stock positions with `quantity`, `average_buy_price`, `instrument`

### Options Positions

```
GET /options/aggregate_positions/
```

Returns: Current option positions

### Portfolios

```
GET /portfolios/
```

Returns: Portfolio value, equity, market value

### Accounts

```
GET /accounts/
```

Returns: Account details, buying power, cash balances

### Watchlists

```
GET /midlands/lists/default/
```

Returns: Stocks on your default watchlist

### Dividends

```
GET /dividends/
```

Returns: Dividend history

## Profile

### User Profile

```
GET /user/
```

Returns: User ID, basic account info

### Investment Profile

```
GET /user/investment_profile/
```

Returns: `total_net_worth`, `annual_income`, risk tolerance, experience level

## Authentication

### Login

```
POST /oauth2/token/
```

See [Authentication docs](authentication.md) for details.

### Logout

```
POST /oauth2/revoke_token/
```

## Markets

### Market Hours

```
GET /markets/
GET /markets/{market}/hours/{date}/
```

Returns: Market open/close times, whether market is open today
