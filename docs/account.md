# Account & Positions

## All Accounts (Including IRA)

Robinhood's standard `/accounts/` endpoint only returns your individual brokerage account. IRA accounts (Traditional, Roth) are hidden behind a different endpoint. pyhood handles this automatically.

```python
accounts = client.get_all_accounts()

for acct in accounts:
    print(f"{acct.account_number} | {acct.account_type} | Cash: ${acct.cash:.2f}")
```

This uses Robinhood's bonfire endpoint internally to discover all linked accounts, including retirement accounts that don't appear in the standard API.

## Buying Power

```python
power = client.get_buying_power()
print(f"Buying power: ${power:,.2f}")
```

### IRA Buying Power

Pass `account_number` to check buying power for a specific account:

```python
bp = client.get_buying_power(account_number="YOUR_IRA_ACCOUNT")
print(f"IRA buying power: ${bp:,.2f}")
```

## Positions

Get all current stock positions:

```python
positions = client.get_positions()

for pos in positions:
    print(
        f"{pos.symbol:>6} | "
        f"Qty: {pos.quantity:.0f} | "
        f"Avg: ${pos.average_cost:.2f} | "
        f"Now: ${pos.current_price:.2f} | "
        f"P/L: ${pos.unrealized_pl:+.2f} ({pos.unrealized_pl_pct:+.1f}%)"
    )
```

### Position Fields

| Field | Type | Description |
|-------|------|-------------|
| `symbol` | `str` | Ticker symbol |
| `quantity` | `float` | Number of shares |
| `average_cost` | `float` | Average purchase price |
| `current_price` | `float` | Current market price |
| `equity` | `float` | Current value (quantity × price) |
| `unrealized_pl` | `float` | Unrealized profit/loss in dollars |
| `unrealized_pl_pct` | `float` | Unrealized P/L as percentage |
| `instrument_type` | `str` | `"stock"` or `"option"` |

### Include Zero Positions

By default, only non-zero positions are returned:

```python
# Include closed positions
all_positions = client.get_positions(nonzero=False)
```

## IRA / Retirement Accounts

pyhood supports trading in Robinhood IRA accounts (Traditional and Roth). Most order methods accept an `account_number` parameter to target a specific account.

### Account Discovery

```python
accounts = client.get_all_accounts()
ira = [a for a in accounts if "ira" in a.account_type.lower()]
```

### Trading in an IRA

Pass `account_number` to any order method:

```python
# Buy stock in IRA
order = client.buy_stock(
    symbol="AAPL", quantity=10, price=180.00,
    account_number="YOUR_IRA_ACCOUNT",
)

# Buy options in IRA
order = client.buy_option(
    symbol="NKE", strike=55.0, expiration="2026-04-02",
    option_type="call", quantity=3, price=1.60,
    account_number="YOUR_IRA_ACCOUNT",
)
```

### IRA Limitations

- **Cash account only** — no margin, no day trading
- **Options: Level 2 max** — long calls, long puts, covered calls, cash-secured puts
- **No spreads** — multi-leg strategies are not available in IRA accounts
- If `account_number` is omitted, orders default to your individual brokerage account
