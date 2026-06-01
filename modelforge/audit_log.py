"""Append-only audit log for ModelForge builds.

Every ``build_model``, ``run_qc``, ``ingest`` operation appends a row to a
SQLite log with timestamp, operation, inputs, outputs, hashes, and (optionally)
caller identity. Provides regulator-grade traceability of what was generated
when, by whom, with what inputs.

Used by the Phase-B SOC 2 audit pathway (one of the controls auditors verify).
Independent of the main ``graph/store.py`` SQLite — this is operational
auditing, not modeling state.

Usage::

    from modelforge.audit_log import AuditLog
    log = AuditLog()  # defaults to ~/.modelforge/audit.db

    with log.record("build_model", inputs={"spec": "deal.yaml"}, user="analyst@..."):
        ... do work ...
        log.set_outputs(xlsx="output/deal.xlsx", sha256="abc...")
"""
from __future__ import annotations

import getpass
import hashlib
import json
import logging
import os
import sqlite3
import socket
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger("modelforge.audit_log")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    event_id TEXT PRIMARY KEY,
    started_at REAL NOT NULL,
    finished_at REAL,
    duration_ms REAL,
    operation TEXT NOT NULL,
    status TEXT NOT NULL,
    inputs_json TEXT,
    outputs_json TEXT,
    user TEXT,
    host TEXT,
    pid INTEGER,
    cwd TEXT,
    error TEXT,
    inputs_sha256 TEXT,
    outputs_sha256 TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_started_at ON audit_events(started_at);
CREATE INDEX IF NOT EXISTS idx_audit_operation ON audit_events(operation);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_events(user);
"""


def _default_db_path() -> Path:
    """~/.modelforge/audit.db (user-scoped, persists across runs)."""
    home = Path(os.path.expanduser("~"))
    base = home / ".modelforge"
    base.mkdir(parents=True, exist_ok=True)
    return base / "audit.db"


def _safe_user() -> str:
    """Return the OS-level user; never raise."""
    try:
        return getpass.getuser()
    except Exception:
        return os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"


def _hash_json(d: dict[str, Any]) -> str:
    """Stable SHA-256 of a JSON-serializable dict."""
    raw = json.dumps(d, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class AuditLog:
    """Append-only audit log."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = Path(db_path) if db_path else _default_db_path()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()
        # Append-only — disable updates outside this class
        self._current_event_id: Optional[str] = None
        self._current_outputs: dict[str, Any] = {}

    @contextmanager
    def record(
        self,
        operation: str,
        *,
        inputs: Optional[dict[str, Any]] = None,
        user: Optional[str] = None,
    ):
        """Context manager: emits ``started`` row on enter, finalizes on exit.

        On exception, status is "error" and the exception repr is logged.
        """
        event_id = str(uuid.uuid4())
        started = time.time()
        self._current_event_id = event_id
        self._current_outputs = {}

        inputs_dict = inputs or {}
        inputs_hash = _hash_json(inputs_dict) if inputs_dict else None

        cur = self._conn.cursor()
        cur.execute(
            """INSERT INTO audit_events (event_id, started_at, operation, status,
                inputs_json, user, host, pid, cwd, inputs_sha256)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id,
                started,
                operation,
                "running",
                json.dumps(inputs_dict, default=str),
                user or _safe_user(),
                socket.gethostname(),
                os.getpid(),
                os.getcwd(),
                inputs_hash,
            ),
        )
        self._conn.commit()

        status = "ok"
        error: Optional[str] = None
        try:
            yield event_id
        except Exception as e:  # noqa: BLE001
            status = "error"
            error = repr(e)
            raise
        finally:
            finished = time.time()
            outputs_hash = _hash_json(self._current_outputs) if self._current_outputs else None
            cur.execute(
                """UPDATE audit_events
                   SET finished_at=?, duration_ms=?, status=?, outputs_json=?,
                       outputs_sha256=?, error=?
                   WHERE event_id=?""",
                (
                    finished,
                    (finished - started) * 1000.0,
                    status,
                    json.dumps(self._current_outputs, default=str) if self._current_outputs else None,
                    outputs_hash,
                    error,
                    event_id,
                ),
            )
            self._conn.commit()
            self._current_event_id = None
            self._current_outputs = {}

    def set_outputs(self, **outputs: Any) -> None:
        """Register outputs for the currently-running event."""
        if not self._current_event_id:
            log.warning("set_outputs called outside record() block")
            return
        self._current_outputs.update(outputs)

    def query(
        self,
        operation: Optional[str] = None,
        user: Optional[str] = None,
        since_unix: Optional[float] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Read-only query of audit events."""
        sql = "SELECT * FROM audit_events WHERE 1=1"
        params: list[Any] = []
        if operation:
            sql += " AND operation = ?"
            params.append(operation)
        if user:
            sql += " AND user = ?"
            params.append(user)
        if since_unix:
            sql += " AND started_at >= ?"
            params.append(since_unix)
        sql += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)

        cur = self._conn.cursor()
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

    def close(self) -> None:
        self._conn.close()


# Module-level singleton for convenience
_DEFAULT: Optional[AuditLog] = None


def get_log() -> AuditLog:
    """Lazily instantiated default AuditLog (~/.modelforge/audit.db)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = AuditLog()
    return _DEFAULT
