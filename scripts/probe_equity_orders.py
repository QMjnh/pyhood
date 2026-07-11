"""Probe Robinhood equity order validation (form v7).

SAFETY DEFAULTS
- Uses qty=0, sub-minimum notional, or unmarketable limit prices.
- Never sends dollar_based_amount >= $1 unless --allow-live-dollar is set.
- Cancels immediately if Robinhood returns an order id.
- Does not place intentionally fillable market orders.

Usage (from repo root, with ROBINHOOD_USERNAME / ROBINHOOD_PASSWORD in env
or stock-dashboard/.env.local):

    python scripts/probe_equity_orders.py
    python scripts/probe_equity_orders.py --symbol PEP
    python scripts/probe_equity_orders.py --suite fields
    python scripts/probe_equity_orders.py --suite limits
    python scripts/probe_equity_orders.py --suite all

See docs/orders.md for the documented results of these probes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from pathlib import Path

# Optional: load dashboard env when probing from the monorepo checkout.
_env_candidates = [
    Path(__file__).resolve().parents[1] / ".env",
    Path(__file__).resolve().parents[2] / "stock-dashboard" / ".env.local",
]
try:
    from dotenv import load_dotenv

    for path in _env_candidates:
        if path.is_file():
            load_dotenv(path)
except ImportError:
    pass

import pyhood
from pyhood import urls


def _login():
    username = os.environ.get("ROBINHOOD_USERNAME")
    password = os.environ.get("ROBINHOOD_PASSWORD")
    if not username or not password:
        sys.exit("Set ROBINHOOD_USERNAME and ROBINHOOD_PASSWORD")
    session = pyhood.login(
        username=username, password=password, store_session=True, timeout=30
    )
    return pyhood.PyhoodClient(session=session)


def _cancel_if_created(client, data: dict) -> None:
    order_id = data.get("id") if isinstance(data, dict) else None
    if not order_id:
        return
    print(f"  ORDER CREATED {order_id} — cancelling")
    cancel_url = data.get("cancel") or f"{urls.ORDERS}{order_id}/cancel/"
    try:
        client._session.post(
            cancel_url, data={}, accept_codes=(200, 201, 400, 403)
        )
    except Exception as exc:
        print(f"  cancel error: {exc}")
    state = client._session.get(f"{urls.ORDERS}{order_id}/")
    print(
        "  after:",
        {
            "state": state.get("state"),
            "cumulative_quantity": state.get("cumulative_quantity"),
            "average_price": state.get("average_price"),
        },
    )


def _probe(client, label: str, payload: dict) -> None:
    body = {k: v for k, v in payload.items() if v is not None}
    data = client._session.post(
        urls.ORDERS, json_data=body, accept_codes=(400, 201, 200)
    )
    print(f"--- {label} ---")
    print("keys:", sorted(body.keys()))
    print(json.dumps(data, indent=2, default=str)[:1200])
    if isinstance(data, dict):
        _cancel_if_created(client, data)
    print()


def _base(account: str, instrument: str, symbol: str, **extra) -> dict:
    return {
        "account": account,
        "instrument": instrument,
        "symbol": symbol,
        "quantity": "0",
        "side": "buy",
        "type": "market",
        "time_in_force": "gfd",
        "trigger": "immediate",
        "extended_hours": False,
        "override_day_trade_checks": False,
        "override_dtbp_checks": False,
        "order_form_version": 7,
        "market_hours": "regular_hours",
        "ref_id": str(uuid.uuid4()),
        **extra,
    }


def suite_fields(client, symbol: str, account: str, instrument: str, ask: float) -> None:
    """Omit-required-field and qty=0 probes."""
    print("=== SUITE: fields (qty=0) ===\n")
    base = _base(account, instrument, symbol, price=str(ask))

    _probe(client, "market buy qty=0 no price", _base(account, instrument, symbol))
    _probe(client, "market buy qty=0 with price", {**base})
    _probe(
        client,
        "market sell qty=0 no price",
        _base(account, instrument, symbol, side="sell"),
    )

    for missing in (
        "account",
        "instrument",
        "symbol",
        "side",
        "type",
        "time_in_force",
        "trigger",
        "quantity",
    ):
        payload = {**base, "ref_id": str(uuid.uuid4())}
        payload.pop(missing, None)
        _probe(client, f"market buy omit {missing} (qty=0)", payload)

    # Limit without price
    payload = _base(
        account, instrument, symbol, type="limit", quantity="1", price="0.10"
    )
    payload.pop("price", None)
    payload["ref_id"] = str(uuid.uuid4())
    _probe(client, "limit buy omit price", payload)


def suite_safe(client, symbol: str, account: str, instrument: str, ask: float, bid: float) -> None:
    """Sub-minimum notional / decimal validation — should not create fillable orders."""
    print("=== SUITE: safe validation ===\n")
    tiny = "0.00001"

    def base(**extra):
        return _base(account, instrument, symbol, quantity=tiny, **extra)

    _probe(client, "market buy tiny no price", base())
    _probe(client, "market buy tiny with price", base(price=str(ask)))
    _probe(client, "market sell tiny no price", base(side="sell"))
    _probe(client, "market sell tiny with price", base(side="sell", price=str(bid)))
    _probe(client, "limit buy tiny (frac)", base(type="limit", price=str(ask)))
    _probe(
        client,
        "market buy dollars=0.01",
        base(
            price=str(ask),
            quantity="0",
            dollar_based_amount={"amount": "0.01000000", "currency_code": "USD"},
        ),
    )
    _probe(
        client,
        "market buy 9dp tiny qty",
        base(quantity="0.000010001", price=str(ask)),
    )


def suite_limits(client, symbol: str, account: str, instrument: str) -> None:
    """Fractional vs whole limit with unmarketable prices; cancel if created."""
    print("=== SUITE: unmarketable limits ===\n")
    frac = "0.02"
    _probe(
        client,
        "frac limit BUY @ 0.10",
        _base(
            account,
            instrument,
            symbol,
            quantity=frac,
            side="buy",
            type="limit",
            price="0.10",
        ),
    )
    _probe(
        client,
        "frac limit SELL @ 9999",
        _base(
            account,
            instrument,
            symbol,
            quantity=frac,
            side="sell",
            type="limit",
            price="9999.00",
        ),
    )
    _probe(
        client,
        "whole limit BUY qty=1 @ 0.10",
        _base(
            account,
            instrument,
            symbol,
            quantity="1",
            side="buy",
            type="limit",
            price="0.10",
        ),
    )


def suite_live_dollar(client, symbol: str, account: str, instrument: str, ask: float) -> None:
    """WARNING: creates a real dollar order then cancels. Opt-in only."""
    print("=== SUITE: live dollar (CREATE then CANCEL) ===\n")
    _probe(
        client,
        "market buy dollar_amount=$2 (will create+cancel)",
        _base(
            account,
            instrument,
            symbol,
            quantity="0",
            price=str(ask),
            dollar_based_amount={"amount": "2.00000000", "currency_code": "USD"},
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbol", default="PEP")
    parser.add_argument(
        "--suite",
        choices=("fields", "safe", "limits", "all"),
        default="all",
    )
    parser.add_argument(
        "--allow-live-dollar",
        action="store_true",
        help="Also run $2 dollar-order create+cancel probe",
    )
    args = parser.parse_args()

    client = _login()
    symbol = args.symbol.upper()
    quote = client.get_quote(symbol)
    account = client._get_account_url(None)
    instrument = client._get_instrument_url(symbol)
    ask = float(quote.ask or quote.price or quote.bid)
    bid = float(quote.bid or quote.price or quote.ask)

    print(
        json.dumps(
            {
                "symbol": symbol,
                "ask": ask,
                "bid": bid,
                "price": quote.price,
                "account": account,
                "instrument": instrument,
            },
            indent=2,
        )
    )
    print()

    suites = []
    if args.suite in ("fields", "all"):
        suites.append(("fields", lambda: suite_fields(client, symbol, account, instrument, ask)))
    if args.suite in ("safe", "all"):
        suites.append(("safe", lambda: suite_safe(client, symbol, account, instrument, ask, bid)))
    if args.suite in ("limits", "all"):
        suites.append(("limits", lambda: suite_limits(client, symbol, account, instrument)))

    for _name, fn in suites:
        fn()

    if args.allow_live_dollar:
        suite_live_dollar(client, symbol, account, instrument, ask)

    print("=== DONE ===")


if __name__ == "__main__":
    main()
