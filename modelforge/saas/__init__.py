"""SaaS shell — multi-tenant auth, tenant isolation, audit log, billing.

Designed for the no-spend Phase A path: every component runs on free
tiers (Supabase Postgres + Auth, Cloudflare Pages, Stripe transactional)
or local SQLite. Add real keys via env vars; no deploy required to
develop and test.

Reach the productized SaaS gate (D5 7.5+) requires only:
1. ``SUPABASE_URL`` + ``SUPABASE_ANON_KEY`` (free tier)
2. ``STRIPE_SECRET_KEY`` + ``STRIPE_WEBHOOK_SECRET`` (free transactional)
3. Cloudflare Pages domain + DNS pointed to a Render/Fly free worker

The code below is what runs once those env vars are set; it's also
fully exercisable with the dev bypass for tests + local builds.

Public API:

    from modelforge.saas import (
        AuthContext, get_current_user, require_auth,
        Tenant, TenantStore,
        BillingEvent, handle_stripe_webhook,
    )
"""
from __future__ import annotations

from modelforge.saas.auth import AuthContext, get_current_user, require_auth
from modelforge.saas.tenant import Tenant, TenantStore
from modelforge.saas.billing import BillingEvent, handle_stripe_webhook

__all__ = [
    "AuthContext",
    "get_current_user",
    "require_auth",
    "Tenant",
    "TenantStore",
    "BillingEvent",
    "handle_stripe_webhook",
]
