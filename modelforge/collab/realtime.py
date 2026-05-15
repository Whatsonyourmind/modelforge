"""Realtime collab — Python client for the CF Worker.

Mirrors `CommentStore` events into the remote Y.Doc via the Worker's
REST endpoints. The Worker (web/collab-worker/) handles the Yjs CRDT
merge; Python only needs to POST the events. WebSocket consumption
of remote updates is optional — only needed if you want server-side
notification of cross-user activity.

Usage::

    from modelforge.collab.realtime import RealtimeClient
    rc = RealtimeClient(
        worker_url="https://modelforge-collab.workers.dev",
        jwt_token=os.environ["SUPABASE_JWT_TOKEN"],
        doc_id="deal-2026-Q2-pbsa-padova",
    )
    rc.publish_comment_event(event_dict)
    remote_comments = rc.list_comments()

For local dev without a deployed Worker, set ``worker_url`` to
``http://localhost:8787`` after running ``wrangler dev`` in
``web/collab-worker/``.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict
from typing import Any, Optional

from modelforge.collab.comments import Comment


class RealtimeError(RuntimeError):
    """Raised on any RealtimeClient transport / auth failure."""


class RealtimeClient:
    """Python client for the ModelForge Collab Worker.

    Stateless — every method opens a fresh HTTP request. For long-lived
    WebSocket subscriptions, use ``RealtimeClient.connect()`` (returns a
    context-managed client wrapping a stdlib websocket; optional dep).
    """

    def __init__(
        self,
        *,
        worker_url: str,
        jwt_token: str,
        doc_id: str,
        timeout_seconds: int = 10,
    ) -> None:
        self.worker_url = worker_url.rstrip("/")
        self.jwt_token = jwt_token
        self.doc_id = doc_id
        self.timeout = timeout_seconds

    # ── transport ─────────────────────────────────────────────────────────

    def _headers(self, extra: Optional[dict] = None) -> dict:
        h = {
            "Authorization": f"Bearer {self.jwt_token}",
            "Accept": "application/json",
            "User-Agent": "modelforge-collab/0.1",
        }
        if extra:
            h.update(extra)
        return h

    def _request(self, method: str, path: str, body: Optional[bytes] = None,
                 headers: Optional[dict] = None) -> dict:
        url = f"{self.worker_url}{path}"
        req = urllib.request.Request(
            url, method=method, data=body, headers=self._headers(headers),
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8") if resp.read != bytes else b""
                if not raw:
                    return {}
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            body_txt = e.read().decode("utf-8", errors="replace")
            raise RealtimeError(
                f"{method} {path} → HTTP {e.code}: {body_txt[:200]}"
            ) from e
        except urllib.error.URLError as e:
            raise RealtimeError(f"{method} {path} network error: {e.reason}") from e

    # ── public API ────────────────────────────────────────────────────────

    def healthz(self) -> bool:
        """Return True if the Worker responds 200 to /healthz."""
        try:
            req = urllib.request.Request(f"{self.worker_url}/healthz")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status == 200
        except urllib.error.URLError:
            return False

    def publish_comment_event(self, event: Comment | dict) -> dict:
        """POST a CommentStore event to the doc's comments map."""
        if isinstance(event, Comment):
            payload = asdict(event)
        else:
            payload = dict(event)
        body = json.dumps(payload).encode("utf-8")
        return self._request(
            "POST",
            f"/docs/{self.doc_id}/comments",
            body=body,
            headers={"Content-Type": "application/json"},
        )

    def list_comments(self) -> list[dict]:
        """GET all comments stored in the doc's Y.Doc 'comments' map."""
        out = self._request("GET", f"/docs/{self.doc_id}/comments")
        return list(out.get("comments") or [])

    def snapshot_url(self) -> str:
        """URL of the binary Y.Doc state snapshot (for debugging)."""
        return f"{self.worker_url}/docs/{self.doc_id}/snapshot"

    def ws_url(self) -> str:
        """URL of the WebSocket sync endpoint (for browser clients)."""
        scheme = "wss" if self.worker_url.startswith("https") else "ws"
        host = self.worker_url.split("://", 1)[1]
        return f"{scheme}://{host}/docs/{self.doc_id}/ws"


def sync_store_to_remote(
    *,
    store,         # CommentStore
    client: RealtimeClient,
    since_id: Optional[str] = None,
) -> int:
    """One-shot mirror: push every comment event in `store` to the worker.

    Returns the number of events published. Idempotent — if a thread
    already exists in the remote Y.Doc, the same key overrides without
    creating a duplicate (Y.Doc map semantics).
    """
    n = 0
    for thread in store.all_threads():
        for event in store.events_for_thread(thread.id):
            client.publish_comment_event(event)
            n += 1
    return n


__all__ = [
    "RealtimeClient",
    "RealtimeError",
    "sync_store_to_remote",
]
