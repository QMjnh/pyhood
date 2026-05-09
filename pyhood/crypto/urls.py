"""Robinhood Crypto API URL definitions."""

CRYPTO_BASE = "https://trading.robinhood.com"

# Account endpoints
CRYPTO_ACCOUNTS_V1 = f"{CRYPTO_BASE}/api/v1/crypto/trading/accounts/"
CRYPTO_ACCOUNTS_V2 = f"{CRYPTO_BASE}/api/v2/crypto/trading/accounts/"
CRYPTO_ACCOUNTS = CRYPTO_ACCOUNTS_V2

# Market data endpoints
CRYPTO_TRADING_PAIRS_V1 = f"{CRYPTO_BASE}/api/v1/crypto/trading/trading_pairs/"
CRYPTO_TRADING_PAIRS_V2 = f"{CRYPTO_BASE}/api/v2/crypto/trading/trading_pairs/"
CRYPTO_TRADING_PAIRS = CRYPTO_TRADING_PAIRS_V2
CRYPTO_BEST_BID_ASK_V1 = f"{CRYPTO_BASE}/api/v1/crypto/marketdata/best_bid_ask/"
CRYPTO_BEST_BID_ASK_V2 = f"{CRYPTO_BASE}/api/v2/crypto/marketdata/best_bid_ask/"
CRYPTO_BEST_BID_ASK = CRYPTO_BEST_BID_ASK_V2
CRYPTO_ESTIMATED_PRICE_V1 = f"{CRYPTO_BASE}/api/v1/crypto/marketdata/estimated_price/"
CRYPTO_ESTIMATED_PRICE_V2 = f"{CRYPTO_BASE}/api/v2/crypto/trading/estimated_price/"
CRYPTO_ESTIMATED_PRICE = CRYPTO_ESTIMATED_PRICE_V2

# Holdings endpoints
CRYPTO_HOLDINGS_V1 = f"{CRYPTO_BASE}/api/v1/crypto/trading/holdings/"
CRYPTO_HOLDINGS_V2 = f"{CRYPTO_BASE}/api/v2/crypto/trading/holdings/"
CRYPTO_HOLDINGS = CRYPTO_HOLDINGS_V2

# Historicals endpoints
CRYPTO_HISTORICALS = f"{CRYPTO_BASE}/api/v2/crypto/marketdata/historicals/"

# Order endpoints
CRYPTO_ORDERS_V1 = f"{CRYPTO_BASE}/api/v1/crypto/trading/orders/"
CRYPTO_ORDERS_V2 = f"{CRYPTO_BASE}/api/v2/crypto/trading/orders/"
CRYPTO_ORDERS = CRYPTO_ORDERS_V2
