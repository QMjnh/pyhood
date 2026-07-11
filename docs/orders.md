# Stock Orders

pyhood places equity orders via `POST https://api.robinhood.com/orders/` using
**order form version 7** (JSON body). Field rules below were verified with live
Robinhood validation probes (2026-07-11). Endpoints may change without notice.

## Client API

```python
# Market (share qty)
client.buy_stock("PEP", 0.02)
client.sell_stock("PEP", 0.02)

# Limit (whole shares only)
client.buy_stock("AAPL", 1, price=150.0)
client.sell_stock("AAPL", 1, price=200.0)

# Dollar-based fractional market buy (quantity ignored; RH derives shares)
client.buy_stock("PEP", quantity=0, dollar_amount=2.0)
```

`price=None` → market order. `price` set → limit order.

## Always sent

| Field | Value |
|-------|--------|
| `order_form_version` | `7` |
| `market_hours` | `regular_hours` or `extended_hours` |
| `ref_id` | UUID |
| Content-Type | `application/json` |

Quantity is floored to **8 decimal places** before submit.

## Required fields by order shape

### Core (all equity orders)

| Field | Required |
|-------|----------|
| `account` | yes |
| `instrument` | yes |
| `symbol` | yes |
| `side` | yes (`buy` / `sell`) |
| `type` | yes (`market` / `limit`) |
| `time_in_force` | yes |
| `quantity` | yes (`> 0`) |
| `trigger` | no (defaults if omitted) |

### Matrix

| Qty | Side | Type | Extra required | Notes |
|-----|------|------|----------------|-------|
| Frac | Buy | Market | — | Price optional |
| Frac | Sell | Market | — | Price optional |
| Frac | Buy | Limit | — | **Rejected** by RH |
| Frac | Sell | Limit | — | **Rejected** by RH |
| Frac | Buy | Market (dollars) | `dollar_based_amount` (≥ `$1`); `quantity`=`"0"` | Price set from quote |
| Whole | Buy/Sell | Market | — | Price optional under form v7 |
| Whole | Buy/Sell | Limit | `price` | Whole shares only |

### Limit-specific

Omit `price` on `type=limit` → `Limit order requested, but no price provided.`

Fractional `quantity` on limit → `Limit order quantity cannot include fractional shares.`

### Dollar-based market buys

```json
"dollar_based_amount": {
  "amount": "2.00000000",
  "currency_code": "USD"
}
```

- Minimum **$1**.
- When present, Robinhood derives share quantity from dollars; **submit `quantity` as `"0"`**.
- Sending a fractional share estimate with `dollar_based_amount` is rejected:
  `Order quantity cannot include fractional shares.`
- pyhood forces `quantity` to `"0"` and sets a reference `price` from the quote.

## What pyhood enforces locally

1. Floor `quantity` to 8 decimals (share-qty orders).
2. Reject `quantity <= 0` unless `dollar_amount` is set (then payload qty is `"0"`).
3. Reject **fractional limit** orders before calling Robinhood.
4. Reject `dollar_amount <= 0` (and RH enforces ≥ `$1`).
5. Always submit form v7 JSON with `market_hours`.

## Common Robinhood errors

| Error | Meaning |
|-------|---------|
| `Ensure that there are no more than 8 decimal places.` | Quantity too precise |
| `Ensure this value is greater than 0.` | Quantity ≤ 0 |
| `Order quantity cannot include fractional shares.` | Frac qty with dollar-based (use qty `0`) |
| `Limit order quantity cannot include fractional shares.` | Frac + limit |
| `Limit order requested, but no price provided.` | Limit without `price` |
| `Market buy order requested, but no price provided.` | Legacy form (not v7) |
| `Dollar-based orders must be at least $1.` | Dollar notional too small |
| `Buy/Sell order cannot have notional less than $0.01.` | Tiny share qty |

## Related

- Re-run probes: [`scripts/probe_equity_orders.py`](../scripts/probe_equity_orders.py) ([scripts/README.md](../scripts/README.md))
- Upstream notes: [sanko/Robinhood Order.md](https://github.com/sanko/Robinhood/blob/master/Order.md) (pre-fractional; older form)
- Community client: [robin_stocks](https://github.com/jmfernandes/robin_stocks)
