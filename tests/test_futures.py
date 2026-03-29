"""Tests for futures trading — contracts, quotes, orders, P&L."""

import pytest
import responses

from pyhood import urls
from pyhood.client import PyhoodClient
from pyhood.exceptions import APIError, SymbolNotFoundError
from pyhood.http import Session
from pyhood.models import FuturesContract, FuturesOrder, FuturesPnL, FuturesQuote

BASE = "https://api.robinhood.com"


@pytest.fixture
def client():
    """Create a client with a mock authenticated session."""
    session = Session(timeout=5)
    session.set_auth("Bearer", "test-token")
    return PyhoodClient(session=session)


# ── Contract tests ───────────────────────────────────────────────────


class TestGetFuturesContract:
    @responses.activate
    def test_single_contract(self, client):
        responses.add(
            responses.GET,
            urls.futures_contract_url("ESH26"),
            json={
                "id": "abc-123",
                "symbol": "ESH26",
                "simple_name": "E-mini S&P 500 March 2026",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "50",
                "state": "active",
                "underlying_symbol": "ES",
                "asset_class": "equity_index",
            },
            status=200,
        )

        contract = client.get_futures_contract("ESH26")
        assert isinstance(contract, FuturesContract)
        assert contract.symbol == "ESH26"
        assert contract.name == "E-mini S&P 500 March 2026"
        assert contract.contract_id == "abc-123"
        assert contract.expiration == "2026-03-20"
        assert contract.tick_size == 0.25
        assert contract.multiplier == 50.0
        assert contract.underlying == "ES"

    @responses.activate
    def test_contract_case_insensitive(self, client):
        responses.add(
            responses.GET,
            urls.futures_contract_url("ESH26"),
            json={
                "id": "abc-123",
                "symbol": "ESH26",
                "simple_name": "E-mini S&P 500",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "50",
            },
            status=200,
        )
        contract = client.get_futures_contract("esh26")
        assert contract.symbol == "ESH26"

    @responses.activate
    def test_contract_not_found(self, client):
        responses.add(
            responses.GET,
            urls.futures_contract_url("FAKE99"),
            json={},
            status=200,
        )
        with pytest.raises(SymbolNotFoundError):
            client.get_futures_contract("FAKE99")


class TestGetFuturesContracts:
    @responses.activate
    def test_batch_contracts(self, client):
        responses.add(
            responses.GET,
            urls.futures_contract_url("ESH26"),
            json={
                "id": "abc-123",
                "symbol": "ESH26",
                "simple_name": "E-mini S&P 500",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "50",
            },
            status=200,
        )
        responses.add(
            responses.GET,
            urls.futures_contract_url("NQH26"),
            json={
                "id": "def-456",
                "symbol": "NQH26",
                "simple_name": "E-mini Nasdaq-100",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "20",
            },
            status=200,
        )

        results = client.get_futures_contracts(["ESH26", "NQH26"])
        assert len(results) == 2
        assert "ESH26" in results
        assert "NQH26" in results
        assert results["ESH26"].multiplier == 50.0
        assert results["NQH26"].multiplier == 20.0

    @responses.activate
    def test_batch_partial_failure(self, client):
        responses.add(
            responses.GET,
            urls.futures_contract_url("ESH26"),
            json={
                "id": "abc-123",
                "symbol": "ESH26",
                "simple_name": "E-mini S&P 500",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "50",
            },
            status=200,
        )
        responses.add(
            responses.GET,
            urls.futures_contract_url("FAKE99"),
            json={},
            status=200,
        )

        results = client.get_futures_contracts(["ESH26", "FAKE99"])
        assert len(results) == 1
        assert "ESH26" in results


# ── Quote tests ──────────────────────────────────────────────────────


class TestGetFuturesQuote:
    @responses.activate
    def test_single_quote(self, client):
        # Mock contract lookup
        responses.add(
            responses.GET,
            urls.futures_contract_url("ESH26"),
            json={
                "id": "abc-123",
                "symbol": "ESH26",
                "simple_name": "E-mini S&P 500",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "50",
            },
            status=200,
        )
        # Mock quote lookup
        responses.add(
            responses.GET,
            urls.FUTURES_QUOTES,
            json={
                "results": [{
                    "last_trade_price": "5750.25",
                    "bid_price": "5750.00",
                    "ask_price": "5750.50",
                    "high_price": "5780.00",
                    "low_price": "5720.00",
                    "previous_close": "5740.00",
                    "volume": "1500000",
                    "open_interest": "2500000",
                }],
            },
            status=200,
        )

        quote = client.get_futures_quote("ESH26")
        assert isinstance(quote, FuturesQuote)
        assert quote.symbol == "ESH26"
        assert quote.last_price == 5750.25
        assert quote.bid == 5750.00
        assert quote.ask == 5750.50
        assert quote.high == 5780.00
        assert quote.volume == 1500000
        assert quote.contract_id == "abc-123"

    @responses.activate
    def test_quote_no_results(self, client):
        responses.add(
            responses.GET,
            urls.futures_contract_url("ESH26"),
            json={
                "id": "abc-123",
                "symbol": "ESH26",
                "simple_name": "E-mini S&P 500",
                "expiration_date": "2026-03-20",
                "tick_size": "0.25",
                "multiplier": "50",
            },
            status=200,
        )
        responses.add(
            responses.GET,
            urls.FUTURES_QUOTES,
            json={"results": []},
            status=200,
        )

        with pytest.raises(SymbolNotFoundError):
            client.get_futures_quote("ESH26")


# ── Account tests ────────────────────────────────────────────────────


class TestGetFuturesAccountId:
    @responses.activate
    def test_discover_account(self, client):
        responses.add(
            responses.GET,
            urls.FUTURES_ACCOUNTS,
            json={
                "results": [
                    {"id": "stock-001", "accountType": "MARGIN"},
                    {"id": "futures-001", "accountType": "FUTURES"},
                ],
            },
            status=200,
        )

        account_id = client.get_futures_account_id()
        assert account_id == "futures-001"

    @responses.activate
    def test_no_futures_account(self, client):
        responses.add(
            responses.GET,
            urls.FUTURES_ACCOUNTS,
            json={
                "results": [
                    {"id": "stock-001", "accountType": "MARGIN"},
                ],
            },
            status=200,
        )

        with pytest.raises(APIError, match="No futures account found"):
            client.get_futures_account_id()


# ── Order tests ──────────────────────────────────────────────────────


SAMPLE_ORDER = {
    "id": "order-001",
    "symbol": "ESH26",
    "side": "buy",
    "type": "limit",
    "quantity": "2",
    "price": "5750.00",
    "state": "filled",
    "created_at": "2026-03-15T10:30:00Z",
    "closing_strategy": "CLOSING",
    "legs": [{
        "executions": [{
            "settlement": {
                "realized_pnl": "1250.00",
            },
        }],
    }],
}

SAMPLE_OPENING_ORDER = {
    "id": "order-002",
    "symbol": "ESH26",
    "side": "buy",
    "type": "market",
    "quantity": "1",
    "price": "5700.00",
    "state": "filled",
    "created_at": "2026-03-14T09:00:00Z",
    "opening_strategy": "OPENING",
    "legs": [{
        "executions": [{
            "settlement": {
                "realized_pnl": "0",
            },
        }],
    }],
}


class TestGetFuturesOrders:
    @responses.activate
    def test_fetch_all_orders(self, client):
        # Mock account discovery
        responses.add(
            responses.GET,
            urls.FUTURES_ACCOUNTS,
            json={
                "results": [{"id": "futures-001", "accountType": "FUTURES"}],
            },
            status=200,
        )
        # Mock orders
        responses.add(
            responses.GET,
            urls.futures_orders_url("futures-001"),
            json={
                "results": [SAMPLE_ORDER, SAMPLE_OPENING_ORDER],
                "next": None,
            },
            status=200,
        )

        orders = client.get_futures_orders()
        assert len(orders) == 2
        assert isinstance(orders[0], FuturesOrder)
        assert orders[0].order_id == "order-001"
        assert orders[0].symbol == "ESH26"
        assert orders[0].status == "filled"
        assert orders[0].realized_pnl == 1250.0

    @responses.activate
    def test_fetch_with_pagination(self, client):
        page2_url = urls.futures_orders_url("futures-001") + "?cursor=page2"
        # Mock account
        responses.add(
            responses.GET,
            urls.FUTURES_ACCOUNTS,
            json={
                "results": [{"id": "futures-001", "accountType": "FUTURES"}],
            },
            status=200,
        )
        # Page 1
        responses.add(
            responses.GET,
            urls.futures_orders_url("futures-001"),
            json={
                "results": [SAMPLE_ORDER],
                "next": page2_url,
            },
            status=200,
        )
        # Page 2
        responses.add(
            responses.GET,
            page2_url,
            json={
                "results": [SAMPLE_OPENING_ORDER],
                "next": None,
            },
            status=200,
        )

        orders = client.get_futures_orders()
        assert len(orders) == 2

    @responses.activate
    def test_fetch_with_explicit_account(self, client):
        responses.add(
            responses.GET,
            urls.futures_orders_url("my-account"),
            json={
                "results": [SAMPLE_ORDER],
                "next": None,
            },
            status=200,
        )

        orders = client.get_futures_orders(account_id="my-account")
        assert len(orders) == 1
        assert orders[0].account_id == "my-account"


class TestGetFilledFuturesOrders:
    @responses.activate
    def test_filters_to_filled_only(self, client):
        pending_order = {
            "id": "order-003",
            "symbol": "ESH26",
            "side": "buy",
            "type": "limit",
            "quantity": "1",
            "price": "5600.00",
            "state": "pending",
            "created_at": "2026-03-16T10:00:00Z",
            "legs": [],
        }
        responses.add(
            responses.GET,
            urls.FUTURES_ACCOUNTS,
            json={
                "results": [{"id": "futures-001", "accountType": "FUTURES"}],
            },
            status=200,
        )
        responses.add(
            responses.GET,
            urls.futures_orders_url("futures-001"),
            json={
                "results": [SAMPLE_ORDER, pending_order],
                "next": None,
            },
            status=200,
        )

        orders = client.get_filled_futures_orders()
        assert len(orders) == 1
        assert orders[0].status == "filled"


# ── P&L tests ────────────────────────────────────────────────────────


class TestExtractFuturesPnl:
    def test_extract_pnl_from_closing_order(self):
        pnl = PyhoodClient._extract_futures_pnl(SAMPLE_ORDER)
        assert isinstance(pnl, FuturesPnL)
        assert pnl.realized_pnl == 1250.0
        assert pnl.direction == "CLOSING"
        assert pnl.order_id == "order-001"

    def test_extract_pnl_from_opening_order(self):
        pnl = PyhoodClient._extract_futures_pnl(SAMPLE_OPENING_ORDER)
        assert isinstance(pnl, FuturesPnL)
        assert pnl.realized_pnl == 0.0
        assert pnl.direction == "OPENING"

    def test_extract_pnl_empty_legs(self):
        order = {"id": "x", "legs": []}
        pnl = PyhoodClient._extract_futures_pnl(order)
        assert pnl is None

    def test_extract_pnl_no_legs(self):
        order = {"id": "x"}
        pnl = PyhoodClient._extract_futures_pnl(order)
        assert pnl is None

    def test_extract_pnl_no_executions(self):
        order = {"id": "x", "legs": [{"executions": []}]}
        pnl = PyhoodClient._extract_futures_pnl(order)
        assert pnl is None


class TestCalculateFuturesPnl:
    def test_aggregate_pnl_closing_only(self, client):
        orders = [
            FuturesOrder(
                order_id="1", symbol="ESH26", side="buy", order_type="limit",
                quantity=1, price=5750.0, status="filled",
                direction="CLOSING", realized_pnl=500.0,
            ),
            FuturesOrder(
                order_id="2", symbol="ESH26", side="sell", order_type="limit",
                quantity=1, price=5700.0, status="filled",
                direction="OPENING", realized_pnl=0.0,
            ),
            FuturesOrder(
                order_id="3", symbol="NQH26", side="sell", order_type="limit",
                quantity=2, price=20000.0, status="filled",
                direction="CLOSING", realized_pnl=750.0,
            ),
        ]
        total = client.calculate_futures_pnl(orders=orders)
        assert total == 1250.0

    def test_aggregate_pnl_no_closing_orders(self, client):
        orders = [
            FuturesOrder(
                order_id="1", symbol="ESH26", side="buy", order_type="limit",
                quantity=1, price=5750.0, status="filled",
                direction="OPENING", realized_pnl=0.0,
            ),
        ]
        total = client.calculate_futures_pnl(orders=orders)
        assert total == 0.0

    def test_aggregate_pnl_empty(self, client):
        total = client.calculate_futures_pnl(orders=[])
        assert total == 0.0
