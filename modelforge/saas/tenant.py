"""Tenant isolation — per-tenant storage paths + RLS-friendly queries.

Tenant objects are durably backed by Supabase Postgres in production
(via the SQL schema in ``migrations/001_supabase_init.sql``). For local
dev + tests, a SQLite store mirrors the same shape so the higher
layers don't care which is wired in.

Storage layout per tenant::

    {root}/
      {tenant_id}/
        workbooks/   ← .xlsx + .manifest.json files
        comments/    ← CommentStore SQLite
        review/      ← ReviewState JSON files
        audit/       ← per-tenant audit slices

Combined with row-level Postgres policies (tenant_id = auth.uid()), this
gives full per-tenant isolation across both filesystem and database
layers.
"""
from __future__ import annotations

import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


_SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    plan         TEXT NOT NULL DEFAULT 'free',
    seats        INTEGER NOT NULL DEFAULT 1,
    created_at   TEXT NOT NULL,
    deactivated  INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS tenant_members (
    tenant_id    TEXT NOT NULL,
    user_id      TEXT NOT NULL,
    email        TEXT,
    role         TEXT NOT NULL DEFAULT 'member',
    joined_at    TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_member_user ON tenant_members(user_id);
"""


@dataclass(frozen=True)
class Tenant:
    id: str
    name: str
    plan: str = "free"
    seats: int = 1
    created_at: str = ""
    deactivated: bool = False


class TenantStore:
    """SQLite-backed tenant + member registry. Production: Supabase Postgres."""

    def __init__(self, db_path: Path | str, storage_root: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── tenants ───────────────────────────────────────────────────────────

    def create_tenant(
        self,
        *,
        name: str,
        plan: str = "free",
        seats: int = 1,
        owner_user_id: str,
        owner_email: Optional[str] = None,
    ) -> Tenant:
        """Create a tenant and register the creator as 'owner'."""
        tid = f"tenant_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(
                """INSERT INTO tenants(id, name, plan, seats, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (tid, name, plan, seats, now),
            )
            c.execute(
                """INSERT INTO tenant_members(tenant_id, user_id, email, role, joined_at)
                   VALUES (?, ?, ?, 'owner', ?)""",
                (tid, owner_user_id, owner_email, now),
            )
        # Create storage prefix
        for sub in ("workbooks", "comments", "review", "audit"):
            (self.storage_root / tid / sub).mkdir(parents=True, exist_ok=True)
        return Tenant(
            id=tid, name=name, plan=plan, seats=seats,
            created_at=now, deactivated=False,
        )

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        with self._conn() as c:
            row = c.execute(
                "SELECT * FROM tenants WHERE id=?", (tenant_id,),
            ).fetchone()
        if not row:
            return None
        return Tenant(
            id=row["id"], name=row["name"], plan=row["plan"],
            seats=row["seats"], created_at=row["created_at"],
            deactivated=bool(row["deactivated"]),
        )

    def add_member(
        self,
        *,
        tenant_id: str,
        user_id: str,
        email: Optional[str] = None,
        role: str = "member",
    ) -> None:
        if not self.get_tenant(tenant_id):
            raise KeyError(f"unknown tenant: {tenant_id}")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(
                """INSERT OR IGNORE INTO tenant_members
                   (tenant_id, user_id, email, role, joined_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (tenant_id, user_id, email, role, now),
            )

    def remove_member(self, *, tenant_id: str, user_id: str) -> None:
        with self._conn() as c:
            c.execute(
                "DELETE FROM tenant_members WHERE tenant_id=? AND user_id=?",
                (tenant_id, user_id),
            )

    def list_members(self, tenant_id: str) -> list[dict]:
        with self._conn() as c:
            rows = c.execute(
                "SELECT * FROM tenant_members WHERE tenant_id=? ORDER BY joined_at",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def list_tenants_for_user(self, user_id: str) -> list[Tenant]:
        with self._conn() as c:
            rows = c.execute(
                """SELECT t.* FROM tenants t
                   JOIN tenant_members m ON m.tenant_id = t.id
                   WHERE m.user_id = ? AND t.deactivated = 0""",
                (user_id,),
            ).fetchall()
        return [
            Tenant(
                id=r["id"], name=r["name"], plan=r["plan"], seats=r["seats"],
                created_at=r["created_at"], deactivated=bool(r["deactivated"]),
            )
            for r in rows
        ]

    # ── storage paths ─────────────────────────────────────────────────────

    def storage_path(self, *, tenant_id: str, kind: str = "workbooks") -> Path:
        """Return the per-tenant storage subdir, creating it on demand."""
        if kind not in ("workbooks", "comments", "review", "audit"):
            raise ValueError(f"unknown storage kind: {kind}")
        p = self.storage_root / tenant_id / kind
        p.mkdir(parents=True, exist_ok=True)
        return p

    def assert_member(self, *, tenant_id: str, user_id: str) -> None:
        """Raise KeyError if user is not a member of tenant."""
        with self._conn() as c:
            row = c.execute(
                "SELECT 1 FROM tenant_members WHERE tenant_id=? AND user_id=?",
                (tenant_id, user_id),
            ).fetchone()
        if not row:
            raise KeyError(
                f"user {user_id!r} is not a member of tenant {tenant_id!r}"
            )
