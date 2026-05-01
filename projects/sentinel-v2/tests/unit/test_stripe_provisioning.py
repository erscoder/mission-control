"""Tests for per-app Stripe provisioning (S1 + S2 of the dynamic-Stripe plan).

Covers:
- ``_provision_stripe_for_draft`` orchestration in ``flows.sentinel_loop``:
  delegates to the pure helpers, refuses to inject empty webhook secret,
  refuses to inject without ``STRIPE_SECRET_KEY`` on the daemon, returns the
  expected payload shape.
- ``stripe_tool.provision_webhook_for_draft`` idempotency-by-replace: any
  prior endpoint matching ``metadata.sentinel_draft_id`` or matching the URL
  is deleted before a fresh one is created, so the live signing secret is
  always returned (Stripe never returns an existing endpoint's secret).
- ``stripe_tool.provision_product_for_draft`` reuse-by-metadata: a second
  call with the same draft_id returns the existing product without creating
  a duplicate.
"""
from __future__ import annotations

import json
import sys
import types
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Test infrastructure ─────────────────────────────────────────────────────

class _FakeStripeObj:
    """Minimal duck-typed Stripe response object used in tests."""

    def __init__(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)


@pytest.fixture
def fake_stripe(monkeypatch):
    """Inject a fake ``stripe`` module into ``sentinel_v2.tools.stripe_tool``.

    Tests configure attributes on the returned object before calling the
    helpers under test.
    """
    fake = types.SimpleNamespace()
    fake.api_key = None

    fake.Product = MagicMock()
    fake.Price = MagicMock()
    fake.WebhookEndpoint = MagicMock()

    monkeypatch.setitem(sys.modules, "stripe", fake)
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    return fake


# ── provision_product_for_draft ─────────────────────────────────────────────

class TestProvisionProductForDraft:
    def test_creates_new_product_when_none_exists(self, fake_stripe):
        from sentinel_v2.tools.stripe_tool import provision_product_for_draft

        fake_stripe.Product.search.return_value = _FakeStripeObj(data=[])
        fake_stripe.Product.create.return_value = _FakeStripeObj(id="prod_new")
        fake_stripe.Price.create.return_value = _FakeStripeObj(id="price_new")

        out = provision_product_for_draft(
            draft_id="draft_x",
            name="X",
            description="desc",
            prices=[{"amount_cents": 999, "currency": "usd", "interval": "month"}],
        )

        assert out == {"product_id": "prod_new", "price_ids": ["price_new"], "reused": False}
        fake_stripe.Product.create.assert_called_once()
        # Metadata must carry the draft id so future calls find it.
        kwargs = fake_stripe.Product.create.call_args.kwargs
        assert kwargs["metadata"] == {"sentinel_draft_id": "draft_x"}

    def test_reuses_existing_product_by_metadata(self, fake_stripe):
        from sentinel_v2.tools.stripe_tool import provision_product_for_draft

        existing_product = _FakeStripeObj(id="prod_existing")
        fake_stripe.Product.search.return_value = _FakeStripeObj(data=[existing_product])
        fake_stripe.Price.list.return_value = _FakeStripeObj(
            data=[_FakeStripeObj(id="price_existing")]
        )

        out = provision_product_for_draft(
            draft_id="draft_x",
            name="X",
            description="desc",
            prices=[{"amount_cents": 999, "currency": "usd", "interval": "month"}],
        )

        assert out == {
            "product_id": "prod_existing",
            "price_ids": ["price_existing"],
            "reused": True,
        }
        fake_stripe.Product.create.assert_not_called()
        fake_stripe.Price.create.assert_not_called()


# ── provision_webhook_for_draft (idempotency-by-replace) ────────────────────

class TestProvisionWebhookForDraft:
    def test_creates_fresh_when_no_prior_exists(self, fake_stripe):
        from sentinel_v2.tools.stripe_tool import provision_webhook_for_draft

        fake_stripe.WebhookEndpoint.list.return_value = _FakeStripeObj(
            auto_paging_iter=lambda: iter([])
        )
        fake_stripe.WebhookEndpoint.create.return_value = _FakeStripeObj(
            id="we_new", secret="whsec_fresh"
        )

        out = provision_webhook_for_draft(
            url="https://x-api.fly.dev/api/stripe/webhook",
            events=["checkout.session.completed"],
            draft_id="draft_x",
        )

        assert out == {
            "endpoint_id": "we_new",
            "secret": "whsec_fresh",
            "secret_was_rotated": False,
        }
        fake_stripe.WebhookEndpoint.delete.assert_not_called()

    def test_deletes_prior_with_same_draft_id_then_recreates(self, fake_stripe):
        from sentinel_v2.tools.stripe_tool import provision_webhook_for_draft

        prior = _FakeStripeObj(
            id="we_prior",
            url="https://OLD/api/stripe/webhook",
            metadata={"sentinel_draft_id": "draft_x"},
        )
        fake_stripe.WebhookEndpoint.list.return_value = _FakeStripeObj(
            auto_paging_iter=lambda: iter([prior])
        )
        fake_stripe.WebhookEndpoint.create.return_value = _FakeStripeObj(
            id="we_fresh", secret="whsec_rotated"
        )

        out = provision_webhook_for_draft(
            url="https://NEW/api/stripe/webhook",
            events=["checkout.session.completed"],
            draft_id="draft_x",
        )

        fake_stripe.WebhookEndpoint.delete.assert_called_once_with("we_prior")
        assert out == {
            "endpoint_id": "we_fresh",
            "secret": "whsec_rotated",
            "secret_was_rotated": True,
        }

    def test_deletes_prior_with_same_url_then_recreates(self, fake_stripe):
        """Even without metadata match, URL collision triggers replace.

        Catches the case where someone manually created a webhook in the
        Stripe dashboard at the same URL we want.
        """
        from sentinel_v2.tools.stripe_tool import provision_webhook_for_draft

        prior = _FakeStripeObj(
            id="we_manual",
            url="https://x-api.fly.dev/api/stripe/webhook",
            metadata={},
        )
        fake_stripe.WebhookEndpoint.list.return_value = _FakeStripeObj(
            auto_paging_iter=lambda: iter([prior])
        )
        fake_stripe.WebhookEndpoint.create.return_value = _FakeStripeObj(
            id="we_fresh", secret="whsec_fresh"
        )

        out = provision_webhook_for_draft(
            url="https://x-api.fly.dev/api/stripe/webhook",
            events=["checkout.session.completed"],
            draft_id="draft_y",
        )

        fake_stripe.WebhookEndpoint.delete.assert_called_once_with("we_manual")
        assert out["secret_was_rotated"] is True


# ── _provision_stripe_for_draft (orchestration in sentinel_loop) ────────────

class TestProvisionStripeForDraftOrchestration:
    @pytest.fixture
    def patched(self, monkeypatch):
        monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")

        product_mock = MagicMock(return_value={
            "product_id": "prod_x",
            "price_ids": ["price_x"],
            "reused": False,
        })
        webhook_mock = MagicMock(return_value={
            "endpoint_id": "we_x",
            "secret": "whsec_x",
            "secret_was_rotated": False,
        })
        secrets_setter = MagicMock(return_value=json.dumps({"set": ["STRIPE_SECRET_KEY"]}))

        monkeypatch.setattr(
            "sentinel_v2.tools.stripe_tool.provision_product_for_draft", product_mock
        )
        monkeypatch.setattr(
            "sentinel_v2.tools.stripe_tool.provision_webhook_for_draft", webhook_mock
        )
        monkeypatch.setattr(
            "sentinel_v2.tools.fly_tool.FlySecretsSetTool._run", secrets_setter
        )
        return product_mock, webhook_mock, secrets_setter

    def test_happy_path_returns_full_payload(self, patched):
        from sentinel_v2.flows.sentinel_loop import _provision_stripe_for_draft

        product_mock, webhook_mock, secrets_setter = patched

        out = _provision_stripe_for_draft(
            draft_id="draft_x",
            slug="myapp",
            backend_url="https://myapp-api.fly.dev",
            opportunity={"title": "MyApp", "tagline": "do stuff"},
            fly_app_name="myapp-api",
        )

        assert out["product_id"] == "prod_x"
        assert out["price_id"] == "price_x"
        assert out["webhook_endpoint_id"] == "we_x"
        assert out["secret_was_rotated"] is False
        # Webhook URL canonicalized to backend_url + /api/stripe/webhook.
        webhook_kwargs = webhook_mock.call_args.kwargs
        assert webhook_kwargs["url"] == "https://myapp-api.fly.dev/api/stripe/webhook"
        # Secrets injected into Fly include all four Stripe keys.
        secrets_payload = secrets_setter.call_args.kwargs["secrets"]
        assert "STRIPE_SECRET_KEY" in secrets_payload
        assert "STRIPE_WEBHOOK_SECRET" in secrets_payload
        assert "STRIPE_PRODUCT_ID" in secrets_payload
        assert "STRIPE_PRICE_ID" in secrets_payload
        assert secrets_payload["STRIPE_WEBHOOK_SECRET"] == "whsec_x"

    def test_refuses_when_webhook_secret_empty(self, patched, monkeypatch):
        """Closes audit blocker F-01 at the source.

        If Stripe somehow returns an empty signing secret (should never
        happen on a fresh create, but defense in depth), Sentinel must NOT
        inject an empty STRIPE_WEBHOOK_SECRET into Fly. That would let the
        deployed app's webhook handler accept any payload.
        """
        from sentinel_v2.flows.sentinel_loop import _provision_stripe_for_draft

        _, webhook_mock, _ = patched
        webhook_mock.return_value = {
            "endpoint_id": "we_empty",
            "secret": "",
            "secret_was_rotated": False,
        }

        with pytest.raises(RuntimeError, match="empty STRIPE_WEBHOOK_SECRET"):
            _provision_stripe_for_draft(
                draft_id="draft_x",
                slug="myapp",
                backend_url="https://myapp-api.fly.dev",
                opportunity={"title": "MyApp"},
                fly_app_name="myapp-api",
            )

    def test_refuses_without_daemon_stripe_secret_key(self, patched, monkeypatch):
        from sentinel_v2.flows.sentinel_loop import _provision_stripe_for_draft

        monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

        with pytest.raises(RuntimeError, match="STRIPE_SECRET_KEY not set"):
            _provision_stripe_for_draft(
                draft_id="draft_x",
                slug="myapp",
                backend_url="https://myapp-api.fly.dev",
                opportunity={"title": "MyApp"},
                fly_app_name="myapp-api",
            )

    def test_propagates_flyctl_failure(self, patched):
        from sentinel_v2.flows.sentinel_loop import _provision_stripe_for_draft

        _, _, secrets_setter = patched
        secrets_setter.return_value = "error rc=1: app not found"

        with pytest.raises(RuntimeError, match="flyctl secrets set failed"):
            _provision_stripe_for_draft(
                draft_id="draft_x",
                slug="myapp",
                backend_url="https://myapp-api.fly.dev",
                opportunity={"title": "MyApp"},
                fly_app_name="myapp-api",
            )

    def test_default_pricing_when_opportunity_lacks_it(self, patched):
        """No `pricing` key on the opportunity defaults to $19/month USD."""
        from sentinel_v2.flows.sentinel_loop import _provision_stripe_for_draft

        product_mock, _, _ = patched

        _provision_stripe_for_draft(
            draft_id="draft_x",
            slug="myapp",
            backend_url="https://myapp-api.fly.dev",
            opportunity={"title": "MyApp"},
            fly_app_name="myapp-api",
        )

        prices_arg = product_mock.call_args.kwargs["prices"]
        assert prices_arg == [{
            "amount_cents": 1900,
            "currency": "usd",
            "interval": "month",
            "nickname": "myapp-month",
        }]
