"""Tests for stripe_tool.py — idempotent product + webhook creation (mocked SDK)."""
from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from sentinel_v2.tools.stripe_tool import (
    StripeCreateProductTool,
    StripeCreateWebhookTool,
    StripeDeleteProductTool,
    StripeListProductsTool,
)


@pytest.fixture(autouse=True)
def _stripe_key(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")


def _mock_stripe_module(**overrides):
    """Create a stripe-module-ish MagicMock usable as _client() return value."""
    m = MagicMock(name="stripe")
    m.Product.search.return_value = SimpleNamespace(data=[])
    m.Product.create.return_value = SimpleNamespace(id="prod_AAA")
    m.Product.list.return_value = SimpleNamespace(data=[])
    m.Price.list.return_value = SimpleNamespace(data=[])
    m.Price.create.return_value = SimpleNamespace(id="price_XXX")
    m.WebhookEndpoint.list.return_value.auto_paging_iter.return_value = []
    m.WebhookEndpoint.create.return_value = SimpleNamespace(
        id="we_abc", secret="whsec_zzz"
    )
    for k, v in overrides.items():
        setattr(m, k, v)
    return m


# ── StripeCreateProductTool ──────────────────────────────────────────────────


def test_create_product_creates_when_not_exists():
    mock_stripe = _mock_stripe_module()
    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        tool = StripeCreateProductTool()
        result = tool._run(
            draft_id="draft_c0_test",
            name="My SaaS",
            description="Does the thing",
            prices=[{"amount_cents": 999, "currency": "usd", "interval": "month"}],
        )
    data = json.loads(result)
    assert data["product_id"] == "prod_AAA"
    assert data["reused"] is False
    assert data["price_ids"] == ["price_XXX"]
    # Product was created with the right metadata
    mock_stripe.Product.create.assert_called_once()
    _, kwargs = mock_stripe.Product.create.call_args
    assert kwargs["metadata"]["sentinel_draft_id"] == "draft_c0_test"


def test_create_product_reuses_when_exists():
    existing_product = SimpleNamespace(id="prod_EXISTING")
    existing_prices = SimpleNamespace(
        data=[SimpleNamespace(id="price_E1"), SimpleNamespace(id="price_E2")]
    )
    mock_stripe = _mock_stripe_module()
    mock_stripe.Product.search.return_value = SimpleNamespace(data=[existing_product])
    mock_stripe.Price.list.return_value = existing_prices

    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        tool = StripeCreateProductTool()
        result = tool._run(
            draft_id="draft_c0_reuse",
            name="Reused",
            description="x",
            prices=[{"amount_cents": 1, "currency": "usd", "interval": "month"}],
        )
    data = json.loads(result)
    assert data["reused"] is True
    assert data["product_id"] == "prod_EXISTING"
    assert set(data["price_ids"]) == {"price_E1", "price_E2"}
    mock_stripe.Product.create.assert_not_called()


def test_create_product_one_time_price_no_recurring():
    mock_stripe = _mock_stripe_module()
    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        StripeCreateProductTool()._run(
            draft_id="d1",
            name="One-time",
            description="x",
            prices=[{"amount_cents": 500, "currency": "usd", "interval": "one_time"}],
        )
    _, kwargs = mock_stripe.Price.create.call_args
    assert "recurring" not in kwargs


# ── StripeCreateWebhookTool ──────────────────────────────────────────────────


def test_create_webhook_creates_when_no_existing():
    mock_stripe = _mock_stripe_module()
    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        result = StripeCreateWebhookTool()._run(
            url="https://app.fly.dev/api/stripe/webhook",
            events=["checkout.session.completed"],
            draft_id="draft_c0_hook",
        )
    data = json.loads(result)
    assert data["endpoint_id"] == "we_abc"
    assert data["secret"] == "whsec_zzz"
    assert data["reused"] is False


def test_create_webhook_reuses_existing_by_url():
    existing = SimpleNamespace(id="we_existing", url="https://app.fly.dev/api/stripe/webhook")
    mock_stripe = _mock_stripe_module()
    mock_stripe.WebhookEndpoint.list.return_value.auto_paging_iter.return_value = [existing]

    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        result = StripeCreateWebhookTool()._run(
            url="https://app.fly.dev/api/stripe/webhook",
            events=["checkout.session.completed"],
            draft_id="draft_c0_dup",
        )
    data = json.loads(result)
    assert data["reused"] is True
    assert data["endpoint_id"] == "we_existing"
    assert data["secret"] is None
    mock_stripe.WebhookEndpoint.create.assert_not_called()


# ── StripeListProductsTool ───────────────────────────────────────────────────


def test_list_products_by_draft_id():
    p = SimpleNamespace(id="prod_1", name="Foo")
    mock_stripe = _mock_stripe_module()
    mock_stripe.Product.search.return_value = SimpleNamespace(data=[p])
    price = SimpleNamespace(
        id="price_1", unit_amount=999, currency="usd",
        recurring=SimpleNamespace(interval="month"),
    )
    mock_stripe.Price.list.return_value = SimpleNamespace(data=[price])

    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        result = StripeListProductsTool()._run(draft_id="draft_c0_test")

    data = json.loads(result)
    assert len(data) == 1
    assert data[0]["id"] == "prod_1"
    assert data[0]["prices"][0]["interval"] == "month"


# ── StripeDeleteProductTool ──────────────────────────────────────────────────


def test_delete_product_archives():
    mock_stripe = _mock_stripe_module()
    mock_stripe.Product.modify.return_value = SimpleNamespace(id="prod_X", active=False)
    with patch("sentinel_v2.tools.stripe_tool._client", return_value=mock_stripe):
        result = StripeDeleteProductTool()._run(product_id="prod_X")
    data = json.loads(result)
    assert data["active"] is False
    mock_stripe.Product.modify.assert_called_once_with("prod_X", active=False)


# ── Missing env var ──────────────────────────────────────────────────────────


def test_missing_env_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    from sentinel_v2.tools.stripe_tool import _client
    with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY"):
        _client()
