"""Stripe tools for CrewAI agents.

Wrap the Stripe Python SDK in CrewAI ``BaseTool`` subclasses so the backend
agent can create products/prices/webhook endpoints for the app it's shipping.
All tools are idempotent — if an object already exists with matching metadata,
it is reused instead of duplicated.

Requires ``STRIPE_SECRET_KEY`` in env.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Type

from crewai.tools import BaseTool
from pydantic import BaseModel, Field

log = logging.getLogger("sentinel_v2.tools.stripe")


def _client():
    import stripe
    api_key = os.environ.get("STRIPE_SECRET_KEY")
    if not api_key:
        raise RuntimeError("STRIPE_SECRET_KEY not set")
    stripe.api_key = api_key
    return stripe


# ── StripeCreateProductTool ──────────────────────────────────────────────────


class _PriceSpec(BaseModel):
    amount_cents: int = Field(..., description="Price in cents (e.g. 999 = $9.99)")
    currency: str = Field(default="usd", description="ISO 4217 currency")
    interval: str = Field(default="month", description="month | year | one_time")
    nickname: str | None = Field(default=None, description="Internal label, e.g. 'pro-monthly'")


class CreateProductInput(BaseModel):
    draft_id: str = Field(..., description="Sentinel draft id — used as metadata for idempotency")
    name: str = Field(..., description="Product name shown on Stripe receipts/portal")
    description: str = Field(..., description="Product description")
    prices: list[_PriceSpec] = Field(..., description="One or more prices to attach")


def provision_product_for_draft(
    draft_id: str,
    name: str,
    description: str,
    prices: list[dict | _PriceSpec],
) -> dict:
    """Idempotent product+prices provisioning by ``metadata.sentinel_draft_id``.

    Returns: {product_id, price_ids, reused}.
    """
    stripe = _client()
    existing = stripe.Product.search(
        query=f"metadata['sentinel_draft_id']:'{draft_id}'"
    )
    if existing.data:
        product = existing.data[0]
        product_prices = stripe.Price.list(product=product.id, active=True, limit=100)
        return {
            "product_id": product.id,
            "price_ids": [p.id for p in product_prices.data],
            "reused": True,
        }

    product = stripe.Product.create(
        name=name,
        description=description,
        metadata={"sentinel_draft_id": draft_id},
    )
    price_ids: list[str] = []
    for p in prices:
        spec = _PriceSpec(**p) if isinstance(p, dict) else p
        kwargs = {
            "product": product.id,
            "unit_amount": spec.amount_cents,
            "currency": spec.currency,
            "nickname": spec.nickname or None,
            "metadata": {"sentinel_draft_id": draft_id},
        }
        if spec.interval != "one_time":
            kwargs["recurring"] = {"interval": spec.interval}
        price = stripe.Price.create(**kwargs)
        price_ids.append(price.id)

    return {
        "product_id": product.id,
        "price_ids": price_ids,
        "reused": False,
    }


class StripeCreateProductTool(BaseTool):
    name: str = "stripe_create_product"
    description: str = (
        "Create a Stripe product with one or more prices. Idempotent: if a product "
        "with the same draft_id already exists, returns its ids instead of creating "
        "duplicates. Returns {product_id, price_ids}."
    )
    args_schema: Type[BaseModel] = CreateProductInput

    def _run(self, draft_id: str, name: str, description: str, prices: list[dict]) -> str:
        return json.dumps(provision_product_for_draft(draft_id, name, description, prices))


# ── StripeListProductsTool ───────────────────────────────────────────────────


class ListProductsInput(BaseModel):
    draft_id: str | None = Field(default=None, description="Filter by Sentinel draft id")


class StripeListProductsTool(BaseTool):
    name: str = "stripe_list_products"
    description: str = (
        "List Stripe products, optionally filtered by Sentinel draft_id. "
        "Returns a JSON array of {id, name, prices: [{id, unit_amount, currency, interval}]}."
    )
    args_schema: Type[BaseModel] = ListProductsInput

    def _run(self, draft_id: str | None = None) -> str:
        stripe = _client()
        if draft_id:
            products = stripe.Product.search(
                query=f"metadata['sentinel_draft_id']:'{draft_id}'"
            ).data
        else:
            products = stripe.Product.list(limit=50).data

        out: list[dict] = []
        for p in products:
            prices = stripe.Price.list(product=p.id, active=True, limit=50).data
            out.append({
                "id": p.id,
                "name": p.name,
                "prices": [
                    {
                        "id": pr.id,
                        "unit_amount": pr.unit_amount,
                        "currency": pr.currency,
                        "interval": getattr(getattr(pr, "recurring", None), "interval", None),
                    }
                    for pr in prices
                ],
            })
        return json.dumps(out)


# ── StripeCreateWebhookTool ──────────────────────────────────────────────────


class CreateWebhookInput(BaseModel):
    url: str = Field(..., description="Webhook endpoint URL, e.g. https://myapp.fly.dev/api/stripe/webhook")
    events: list[str] = Field(..., description="Stripe event names to subscribe to")
    draft_id: str = Field(..., description="Sentinel draft id — used for idempotency metadata")


def provision_webhook_for_draft(url: str, events: list[str], draft_id: str) -> dict:
    """Idempotent-by-replace webhook provisioning. Returns the live secret.

    Stripe never returns the signing secret of an existing endpoint. To make
    redeploys actually capture a usable secret, on retry we DELETE the prior
    endpoint (matched by ``metadata.sentinel_draft_id``) and create a fresh
    one. Any in-flight Stripe events against the deleted endpoint are queued
    by Stripe and retried against the new one (same backend URL, no traffic
    loss).

    Returns: {endpoint_id, secret, secret_was_rotated}.
    """
    stripe = _client()
    deleted: list[str] = []
    for ep in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
        prior = (getattr(ep, "metadata", None) or {}).get("sentinel_draft_id")
        if prior == draft_id or ep.url == url:
            try:
                stripe.WebhookEndpoint.delete(ep.id)
                deleted.append(ep.id)
            except Exception as e:  # noqa: BLE001 - best-effort cleanup
                log.warning("Could not delete prior webhook %s: %s", ep.id, e)
    fresh = stripe.WebhookEndpoint.create(
        url=url,
        enabled_events=events,
        metadata={"sentinel_draft_id": draft_id},
    )
    return {
        "endpoint_id": fresh.id,
        "secret": fresh.secret,
        "secret_was_rotated": bool(deleted),
    }


class StripeCreateWebhookTool(BaseTool):
    name: str = "stripe_create_webhook"
    description: str = (
        "Provision a Stripe webhook endpoint for a Sentinel draft. Idempotent "
        "by replacement: any prior endpoint matching the draft_id metadata or "
        "URL is deleted and recreated, so the live signing secret is always "
        "returned. Caller MUST persist the secret (e.g. set STRIPE_WEBHOOK_SECRET "
        "on the backend) before this call returns."
    )
    args_schema: Type[BaseModel] = CreateWebhookInput

    def _run(self, url: str, events: list[str], draft_id: str) -> str:
        return json.dumps(provision_webhook_for_draft(url, events, draft_id))


# ── StripeDeleteProductTool ─────────────────────────────────────────────────


class DeleteProductInput(BaseModel):
    product_id: str = Field(..., description="Stripe product id to archive")


class StripeDeleteProductTool(BaseTool):
    name: str = "stripe_delete_product"
    description: str = "Archive a Stripe product (sets active=false). Used for cleanup on retries."
    args_schema: Type[BaseModel] = DeleteProductInput

    def _run(self, product_id: str) -> str:
        stripe = _client()
        try:
            product = stripe.Product.modify(product_id, active=False)
            return json.dumps({"id": product.id, "active": product.active})
        except Exception as e:
            return f"error: {e}"
