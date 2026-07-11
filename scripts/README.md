# Scripts

Manual / investigative helpers. Not part of the installed package.

| Script | Purpose |
|--------|---------|
| `probe_equity_orders.py` | Live Robinhood validation probes for equity `POST /orders/` (form v7). Safe by default; cancels any created order ids. |

## probe_equity_orders.py

Documents field requirements for market/limit and fractional/whole orders.
Results are summarized in [docs/orders.md](../docs/orders.md).

```bash
# From the pyhood repo root, with credentials in the environment:
export ROBINHOOD_USERNAME=...
export ROBINHOOD_PASSWORD=...

python scripts/probe_equity_orders.py
python scripts/probe_equity_orders.py --suite safe
python scripts/probe_equity_orders.py --suite limits --symbol PEP

# Opt-in: actually create a $2 dollar-based order then cancel it
python scripts/probe_equity_orders.py --allow-live-dollar
```

If this checkout sits next to `stock-dashboard/`, the script will also load
`stock-dashboard/.env.local` when present.
