"""Stripe webhook handler — transactional billing only (no fixed cost).

The MVP uses Stripe Checkout for two flows:
1. Per-seat subscription — $99/mo per active seat in a tenant
2. Per-workbook usage — $5 charged when a tenant builds a paid-tier workbook

Stripe is free to set up and only charges fees on actual transactions
(2.9% + 30¢ per US, 1.5% + €0.25 per EU). Aligns with the no-spend
constraint: we pay Stripe nothing until we collect from a customer.

This module ONLY handles inbound webhook events. Checkout / portal
URL generation lives in the FastAPI routes layer.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class BillingEvent:
    """Normalized representation of a Stripe webhook event."""
    event_type: str             # e.g. "checkout.session.completed"
    stripe_event_id: str
    tenant_id: Optional[str]    # extracted from metadata.tenant_id
    user_id: Optional[str]      # extracted from metadata.user_id
    amount_cents: Optional[int]
    currency: Optional[str]
    plan: Optional[str]         # "seat_monthly" / "workbook_oneoff"
    raw: dict


class WebhookSignatureError(RuntimeError):
    """Raised when Stripe-Signature header doesn't match payload."""


def _verify_stripe_signature(
    payload: bytes,
    signature_header: str,
    secret: str,
    tolerance_seconds: int = 300,
) -> None:
    """Verify Stripe-Signature per https://stripe.com/docs/webhooks/signatures.

    Header format: ``t=<timestamp>,v1=<sig>[,v0=<sig>]``.
    """
    if not signature_header:
        raise WebhookSignatureError("Missing Stripe-Signature header")
    parts = {}
    for kv in signature_header.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            parts.setdefault(k.strip(), []).append(v.strip())
    timestamp = parts.get("t", [None])[0]
    sigs = parts.get("v1", [])
    if not timestamp or not sigs:
        raise WebhookSignatureError("Stripe-Signature missing t= or v1=")
    try:
        ts_int = int(timestamp)
    except ValueError:
        raise WebhookSignatureError("Non-numeric timestamp")
    if abs(time.time() - ts_int) > tolerance_seconds:
        raise WebhookSignatureError(
            f"Timestamp outside tolerance ({tolerance_seconds}s)"
        )
    signed = f"{timestamp}.".encode("utf-8") + payload
    expected = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise WebhookSignatureError("Stripe-Signature mismatch")


def _normalize(payload: dict) -> BillingEvent:
    """Translate a Stripe webhook payload into a BillingEvent."""
    event_type = payload.get("type", "")
    obj = (payload.get("data", {}) or {}).get("object", {}) or {}
    md = obj.get("metadata") or {}
    return BillingEvent(
        event_type=event_type,
        stripe_event_id=payload.get("id", ""),
        tenant_id=md.get("tenant_id") or md.get("modelforge_tenant_id"),
        user_id=md.get("user_id") or md.get("modelforge_user_id"),
        amount_cents=obj.get("amount_total") or obj.get("amount"),
        currency=obj.get("currency"),
        plan=md.get("plan"),
        raw=payload,
    )


def handle_stripe_webhook(
    payload: bytes,
    signature_header: str,
    *,
    secret: Optional[str] = None,
    skip_signature: bool = False,
) -> BillingEvent:
    """Verify + parse a Stripe webhook payload.

    Use ``skip_signature=True`` only in tests. In production, the
    secret must match Stripe's webhook signing secret (env
    ``STRIPE_WEBHOOK_SECRET``).
    """
    if not skip_signature:
        actual_secret = secret or os.environ.get("STRIPE_WEBHOOK_SECRET")
        if not actual_secret:
            raise WebhookSignatureError(
                "STRIPE_WEBHOOK_SECRET not configured"
            )
        _verify_stripe_signature(payload, signature_header, actual_secret)
    try:
        data = json.loads(payload)
    except json.JSONDecodeError as e:
        raise WebhookSignatureError(f"Invalid JSON payload: {e}")
    return _normalize(data)


__all__ = [
    "BillingEvent",
    "WebhookSignatureError",
    "handle_stripe_webhook",
]
