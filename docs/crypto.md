# Crypto Trading (Official API)

pyhood wraps Robinhood's **official, documented** Crypto Trading API. This is separate from the unofficial API used for stocks and options.

## Key Differences

| | Stocks/Options | Crypto |
|---|---|---|
| **API** | Unofficial (reverse-engineered) | Official (documented) |
| **Auth** | OAuth + device approval | ED25519 API keys |
| **Base URL** | `api.robinhood.com` | `trading.robinhood.com` |
| **Rate limits** | Unknown | 100 req/min, 300 burst |
| **Human needed** | First login + expired refresh | Never |

## Setup

### 1. Generate API Keys

Go to [robinhood.com/account/crypto](https://robinhood.com/account/crypto) on web classic and create credentials. You'll get:

- **API key** (starts with `rh-api-`)
- **Public key** (base64, you upload to Robinhood)
- **Private key** (base64, you keep secret)

You can also generate a keypair with pyhood:

```python
from pyhood.crypto.auth import generate_keypair

private_key, public_key = generate_keypair()
print(f"Private: {private_key}")  # Save securely
print(f"Public:  {public_key}")   # Upload to Robinhood
```

### 2. Create a Client

```python
from pyhood.crypto import CryptoClient

crypto = CryptoClient(
    api_key="rh-api-your-key-here",
    private_key_base64="your-private-key-base64",
)
```

!!! warning "Never share your private key"
    Store it in an environment variable or encrypted file. Never commit it to version control.

## Market Data

### Best Bid/Ask

```python
quotes = crypto.get_best_bid_ask("BTC-USD", "ETH-USD")

for quote in quotes:
    print(f"{quote.symbol}: bid=${quote.bid:.2f} ask=${quote.ask:.2f}")
```

### Estimated Price

Get the expected execution price including fees:

```python
price = crypto.get_estimated_price("BTC-USD", "buy", 0.001)

print(f"Bid: ${price.bid_price:.2f}")
print(f"Ask: ${price.ask_price:.2f}")
print(f"Fee: ${price.fee:.2f}")
```

### Trading Pairs

```python
pairs = crypto.get_trading_pairs("BTC-USD", "ETH-USD")

for pair in pairs:
    print(f"{pair.symbol}: min={pair.min_order_size} max={pair.max_order_size}")
```

## Account & Holdings

```python
# Get account info
account = crypto.get_account()
print(f"Account: {account.account_number}")
print(f"Buying power: ${account.buying_power:.2f}")
print(f"Fee tier: {account.fee_tier}")

# Get holdings
holdings = crypto.get_holdings(account.account_number)
for h in holdings:
    print(f"{h.asset_code}: {h.quantity} (available: {h.available_quantity})")
```

## Placing Orders

### Market Order (by quantity)

```python
order = crypto.place_order(
    account_number=account.account_number,
    side="buy",
    order_type="market",
    symbol="BTC-USD",
    order_config={"asset_quantity": "0.001"},
)
print(f"Order {order.order_id}: {order.status}")
```

### Market Order (by dollar amount)

```python
order = crypto.place_order(
    account_number=account.account_number,
    side="buy",
    order_type="market",
    symbol="BTC-USD",
    order_config={"notional_amount": "100.00"},  # Buy $100 of BTC
)
```

### Limit Order

```python
order = crypto.place_order(
    account_number=account.account_number,
    side="buy",
    order_type="limit",
    symbol="BTC-USD",
    order_config={
        "asset_quantity": "0.001",
        "limit_price": "60000.00",
    },
)
```

## Managing Orders

```python
# Get all orders
orders = crypto.get_orders(account.account_number)
for order in orders:
    print(f"{order.symbol} {order.side} {order.status}")

# Get specific order
order = crypto.get_order(account.account_number, "order-id-here")

# Cancel an order
crypto.cancel_order("order-id-here")
```

## Authentication Details

Every request is signed with ED25519:

```
message = f"{api_key}{timestamp}{path}{method}{body}"
signature = ed25519_sign(message, private_key)
```

Three headers are sent:

| Header | Value |
|--------|-------|
| `x-api-key` | Your API key |
| `x-signature` | Base64-encoded ED25519 signature |
| `x-timestamp` | Unix timestamp (valid for 30 seconds) |

pyhood handles all of this automatically.

## Rate Limits

The official API has documented rate limits:

- **100 requests per minute** per account
- **300 requests per minute** burst capacity
- Token bucket with automatic refill

pyhood includes a built-in token bucket rate limiter that tracks your usage and prevents you from hitting limits.
