"""SaaS API routes — tenant management, auth, billing, tenant-scoped workbooks.

Mounted under ``/api/v1/*`` by ``create_app``. Keeps the existing demo
routes (/, /upload, /workbook/{id}/...) intact while adding the
production SaaS surface.

Auth: every route requires a valid ``Authorization: Bearer <jwt>`` (or
``MODELFORGE_AUTH_DEV_BYPASS=1`` + ``X-User-Id`` + ``X-Tenant-Id`` headers
for local dev).

Tenant isolation: every workbook / comment / audit row is scoped to the
authenticated tenant_id. Cross-tenant access is impossible because the
tenant_id is derived from the verified JWT claim.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

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


# ── module-level singletons (lazy) ──────────────────────────────────────────


def _get_tenant_store() -> TenantStore:
    """Return process-wide TenantStore. Path overrideable via env."""
    db_path = os.environ.get(
        "MODELFORGE_TENANT_DB",
        str(Path.home() / ".modelforge" / "tenants.db"),
    )
    storage_root = os.environ.get(
        "MODELFORGE_TENANT_STORAGE",
        str(Path.home() / ".modelforge" / "tenant_storage"),
    )
    return TenantStore(Path(db_path), Path(storage_root))


# ── auth dependency ────────────────────────────────────────────────────────


def authenticate(request: Request) -> AuthContext:
    """FastAPI dep: extract AuthContext from request headers."""
    headers = dict(request.headers)
    try:
        return require_auth(headers)
    except AuthError as e:
        raise HTTPException(status_code=401, detail=str(e)) from e


# ── request/response models ────────────────────────────────────────────────


class CreateTenantRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    plan: str = "free"
    seats: int = Field(default=1, ge=1, le=500)


class TenantResponse(BaseModel):
    id: str
    name: str
    plan: str
    seats: int
    created_at: str
    deactivated: bool

    @classmethod
    def from_tenant(cls, t: Tenant) -> "TenantResponse":
        return cls(
            id=t.id, name=t.name, plan=t.plan, seats=t.seats,
            created_at=t.created_at, deactivated=t.deactivated,
        )


class AddMemberRequest(BaseModel):
    user_id: str
    email: Optional[str] = None
    role: str = "member"


class WhoamiResponse(BaseModel):
    user_id: str
    tenant_id: str
    email: Optional[str]
    role: str
    is_dev_bypass: bool


# ── router ──────────────────────────────────────────────────────────────────


def build_saas_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1", tags=["saas"])

    @router.get("/healthz")
    def healthz() -> dict:
        return {
            "status": "ok",
            "service": "modelforge-saas",
            "auth_dev_bypass": os.environ.get("MODELFORGE_AUTH_DEV_BYPASS") == "1",
            "supabase_jwt_configured": bool(os.environ.get("SUPABASE_JWT_SECRET")),
            "stripe_webhook_configured": bool(os.environ.get("STRIPE_WEBHOOK_SECRET")),
        }

    # ── auth ──────────────────────────────────────────────────────────────

    @router.get("/auth/whoami", response_model=WhoamiResponse)
    def whoami(ctx: AuthContext = Depends(authenticate)) -> WhoamiResponse:
        return WhoamiResponse(
            user_id=ctx.user_id, tenant_id=ctx.tenant_id,
            email=ctx.email, role=ctx.role, is_dev_bypass=ctx.is_dev_bypass,
        )

    # ── tenants ───────────────────────────────────────────────────────────

    @router.post("/tenants", response_model=TenantResponse, status_code=201)
    def create_tenant(
        req: CreateTenantRequest,
        ctx: AuthContext = Depends(authenticate),
    ) -> TenantResponse:
        store = _get_tenant_store()
        tenant = store.create_tenant(
            name=req.name, plan=req.plan, seats=req.seats,
            owner_user_id=ctx.user_id, owner_email=ctx.email,
        )
        return TenantResponse.from_tenant(tenant)

    @router.get("/tenants", response_model=list[TenantResponse])
    def list_my_tenants(
        ctx: AuthContext = Depends(authenticate),
    ) -> list[TenantResponse]:
        store = _get_tenant_store()
        tenants = store.list_tenants_for_user(ctx.user_id)
        return [TenantResponse.from_tenant(t) for t in tenants]

    @router.get("/tenants/{tenant_id}", response_model=TenantResponse)
    def get_tenant(
        tenant_id: str,
        ctx: AuthContext = Depends(authenticate),
    ) -> TenantResponse:
        store = _get_tenant_store()
        try:
            store.assert_member(tenant_id=tenant_id, user_id=ctx.user_id)
        except KeyError:
            raise HTTPException(403, f"not a member of tenant {tenant_id}")
        t = store.get_tenant(tenant_id)
        if t is None:
            raise HTTPException(404, f"tenant {tenant_id} not found")
        return TenantResponse.from_tenant(t)

    @router.get("/tenants/{tenant_id}/members")
    def list_tenant_members(
        tenant_id: str,
        ctx: AuthContext = Depends(authenticate),
    ) -> list[dict]:
        store = _get_tenant_store()
        try:
            store.assert_member(tenant_id=tenant_id, user_id=ctx.user_id)
        except KeyError:
            raise HTTPException(403, f"not a member of tenant {tenant_id}")
        return store.list_members(tenant_id)

    @router.post("/tenants/{tenant_id}/members", status_code=201)
    def add_tenant_member(
        tenant_id: str,
        req: AddMemberRequest,
        ctx: AuthContext = Depends(authenticate),
    ) -> dict:
        store = _get_tenant_store()
        try:
            store.assert_member(tenant_id=tenant_id, user_id=ctx.user_id)
        except KeyError:
            raise HTTPException(403, f"not a member of tenant {tenant_id}")
        # Only owners/admins can add members (enforced by SQLite layer in prod)
        members = store.list_members(tenant_id)
        my_role = next((m["role"] for m in members if m["user_id"] == ctx.user_id), None)
        if my_role not in ("owner", "admin"):
            raise HTTPException(403, "owner or admin role required")
        store.add_member(
            tenant_id=tenant_id, user_id=req.user_id,
            email=req.email, role=req.role,
        )
        return {"ok": True, "tenant_id": tenant_id, "user_id": req.user_id}

    @router.delete("/tenants/{tenant_id}/members/{user_id}")
    def remove_tenant_member(
        tenant_id: str, user_id: str,
        ctx: AuthContext = Depends(authenticate),
    ) -> dict:
        store = _get_tenant_store()
        try:
            store.assert_member(tenant_id=tenant_id, user_id=ctx.user_id)
        except KeyError:
            raise HTTPException(403, f"not a member of tenant {tenant_id}")
        members = store.list_members(tenant_id)
        my_role = next((m["role"] for m in members if m["user_id"] == ctx.user_id), None)
        if my_role not in ("owner", "admin"):
            raise HTTPException(403, "owner or admin role required")
        store.remove_member(tenant_id=tenant_id, user_id=user_id)
        return {"ok": True}

    # ── billing webhook ───────────────────────────────────────────────────

    @router.post("/billing/webhook")
    async def stripe_webhook(request: Request) -> dict:
        """Stripe webhook ingress. Verifies HMAC signature + records event."""
        payload = await request.body()
        sig = request.headers.get("stripe-signature", "")
        try:
            event = handle_stripe_webhook(payload, sig)
        except WebhookSignatureError as e:
            raise HTTPException(400, f"webhook verification failed: {e}")
        # Persist to per-tenant audit dir for now (Postgres in prod via RLS)
        if event.tenant_id:
            store = _get_tenant_store()
            audit_dir = store.storage_path(
                tenant_id=event.tenant_id, kind="audit",
            )
            event_path = audit_dir / f"billing_{event.stripe_event_id}.json"
            event_path.write_text(
                json.dumps({
                    "event_type": event.event_type,
                    "stripe_event_id": event.stripe_event_id,
                    "tenant_id": event.tenant_id,
                    "user_id": event.user_id,
                    "amount_cents": event.amount_cents,
                    "currency": event.currency,
                    "plan": event.plan,
                }, indent=2),
                encoding="utf-8",
            )
        return {
            "ok": True,
            "event_type": event.event_type,
            "stripe_event_id": event.stripe_event_id,
            "tenant_id": event.tenant_id,
            "amount_cents": event.amount_cents,
        }

    # ── tenant-scoped workbook routes ─────────────────────────────────────

    @router.get("/tenants/{tenant_id}/workbooks")
    def list_tenant_workbooks(
        tenant_id: str,
        ctx: AuthContext = Depends(authenticate),
    ) -> list[dict]:
        store = _get_tenant_store()
        try:
            store.assert_member(tenant_id=tenant_id, user_id=ctx.user_id)
        except KeyError:
            raise HTTPException(403, f"not a member of tenant {tenant_id}")
        wb_dir = store.storage_path(tenant_id=tenant_id, kind="workbooks")
        out = []
        for xlsx in sorted(wb_dir.glob("*.xlsx")):
            manifest = xlsx.with_suffix(".manifest.json")
            entry = {
                "name": xlsx.name,
                "size_bytes": xlsx.stat().st_size,
                "has_manifest": manifest.exists(),
            }
            if manifest.exists():
                try:
                    m = json.loads(manifest.read_text(encoding="utf-8"))
                    entry["spec_sha256"] = (m.get("spec_sha256") or "")[:16]
                    entry["workbook_sha256"] = (m.get("workbook_sha256") or "")[:16]
                    entry["build_timestamp_utc"] = m.get("build_timestamp_utc")
                except Exception:
                    pass
            out.append(entry)
        return out

    return router


__all__ = ["build_saas_router", "authenticate"]
