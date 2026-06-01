"""Integration tests for the FastAPI SaaS surface (D5 deploy).

Uses FastAPI TestClient — no real network, no real Supabase, no real
Stripe. Auth is dev-bypass via MODELFORGE_AUTH_DEV_BYPASS=1 +
X-User-Id + X-Tenant-Id headers (mirrors the production auth surface
exactly without requiring a JWT signing secret).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Fresh app per test with isolated tenant store + dev-bypass auth."""
    monkeypatch.setenv("MODELFORGE_AUTH_DEV_BYPASS", "1")
    monkeypatch.setenv("MODELFORGE_TENANT_DB", str(tmp_path / "tenants.db"))
    monkeypatch.setenv(
        "MODELFORGE_TENANT_STORAGE", str(tmp_path / "tenant_storage"),
    )
    from modelforge.web.app import create_app
    app = create_app(session_dir=tmp_path / "wb_session")
    return TestClient(app)


def _h(user_id: str = "u-demo", tenant_id: str = "t-123",
       email: str = "demo@example.com", role: str = "owner") -> dict:
    return {
        "X-User-Id": user_id,
        "X-Tenant-Id": tenant_id,
        "X-Email": email,
        "X-Role": role,
    }


# ── healthz ─────────────────────────────────────────────────────────────────


def test_root_healthz_returns_ok(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_saas_healthz_reports_dev_bypass_status(client):
    r = client.get("/api/v1/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "modelforge-saas"
    assert body["auth_dev_bypass"] is True
    assert body["supabase_jwt_configured"] is False
    assert body["stripe_webhook_configured"] is False


# ── auth ────────────────────────────────────────────────────────────────────


def test_whoami_returns_authcontext(client):
    r = client.get("/api/v1/auth/whoami", headers=_h())
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "u-demo"
    assert body["tenant_id"] == "t-123"
    assert body["email"] == "demo@example.com"
    assert body["role"] == "owner"
    assert body["is_dev_bypass"] is True


def test_whoami_401_without_headers(client):
    r = client.get("/api/v1/auth/whoami")
    assert r.status_code == 401


# ── tenants ─────────────────────────────────────────────────────────────────


def test_create_tenant_returns_owner_membership(client):
    r = client.post(
        "/api/v1/tenants",
        json={"name": "DemoCo Capital", "plan": "free", "seats": 3},
        headers=_h(),
    )
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == "DemoCo Capital"
    assert body["plan"] == "free"
    assert body["seats"] == 3
    assert body["id"].startswith("tenant_")


def test_list_my_tenants_is_empty_at_first(client):
    r = client.get("/api/v1/tenants", headers=_h(user_id="u-empty"))
    assert r.status_code == 200
    assert r.json() == []


def test_list_my_tenants_contains_created_one(client):
    create_resp = client.post(
        "/api/v1/tenants", json={"name": "Foo"}, headers=_h(),
    )
    tid = create_resp.json()["id"]
    r = client.get("/api/v1/tenants", headers=_h())
    assert r.status_code == 200
    tenants = r.json()
    assert any(t["id"] == tid for t in tenants)


def test_get_tenant_403_for_non_member(client):
    create_resp = client.post(
        "/api/v1/tenants", json={"name": "Owned by Alice"}, headers=_h(user_id="alice"),
    )
    tid = create_resp.json()["id"]
    r = client.get(f"/api/v1/tenants/{tid}", headers=_h(user_id="bob"))
    assert r.status_code == 403


def test_get_tenant_404_for_unknown_id(client):
    r = client.get("/api/v1/tenants/tenant_doesnotexist", headers=_h())
    assert r.status_code in (403, 404)  # 403 (membership check) or 404


def test_add_and_remove_member(client):
    create_resp = client.post(
        "/api/v1/tenants", json={"name": "Demo"}, headers=_h(user_id="alice"),
    )
    tid = create_resp.json()["id"]
    add = client.post(
        f"/api/v1/tenants/{tid}/members",
        json={"user_id": "bob", "email": "bob@example.com", "role": "member"},
        headers=_h(user_id="alice"),
    )
    assert add.status_code == 201

    members = client.get(
        f"/api/v1/tenants/{tid}/members", headers=_h(user_id="alice"),
    ).json()
    assert any(m["user_id"] == "bob" for m in members)

    rm = client.delete(
        f"/api/v1/tenants/{tid}/members/bob", headers=_h(user_id="alice"),
    )
    assert rm.status_code == 200
    members = client.get(
        f"/api/v1/tenants/{tid}/members", headers=_h(user_id="alice"),
    ).json()
    assert all(m["user_id"] != "bob" for m in members)


def test_add_member_requires_owner_or_admin(client):
    create_resp = client.post(
        "/api/v1/tenants", json={"name": "Demo"}, headers=_h(user_id="alice"),
    )
    tid = create_resp.json()["id"]
    client.post(
        f"/api/v1/tenants/{tid}/members",
        json={"user_id": "bob", "role": "member"},
        headers=_h(user_id="alice"),
    )
    # Bob (member, not admin) tries to add carol → 403
    r = client.post(
        f"/api/v1/tenants/{tid}/members",
        json={"user_id": "carol", "role": "member"},
        headers=_h(user_id="bob"),
    )
    assert r.status_code == 403


# ── billing webhook ────────────────────────────────────────────────────────


def _make_stripe_payload(tenant_id="t-123", amount=9900) -> dict:
    return {
        "id": f"evt_test_{int(time.time())}",
        "type": "checkout.session.completed",
        "data": {"object": {
            "amount_total": amount, "currency": "usd",
            "metadata": {"tenant_id": tenant_id, "user_id": "u-demo",
                         "plan": "seat_monthly"},
        }},
    }


def _sign(payload_bytes: bytes, secret: str) -> str:
    ts = int(time.time())
    msg = f"{ts}.".encode() + payload_bytes
    sig = hmac.new(secret.encode(), msg, hashlib.sha256).hexdigest()
    return f"t={ts},v1={sig}"


def test_billing_webhook_400_without_secret_configured(client):
    payload = _make_stripe_payload()
    r = client.post(
        "/api/v1/billing/webhook",
        content=json.dumps(payload).encode(),
        headers={"stripe-signature": "t=0,v1=zz"},
    )
    assert r.status_code == 400
    assert "verification" in r.json()["detail"].lower()


def test_billing_webhook_accepts_signed_payload(client, monkeypatch):
    secret = "whsec_test_xyz"
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", secret)
    # Pre-create the tenant so the webhook can write its audit row
    client.post(
        "/api/v1/tenants", json={"name": "Foo"},
        headers=_h(tenant_id="t-stripe"),
    )
    payload = json.dumps(_make_stripe_payload(tenant_id="t-stripe")).encode()
    sig = _sign(payload, secret)
    r = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": sig, "content-type": "application/json"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["event_type"] == "checkout.session.completed"
    assert body["amount_cents"] == 9900


def test_billing_webhook_rejects_bad_signature(client, monkeypatch):
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_real")
    payload = json.dumps(_make_stripe_payload()).encode()
    bad_sig = _sign(payload, "whsec_wrong")
    r = client.post(
        "/api/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": bad_sig},
    )
    assert r.status_code == 400


# ── tenant-scoped workbooks ─────────────────────────────────────────────────


def test_list_tenant_workbooks_empty(client):
    create_resp = client.post(
        "/api/v1/tenants", json={"name": "X"}, headers=_h(),
    )
    tid = create_resp.json()["id"]
    r = client.get(f"/api/v1/tenants/{tid}/workbooks", headers=_h())
    assert r.status_code == 200
    assert r.json() == []


def test_list_tenant_workbooks_403_for_non_member(client):
    create_resp = client.post(
        "/api/v1/tenants", json={"name": "X"}, headers=_h(user_id="alice"),
    )
    tid = create_resp.json()["id"]
    r = client.get(
        f"/api/v1/tenants/{tid}/workbooks", headers=_h(user_id="bob"),
    )
    assert r.status_code == 403
