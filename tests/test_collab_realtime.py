"""Tests for the realtime client (CF Worker integration layer)."""
from __future__ import annotations

import io
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from modelforge.collab import (
    Comment,
    CommentStore,
    RealtimeClient,
    RealtimeError,
    sync_store_to_remote,
)


# ── helpers ───────────────────────────────────────────────────────────────


def _http_response(payload: dict | str, status: int = 200) -> MagicMock:
    body = json.dumps(payload).encode() if isinstance(payload, dict) else payload.encode()
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body
    cm.__enter__.return_value.status = status
    return cm


def _client() -> RealtimeClient:
    return RealtimeClient(
        worker_url="https://collab.test/",
        jwt_token="test-jwt",
        doc_id="deal-123",
    )


# ── healthz ───────────────────────────────────────────────────────────────


def test_healthz_returns_true_on_200():
    rc = _client()
    cm = MagicMock()
    cm.__enter__.return_value.status = 200
    with patch("urllib.request.urlopen", return_value=cm):
        assert rc.healthz() is True


def test_healthz_returns_false_on_network_error():
    rc = _client()
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
        assert rc.healthz() is False


# ── publish_comment_event ────────────────────────────────────────────────


def test_publish_comment_event_posts_to_doc_endpoint():
    rc = _client()
    captured = {}

    def fake_open(req, timeout):
        captured["url"] = req.full_url
        captured["method"] = req.get_method()
        captured["headers"] = dict(req.header_items())
        captured["body"] = req.data
        return _http_response({"ok": True, "id": "c1"})

    with patch("urllib.request.urlopen", side_effect=fake_open):
        out = rc.publish_comment_event({"id": "c1", "body": "hi"})
    assert out["ok"] is True
    assert out["id"] == "c1"
    assert captured["url"].endswith("/docs/deal-123/comments")
    assert captured["method"] == "POST"
    # Header lookup is case-preserved by stdlib (Authorization, Content-type, User-agent)
    h_lower = {k.lower(): v for k, v in captured["headers"].items()}
    assert h_lower["authorization"] == "Bearer test-jwt"
    assert h_lower["content-type"] == "application/json"
    body = json.loads(captured["body"])
    assert body["id"] == "c1"
    assert body["body"] == "hi"


def test_publish_comment_event_accepts_dataclass(tmp_path):
    """Comment dataclass should be auto-serialized to dict."""
    rc = _client()
    store = CommentStore(tmp_path / "c.db")
    c = store.create(anchor="wacc_rate", author="md@x", body="Q?")
    captured = {}

    def fake_open(req, timeout):
        captured["body"] = req.data
        return _http_response({"ok": True})

    with patch("urllib.request.urlopen", side_effect=fake_open):
        rc.publish_comment_event(c)
    body = json.loads(captured["body"])
    assert body["anchor"] == "wacc_rate"
    assert body["event"] == "create"


# ── list_comments ────────────────────────────────────────────────────────


def test_list_comments_returns_remote_list():
    rc = _client()
    payload = {"comments": [{"id": "c1", "body": "hi"}, {"id": "c2", "body": "yo"}]}
    with patch("urllib.request.urlopen", return_value=_http_response(payload)):
        out = rc.list_comments()
    assert len(out) == 2
    assert out[0]["id"] == "c1"


def test_list_comments_returns_empty_when_no_key():
    rc = _client()
    with patch("urllib.request.urlopen", return_value=_http_response({})):
        assert rc.list_comments() == []


# ── error handling ───────────────────────────────────────────────────────


def test_publish_raises_realtime_error_on_401():
    rc = _client()
    err = urllib.error.HTTPError(
        "u", 401, "Unauthorized", None, io.BytesIO(b"bad token"),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RealtimeError):
            rc.publish_comment_event({"id": "x"})


def test_list_raises_realtime_error_on_500():
    rc = _client()
    err = urllib.error.HTTPError(
        "u", 500, "Server Error", None, io.BytesIO(b"oops"),
    )
    with patch("urllib.request.urlopen", side_effect=err):
        with pytest.raises(RealtimeError):
            rc.list_comments()


# ── URL helpers ──────────────────────────────────────────────────────────


def test_ws_url_translates_https_to_wss():
    rc = _client()
    assert rc.ws_url() == "wss://collab.test/docs/deal-123/ws"


def test_ws_url_translates_http_to_ws():
    rc = RealtimeClient(
        worker_url="http://localhost:8787",
        jwt_token="x",
        doc_id="d",
    )
    assert rc.ws_url() == "ws://localhost:8787/docs/d/ws"


def test_snapshot_url_includes_doc_id():
    rc = _client()
    assert rc.snapshot_url() == "https://collab.test/docs/deal-123/snapshot"


# ── sync_store_to_remote ─────────────────────────────────────────────────


def test_sync_store_to_remote_publishes_every_event(tmp_path):
    store = CommentStore(tmp_path / "c.db")
    c1 = store.create(anchor="a", author="u1", body="Q1")
    store.reply(thread=c1.id, author="u2", body="A1")
    store.create(anchor="b", author="u1", body="Q2")
    rc = _client()
    publish_count = {"n": 0}

    def fake_open(req, timeout):
        publish_count["n"] += 1
        return _http_response({"ok": True})

    with patch("urllib.request.urlopen", side_effect=fake_open):
        n = sync_store_to_remote(store=store, client=rc)
    assert n == 3
    assert publish_count["n"] == 3
