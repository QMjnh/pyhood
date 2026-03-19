"""Robinhood API URL definitions — single source of truth.

Batch limits (tested & verified):
- /fundamentals/ — 100 symbols max (hard count limit)
- /quotes/ — ~1,220 symbols max (URL length ~5,700 chars)
- /marketdata/options/ — ~17 instrument URLs max (URL length)
"""

BASE = "https://api.robinhood.com"
OAUTH = "https://api.robinhood.com/oauth2"

# Auth
LOGIN = f"{OAUTH}/token/"
LOGOUT = f"{OAUTH}/revoke_token/"

# Account
ACCOUNTS = f"{BASE}/accounts/"
POSITIONS = f"{BASE}/positions/"
PORTFOLIOS = f"{BASE}/portfolios/"

# Stocks — Market Data
QUOTES = f"{BASE}/quotes/"
INSTRUMENTS = f"{BASE}/instruments/"
FUNDAMENTALS = f"{BASE}/fundamentals/"
HISTORICALS = f"{BASE}/marketdata/historicals/"
RATINGS = f"{BASE}/midlands/ratings/"
NEWS = f"{BASE}/midlands/news/"
EARNINGS = f"{BASE}/marketdata/earnings/"

# Options
OPTIONS_BASE = f"{BASE}/options/"
OPTIONS_CHAINS = f"{OPTIONS_BASE}chains/"
OPTIONS_INSTRUMENTS = f"{OPTIONS_BASE}instruments/"
OPTIONS_ORDERS = f"{OPTIONS_BASE}orders/"
OPTIONS_POSITIONS = f"{OPTIONS_BASE}aggregate_positions/"
OPTIONS_MARKET_DATA = f"{BASE}/marketdata/options/"

# Orders
ORDERS = f"{BASE}/orders/"

# Markets
MARKETS = f"{BASE}/markets/"
MARKET_HOURS = f"{BASE}/markets/{{market}}/hours/{{date}}/"

# Discovery & Lists
MOVERS_SP500 = f"{BASE}/midlands/movers/sp500/"
TAGS = f"{BASE}/midlands/tags/tag/"
WATCHLISTS = f"{BASE}/midlands/lists/default/"

# Profile
USER = f"{BASE}/user/"
INVESTMENT_PROFILE = f"{BASE}/user/investment_profile/"

# Dividends
DIVIDENDS = f"{BASE}/dividends/"
