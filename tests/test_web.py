"""Tests for modelforge.web (US-018 — FastAPI MVP)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from modelforge.templates import build_model
from modelforge.web import create_app

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    session = tmp_path_factory.mktemp("web_session")
    app = create_app(session_dir=session)
    return TestClient(app)


@pytest.fixture(scope="module")
def uploaded_workbook(client, tmp_path_factory):
    """Build a unitranche workbook and POST it to /upload once."""
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("web_uploaded") / "u.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    with out.open("rb") as fh:
        r = client.post(
            "/upload",
            files={"file": ("u.xlsx", fh,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert r.status_code == 200
    return r.json()


# ── Basic health ────────────────────────────────────────────────────────────


def test_health_returns_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"


def test_index_renders_html(client):
    r = client.get("/")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")
    assert "ModelForge Web" in r.text


# ── Upload ──────────────────────────────────────────────────────────────────


def test_upload_rejects_non_xlsx(client):
    r = client.post("/upload",
                    files={"file": ("test.pdf", b"%PDF", "application/pdf")})
    assert r.status_code == 400


def test_upload_rejects_empty(client):
    r = client.post("/upload",
                    files={"file": ("empty.xlsx", b"",
                                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 400


def test_upload_returns_metadata(uploaded_workbook):
    assert "workbook_id" in uploaded_workbook
    assert len(uploaded_workbook["workbook_id"]) == 16  # first 16 of SHA256
    assert uploaded_workbook["primary_output_ref"] is not None
    assert "Cover" in uploaded_workbook["sheet_names"]
    assert "Assumptions" in uploaded_workbook["sheet_names"]


def test_upload_idempotent_on_identical_file_bytes(client, uploaded_workbook):
    """Uploading the EXACT SAME file bytes twice returns the same wid.

    (We can't re-build the spec twice and expect matching wids — the
    Reproducibility sheet's build_timestamp differs per build — so we
    re-upload the stored file via the store's on-disk path.)
    """
    wid = uploaded_workbook["workbook_id"]
    # Find the stored file via the store
    stored = client.app.state.store.get(wid)
    raw = stored.path.read_bytes()
    r = client.post("/upload",
                    files={"file": (stored.original_name, raw,
                                    "application/octet-stream")})
    assert r.status_code == 200
    assert r.json()["workbook_id"] == wid


# ── View / metadata ─────────────────────────────────────────────────────────


def test_workbook_metadata_endpoint(client, uploaded_workbook):
    wid = uploaded_workbook["workbook_id"]
    r = client.get(f"/workbook/{wid}")
    assert r.status_code == 200
    body = r.json()
    assert body["workbook_id"] == wid
    assert body["primary_output_ref"] == uploaded_workbook["primary_output_ref"]


def test_workbook_view_html(client, uploaded_workbook):
    wid = uploaded_workbook["workbook_id"]
    r = client.get(f"/workbook/{wid}/view")
    assert r.status_code == 200
    assert "SensitivityAnalysis" in r.text
    assert "Reproducibility" in r.text


def test_unknown_workbook_returns_404(client):
    r = client.get("/workbook/nonexistenthex0")
    assert r.status_code == 404


# ── Dossier ─────────────────────────────────────────────────────────────────


def test_dossier_endpoint_returns_pdf(client, uploaded_workbook):
    wid = uploaded_workbook["workbook_id"]
    r = client.get(f"/workbook/{wid}/dossier")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF-")
    assert len(r.content) > 5000


# ── Drift ───────────────────────────────────────────────────────────────────


def test_drift_endpoint(client, uploaded_workbook):
    wid = uploaded_workbook["workbook_id"]
    r = client.get(f"/workbook/{wid}/drift")
    assert r.status_code == 200
    body = r.json()
    assert body["workbook_id"] == wid
    # CDMO unitranche has EURIBOR 6M at stale 2.8% → at least 1 flag
    assert body["flagged"] >= 1
    # Items should carry all required fields
    for item in body["items"]:
        assert "driver" in item
        assert "assumed" in item
        assert "current" in item
        assert "flagged" in item


# ── Diff ────────────────────────────────────────────────────────────────────


def test_diff_endpoint(client, uploaded_workbook):
    # Diff workbook against itself — clean result
    wid = uploaded_workbook["workbook_id"]
    r = client.get(f"/diff?a={wid}&b={wid}")
    assert r.status_code == 200
    assert "ModelForge diff" in r.text


def test_diff_missing_workbook_404(client):
    r = client.get("/diff?a=nonexistenthexxxx&b=nonexistenthexxxx")
    assert r.status_code == 404


# ── Risk ────────────────────────────────────────────────────────────────────


def test_risk_endpoint_post(client):
    r = client.post("/risk", json={
        "equity_value_eur_m": 500, "equity_volatility": 0.32,
        "debt_face_value_eur_m": 400, "lgd": 0.45, "maturity_years": 7,
        "counterparty": "TestCo",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["merton"]["converged"] is True
    assert 0 <= body["merton"]["pd"] <= 1
    assert body["ecl"]["stage"] in ("stage_1", "stage_2", "stage_3")


def test_risk_endpoint_rejects_invalid():
    """Negative equity rejected by Pydantic."""
    app = create_app()
    client_local = TestClient(app)
    r = client_local.post("/risk", json={
        "equity_value_eur_m": -1, "equity_volatility": 0.3,
        "debt_face_value_eur_m": 50,
    })
    assert r.status_code == 422
