"""Multi-tenant auth — Supabase JWT verification with dev-mode bypass.

In production: validates Supabase JWTs (Bearer token) and extracts
user_id + tenant_id (from a custom JWT claim or Supabase row lookup).

In dev / testing: when ``MODELFORGE_AUTH_DEV_BYPASS=1`` is set, accepts
``X-User-Id`` + ``X-Tenant-Id`` headers as the auth context. Lets the
SaaS shell run end-to-end on a laptop with no Supabase account.

Usage in a FastAPI route::

    from fastapi import Depends
    from modelforge.saas.auth import AuthContext, require_auth

    @app.post("/api/build")
    async def build(spec: dict, ctx: AuthContext = Depends(require_auth)):
        # ctx.user_id, ctx.tenant_id, ctx.email are populated
        ...
"""
from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Optional


# ── public ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuthContext:
    """Authenticated principal for the current request."""
    user_id: str
    tenant_id: str
    email: Optional[str] = None
    role: str = "member"   # "owner" | "admin" | "member"
    is_dev_bypass: bool = False


class AuthError(Exception):
    """Raised on any auth failure — translated to 401 in FastAPI layer."""


def _dev_bypass_enabled() -> bool:
    return os.environ.get("MODELFORGE_AUTH_DEV_BYPASS") == "1"


def _decode_jwt_unverified(token: str) -> dict:
    """Decode a JWT payload WITHOUT signature verification.

    For local-dev or ``unverified`` paths only. The verified path uses
    ``PyJWT`` + the Supabase JWKS — wired when SUPABASE_JWT_SECRET is set.
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise AuthError("Malformed JWT")
    payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
    try:
        return json.loads(base64.urlsafe_b64decode(payload_b64))
    except Exception as e:
        raise AuthError(f"Cannot decode JWT payload: {e}") from e


def _verify_jwt(token: str) -> dict:
    """Verify a Supabase JWT and return the payload.

    When ``SUPABASE_JWT_SECRET`` is set, performs HS256 signature check
    (Supabase's default for project JWTs). Otherwise raises AuthError —
    fail-closed in production, fail-open only via the dev bypass header.
    """
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise AuthError(
            "SUPABASE_JWT_SECRET not configured; "
            "set the env var or use MODELFORGE_AUTH_DEV_BYPASS=1 for local dev"
        )
    try:
        import jwt  # type: ignore
    except ImportError:
        raise AuthError(
            "PyJWT not installed; pip install pyjwt to enable verified JWT auth"
        )
    try:
        return jwt.decode(token, secret, algorithms=["HS256"], audience="authenticated")
    except jwt.PyJWTError as e:
        raise AuthError(f"JWT verification failed: {e}") from e


def get_current_user(headers: dict[str, str]) -> AuthContext:
    """Extract AuthContext from request headers.

    Two paths:
    1. ``MODELFORGE_AUTH_DEV_BYPASS=1`` + ``X-User-Id`` + ``X-Tenant-Id``
       headers → AuthContext with ``is_dev_bypass=True``.
    2. ``Authorization: Bearer <jwt>`` → verified Supabase JWT → AuthContext.
    """
    # Normalize header keys (FastAPI passes case-preserved; tests vary)
    norm = {k.lower(): v for k, v in headers.items()}

    if _dev_bypass_enabled():
        uid = norm.get("x-user-id")
        tid = norm.get("x-tenant-id")
        if not uid or not tid:
            raise AuthError(
                "MODELFORGE_AUTH_DEV_BYPASS=1 requires X-User-Id and X-Tenant-Id headers"
            )
        return AuthContext(
            user_id=uid,
            tenant_id=tid,
            email=norm.get("x-email"),
            role=norm.get("x-role", "member"),
            is_dev_bypass=True,
        )

    auth_h = norm.get("authorization") or ""
    if not auth_h.lower().startswith("bearer "):
        raise AuthError("Missing or malformed Authorization header")
    token = auth_h.split(" ", 1)[1].strip()

    payload = _verify_jwt(token)
    sub = payload.get("sub")
    if not sub:
        raise AuthError("JWT missing 'sub' (user_id)")
    # Tenant id is expected as a custom Supabase user-metadata claim,
    # set at signup via the Supabase trigger:
    #   user_metadata.tenant_id = <uuid>
    user_meta = payload.get("user_metadata") or {}
    tenant_id = (
        user_meta.get("tenant_id")
        or payload.get("tenant_id")
        # Fallback: every user in their own tenant if metadata not set
        or sub
    )
    return AuthContext(
        user_id=str(sub),
        tenant_id=str(tenant_id),
        email=payload.get("email"),
        role=user_meta.get("role", "member"),
        is_dev_bypass=False,
    )


def require_auth(headers: dict[str, str]) -> AuthContext:
    """Strict variant: raises AuthError on any failure (FastAPI dependency)."""
    return get_current_user(headers)


__all__ = ["AuthContext", "AuthError", "get_current_user", "require_auth"]
