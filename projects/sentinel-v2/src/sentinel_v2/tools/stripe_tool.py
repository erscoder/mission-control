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


class StripeCreateProductTool(BaseTool):
    name: str = "stripe_create_product"
    description: str = (
        "Create a Stripe product with one or more prices. Idempotent: if a product "
        "with the same draft_id already exists, returns its ids instead of creating "
        "duplicates. Returns {product_id, price_ids}."
    )
    args_schema: Type[BaseModel] = CreateProductInput

    def _run(self, draft_id: str, name: str, description: str, prices: list[dict]) -> str:
        stripe = _client()

        # Idempotency: search products by metadata
        existing = stripe.Product.search(query=f"metadata['sentinel_draft_id']:'{draft_id}'")
        if existing.data:
            product = existing.data[0]
            product_prices = stripe.Price.list(product=product.id, active=True, limit=100)
            return json.dumps({
                "product_id": product.id,
                "price_ids": [p.id for p in product_prices.data],
                "reused": True,
            })

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

        return json.dumps({
            "product_id": product.id,
            "price_ids": price_ids,
            "reused": False,
        })


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


class StripeCreateWebhookTool(BaseTool):
    name: str = "stripe_create_webhook"
    description: str = (
        "Create (or reuse) a Stripe webhook endpoint. Idempotent by (url, draft_id). "
        "Returns {endpoint_id, secret} — the secret is only shown at creation, so it "
        "must be stored immediately (e.g. by setting STRIPE_WEBHOOK_SECRET on the backend)."
    )
    args_schema: Type[BaseModel] = CreateWebhookInput

    def _run(self, url: str, events: list[str], draft_id: str) -> str:
        stripe = _client()
        # Look for existing endpoint with matching url
        for ep in stripe.WebhookEndpoint.list(limit=100).auto_paging_iter():
            if ep.url == url:
                # Reuse; secret is not retrievable — caller must have saved it or rotate
                return json.dumps({
                    "endpoint_id": ep.id,
                    "secret": None,
                    "reused": True,
                    "note": "existing endpoint; secret unavailable — rotate if lost",
                })

        ep = stripe.WebhookEndpoint.create(
            url=url,
            enabled_events=events,
            metadata={"sentinel_draft_id": draft_id},
        )
        return json.dumps({
            "endpoint_id": ep.id,
            "secret": ep.secret,
            "reused": False,
        })


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
