"""Robinhood Crypto API v2 URL definitions."""

CRYPTO_BASE = "https://trading.robinhood.com"

# Account endpoints
CRYPTO_ACCOUNTS = f"{CRYPTO_BASE}/api/v2/crypto/trading/accounts/"

# Market data endpoints
CRYPTO_TRADING_PAIRS = f"{CRYPTO_BASE}/api/v2/crypto/trading/trading_pairs/"
CRYPTO_BEST_BID_ASK = f"{CRYPTO_BASE}/api/v2/crypto/marketdata/best_bid_ask/"
CRYPTO_ESTIMATED_PRICE = f"{CRYPTO_BASE}/api/v2/crypto/trading/estimated_price/"

# Holdings endpoints
CRYPTO_HOLDINGS = f"{CRYPTO_BASE}/api/v2/crypto/trading/holdings/"

# Order endpoints
CRYPTO_ORDERS = f"{CRYPTO_BASE}/api/v2/crypto/trading/orders/"
