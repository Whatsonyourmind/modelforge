"""Tests for D5 SaaS shell (auth + tenant + billing)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from pathlib import Path

import pytest

from modelforge.saas import (
    AuthContext,
    BillingEvent,
    Tenant,
    TenantStore,
    handle_stripe_webhook,
    require_auth,
)
from modelforge.saas.auth import AuthError
from modelforge.saas.billing import WebhookSignatureError


# ── auth: dev bypass ─────────────────────────────────────────────────────


@pytest.fixture
def dev_bypass(monkeypatch):
    monkeypatch.setenv("MODELFORGE_AUTH_DEV_BYPASS", "1")


def test_dev_bypass_with_headers_returns_context(dev_bypass):
    ctx = require_auth({
        "X-User-Id": "u-123",
        "X-Tenant-Id": "t-456",
        "X-Email": "ops@firm.com",
    })
    assert ctx.user_id == "u-123"
    assert ctx.tenant_id == "t-456"
    assert ctx.email == "ops@firm.com"
    assert ctx.is_dev_bypass is True


def test_dev_bypass_missing_headers_raises(dev_bypass):
    with pytest.raises(AuthError):
        require_auth({"X-User-Id": "u-123"})  # missing tenant


def test_dev_bypass_lowercase_headers_work(dev_bypass):
    ctx = require_auth({"x-user-id": "u", "x-tenant-id": "t"})
    assert ctx.user_id == "u" and ctx.tenant_id == "t"


# ── auth: production JWT path ────────────────────────────────────────────


def _make_unsigned_jwt(payload: dict) -> str:
    header = base64.urlsafe_b64encode(b'{"alg":"HS256","typ":"JWT"}').rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).rstrip(b"=").decode()
    return f"{header}.{body}.fakesig"


def test_no_auth_header_raises(monkeypatch):
    monkeypatch.delenv("MODELFORGE_AUTH_DEV_BYPASS", raising=False)
    monkeypatch.setenv("SUPABASE_JWT_SECRET", "secret")
    with pytest.raises(AuthError):
        require_auth({})


def test_jwt_without_secret_raises(monkeypatch):
    monkeypatch.delenv("MODELFORGE_AUTH_DEV_BYPASS", raising=False)
    monkeypatch.delenv("SUPABASE_JWT_SECRET", raising=False)
    token = _make_unsigned_jwt({"sub": "u1", "user_metadata": {"tenant_id": "t1"}})
    with pytest.raises(AuthError):
        require_auth({"Authorization": f"Bearer {token}"})


# ── tenant store ─────────────────────────────────────────────────────────


@pytest.fixture
def tenant_store(tmp_path):
    return TenantStore(tmp_path / "tenants.db", tmp_path / "storage")


def test_create_tenant_returns_tenant_with_owner(tenant_store):
    t = tenant_store.create_tenant(
        name="Aither", owner_user_id="luka", owner_email="l@x.com",
    )
    assert isinstance(t, Tenant)
    assert t.name == "Aither"
    assert t.plan == "free"
    members = tenant_store.list_members(t.id)
    assert len(members) == 1
    assert members[0]["role"] == "owner"
    assert members[0]["user_id"] == "luka"


def test_create_tenant_provisions_storage_dirs(tenant_store):
    t = tenant_store.create_tenant(name="X", owner_user_id="u")
    for kind in ("workbooks", "comments", "review", "audit"):
        p = tenant_store.storage_path(tenant_id=t.id, kind=kind)
        assert p.exists() and p.is_dir()


def test_storage_path_unknown_kind_raises(tenant_store):
    t = tenant_store.create_tenant(name="X", owner_user_id="u")
    with pytest.raises(ValueError):
        tenant_store.storage_path(tenant_id=t.id, kind="bogus")


def test_add_member_idempotent(tenant_store):
    t = tenant_store.create_tenant(name="X", owner_user_id="luka")
    tenant_store.add_member(tenant_id=t.id, user_id="bob", role="member")
    tenant_store.add_member(tenant_id=t.id, user_id="bob", role="member")
    members = tenant_store.list_members(t.id)
    assert len(members) == 2  # owner + bob


def test_remove_member(tenant_store):
    t = tenant_store.create_tenant(name="X", owner_user_id="luka")
    tenant_store.add_member(tenant_id=t.id, user_id="bob")
    tenant_store.remove_member(tenant_id=t.id, user_id="bob")
    members = tenant_store.list_members(t.id)
    assert all(m["user_id"] != "bob" for m in members)


def test_list_tenants_for_user(tenant_store):
    t1 = tenant_store.create_tenant(name="A", owner_user_id="luka")
    t2 = tenant_store.create_tenant(name="B", owner_user_id="bob")
    tenant_store.add_member(tenant_id=t2.id, user_id="luka")
    luka_tenants = tenant_store.list_tenants_for_user("luka")
    assert {t.id for t in luka_tenants} == {t1.id, t2.id}


def test_assert_member_passes_for_member(tenant_store):
    t = tenant_store.create_tenant(name="X", owner_user_id="luka")
    tenant_store.assert_member(tenant_id=t.id, user_id="luka")


def test_assert_member_raises_for_non_member(tenant_store):
    t = tenant_store.create_tenant(name="X", owner_user_id="luka")
    with pytest.raises(KeyError):
        tenant_store.assert_member(tenant_id=t.id, user_id="bob")


# ── billing: webhook handler ─────────────────────────────────────────────


def _stripe_payload(event_type="checkout.session.completed", **kw):
    obj = {
        "amount_total": kw.pop("amount_total", 9900),
        "currency": "usd",
        "metadata": {
            "tenant_id": kw.pop("tenant_id", "t-123"),
            "user_id": kw.pop("user_id", "u-456"),
            "plan": kw.pop("plan", "seat_monthly"),
        },
    }
    return {
        "id": kw.pop("event_id", "evt_test"),
        "type": event_type,
        "data": {"object": obj},
    }


def _sign_payload(payload_bytes: bytes, secret: str, ts: int = None) -> str:
    ts = ts or int(time.time())
    signed = f"{ts}.".encode("utf-8") + payload_bytes
    sig = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_handle_webhook_skip_signature_path():
    payload = json.dumps(_stripe_payload()).encode()
    event = handle_stripe_webhook(payload, "", skip_signature=True)
    assert isinstance(event, BillingEvent)
    assert event.event_type == "checkout.session.completed"
    assert event.tenant_id == "t-123"
    assert event.user_id == "u-456"
    assert event.amount_cents == 9900
    assert event.plan == "seat_monthly"


def test_handle_webhook_extracts_workbook_oneoff_plan():
    payload = json.dumps(_stripe_payload(plan="workbook_oneoff", amount_total=500)).encode()
    event = handle_stripe_webhook(payload, "", skip_signature=True)
    assert event.plan == "workbook_oneoff"
    assert event.amount_cents == 500


def test_handle_webhook_invalid_json_raises():
    with pytest.raises(WebhookSignatureError):
        handle_stripe_webhook(b"not json", "", skip_signature=True)


def test_handle_webhook_signature_verification_passes():
    secret = "whsec_testabc"
    payload = json.dumps(_stripe_payload()).encode()
    sig = _sign_payload(payload, secret)
    event = handle_stripe_webhook(payload, sig, secret=secret)
    assert event.tenant_id == "t-123"


def test_handle_webhook_signature_verification_rejects_tamper():
    secret = "whsec_testabc"
    payload = json.dumps(_stripe_payload()).encode()
    sig = _sign_payload(payload, secret)
    tampered = payload + b"X"
    with pytest.raises(WebhookSignatureError):
        handle_stripe_webhook(tampered, sig, secret=secret)


def test_handle_webhook_signature_rejects_old_timestamp():
    secret = "whsec_testabc"
    payload = json.dumps(_stripe_payload()).encode()
    old_ts = int(time.time()) - 600  # 10min ago > 5min tolerance
    sig = _sign_payload(payload, secret, ts=old_ts)
    with pytest.raises(WebhookSignatureError):
        handle_stripe_webhook(payload, sig, secret=secret)


def test_handle_webhook_missing_secret_raises(monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    payload = json.dumps(_stripe_payload()).encode()
    with pytest.raises(WebhookSignatureError):
        handle_stripe_webhook(payload, "t=1,v1=xx")
