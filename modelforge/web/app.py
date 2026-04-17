"""FastAPI app factory."""

from __future__ import annotations

import hashlib
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from openpyxl import load_workbook
from pydantic import BaseModel, Field


# ── In-memory + disk-backed workbook store ──────────────────────────────────


@dataclass
class StoredWorkbook:
    workbook_id: str     # content SHA-256 first 16 chars
    original_name: str
    path: Path
    sheet_names: list[str]
    primary_output_ref: Optional[str]
    reproducibility: dict = field(default_factory=dict)


class WorkbookStore:
    """File-system-backed registry keyed by content hash."""

    def __init__(self, session_dir: Optional[Path] = None) -> None:
        self.session_dir = session_dir or Path(tempfile.mkdtemp(
            prefix="modelforge_web_"))
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.workbooks: dict[str, StoredWorkbook] = {}
        self._rescan()

    def _rescan(self) -> None:
        """Re-populate from disk (survives server restart)."""
        for f in self.session_dir.glob("*.xlsx"):
            # workbook_id encoded in the stem
            wid = f.stem.split("_", 1)[0]
            if wid in self.workbooks:
                continue
            self._register_existing(f, wid)

    def _register_existing(self, path: Path, wid: str) -> StoredWorkbook:
        wb = load_workbook(path, data_only=False, keep_links=True,
                           read_only=False)
        primary = None
        if "primary_output" in wb.defined_names:
            primary = wb.defined_names["primary_output"].attr_text
        repro = {}
        if "Reproducibility" in wb.sheetnames:
            ws = wb["Reproducibility"]
            for r in range(5, ws.max_row + 1):
                k = ws.cell(row=r, column=1).value
                v = ws.cell(row=r, column=2).value
                if k and v is not None:
                    repro[str(k)] = str(v)
        stored = StoredWorkbook(
            workbook_id=wid,
            original_name=path.name.split("_", 1)[1] if "_" in path.name else path.name,
            path=path,
            sheet_names=list(wb.sheetnames),
            primary_output_ref=primary,
            reproducibility=repro,
        )
        self.workbooks[wid] = stored
        return stored

    def add(self, content: bytes, original_name: str) -> StoredWorkbook:
        wid = hashlib.sha256(content).hexdigest()[:16]
        if wid in self.workbooks:
            return self.workbooks[wid]
        safe_name = "".join(c if c.isalnum() or c in "-._" else "_"
                             for c in original_name)
        path = self.session_dir / f"{wid}_{safe_name}"
        path.write_bytes(content)
        return self._register_existing(path, wid)

    def get(self, wid: str) -> StoredWorkbook:
        if wid not in self.workbooks:
            raise KeyError(wid)
        return self.workbooks[wid]

    def list_all(self) -> list[StoredWorkbook]:
        return list(self.workbooks.values())


# ── Request models ──────────────────────────────────────────────────────────


class RiskRequest(BaseModel):
    equity_value_eur_m: float = Field(gt=0)
    equity_volatility: float = Field(gt=0)
    debt_face_value_eur_m: float = Field(gt=0)
    risk_free_rate: float = 0.039
    horizon_years: float = 1.0
    lgd: float = 0.45
    eir: float = 0.05
    maturity_years: int = 5
    days_past_due: int = 0
    counterparty: Optional[str] = None


# ── App factory ─────────────────────────────────────────────────────────────


def create_app(session_dir: Optional[Path] = None) -> FastAPI:
    app = FastAPI(
        title="ModelForge Web",
        description="Bulge-tier Excel model factory — HTTP surface.",
        version="0.5.8",
    )
    store = WorkbookStore(session_dir=session_dir)

    # ── Index
    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        rows = "\n".join(
            f"<tr><td><code>{w.workbook_id}</code></td>"
            f"<td>{w.original_name}</td>"
            f"<td>{len(w.sheet_names)}</td>"
            f"<td><code>{w.primary_output_ref or '—'}</code></td>"
            f"<td><a href='/workbook/{w.workbook_id}/view'>view</a> · "
            f"<a href='/workbook/{w.workbook_id}/dossier'>dossier</a> · "
            f"<a href='/workbook/{w.workbook_id}/drift'>drift</a></td></tr>"
            for w in sorted(store.list_all(), key=lambda x: x.original_name)
        )
        return _INDEX_HTML.replace("__ROWS__", rows or
                                    "<tr><td colspan='5'><i>(no uploads yet)</i></td></tr>")

    # ── Upload
    @app.post("/upload")
    async def upload(file: UploadFile = File(...)) -> dict:
        content = await file.read()
        if not content:
            raise HTTPException(400, "empty file")
        if not (file.filename or "").lower().endswith(".xlsx"):
            raise HTTPException(400, "only .xlsx accepted")
        try:
            stored = store.add(content, file.filename or "upload.xlsx")
        except Exception as e:
            raise HTTPException(400, f"failed to parse workbook: {e}")
        return {
            "workbook_id": stored.workbook_id,
            "original_name": stored.original_name,
            "sheet_names": stored.sheet_names,
            "primary_output_ref": stored.primary_output_ref,
            "reproducibility": stored.reproducibility,
        }

    # ── JSON metadata
    @app.get("/workbook/{wid}")
    def get_workbook(wid: str) -> dict:
        try:
            stored = store.get(wid)
        except KeyError:
            raise HTTPException(404, "workbook not found")
        return {
            "workbook_id": stored.workbook_id,
            "original_name": stored.original_name,
            "sheet_names": stored.sheet_names,
            "primary_output_ref": stored.primary_output_ref,
            "reproducibility": stored.reproducibility,
        }

    # ── HTML view
    @app.get("/workbook/{wid}/view", response_class=HTMLResponse)
    def view_workbook(wid: str) -> str:
        try:
            stored = store.get(wid)
        except KeyError:
            raise HTTPException(404, "workbook not found")
        sheets_html = "\n".join(f"<li>{s}</li>" for s in stored.sheet_names)
        repro_rows = "\n".join(
            f"<tr><td>{k}</td><td><code>{v}</code></td></tr>"
            for k, v in stored.reproducibility.items()
        )
        return _VIEW_HTML.replace("__ID__", stored.workbook_id)\
                        .replace("__NAME__", stored.original_name)\
                        .replace("__PRIMARY__", stored.primary_output_ref or "—")\
                        .replace("__SHEETS__", sheets_html)\
                        .replace("__REPRO__", repro_rows or
                                 "<tr><td colspan='2'>(no repro block)</td></tr>")

    # ── Dossier
    @app.get("/workbook/{wid}/dossier")
    def get_dossier(wid: str) -> FileResponse:
        from modelforge.dossier import generate_dossier
        try:
            stored = store.get(wid)
        except KeyError:
            raise HTTPException(404, "workbook not found")
        pdf = stored.path.with_suffix(".dossier.pdf")
        if not pdf.exists():
            generate_dossier(stored.path, pdf)
        return FileResponse(pdf, media_type="application/pdf",
                            filename=f"{stored.original_name}.dossier.pdf")

    # ── Drift
    @app.get("/workbook/{wid}/drift")
    def check_drift_endpoint(wid: str) -> dict:
        from modelforge.drift import check_drift
        try:
            stored = store.get(wid)
        except KeyError:
            raise HTTPException(404, "workbook not found")
        rep = check_drift(stored.path)
        return {
            "workbook_id": wid,
            "checked": rep.checked_drivers,
            "flagged": rep.n_flagged,
            "clean": rep.clean,
            "items": [
                {
                    "driver": i.driver_name, "assumed": i.assumed_value,
                    "current": i.current_value, "delta_bps": i.delta_bps,
                    "delta_rel": i.delta_rel, "flagged": i.flagged,
                    "source": i.source, "kind": i.kind,
                }
                for i in rep.items
            ],
            "missing": rep.missing_drivers,
        }

    # ── Diff
    @app.get("/diff", response_class=HTMLResponse)
    def diff_endpoint(a: str = Query(...), b: str = Query(...)) -> str:
        from modelforge.diff import compute_diff, render_html
        try:
            wa, wb_ = store.get(a), store.get(b)
        except KeyError as e:
            raise HTTPException(404, f"workbook not found: {e}")
        res = compute_diff(wa.path, wb_.path)
        return render_html(res)

    # ── Risk
    @app.post("/risk")
    def risk_endpoint(req: RiskRequest) -> dict:
        from modelforge.risk import (
            ECLInputs, MertonInputs, calibrate_pd_kmv, compute_ecl,
            solve_merton,
        )
        merton = solve_merton(MertonInputs(
            equity_value=req.equity_value_eur_m,
            equity_volatility=req.equity_volatility,
            debt_face_value=req.debt_face_value_eur_m,
            risk_free_rate=req.risk_free_rate,
            horizon_years=req.horizon_years,
        ))
        kmv_pd = calibrate_pd_kmv(merton.distance_to_default)
        pd_ = max(merton.probability_of_default, kmv_pd)
        ecl_inp = ECLInputs(
            exposure_at_default_eur_m=req.debt_face_value_eur_m,
            loss_given_default=req.lgd,
            effective_interest_rate=req.eir,
            maturity_years=req.maturity_years,
            pd_curve_annual=[pd_] * req.maturity_years,
            current_pd_12m=pd_, origination_pd_12m=pd_,
            days_past_due=req.days_past_due,
        )
        ecl = compute_ecl(ecl_inp, req.counterparty or "counterparty")
        return {
            "counterparty": req.counterparty,
            "merton": {
                "asset_value": merton.asset_value,
                "asset_volatility": merton.asset_volatility,
                "distance_to_default": merton.distance_to_default,
                "pd": merton.probability_of_default,
                "converged": merton.converged,
            },
            "kmv_pd": kmv_pd,
            "ecl": {
                "stage": ecl.stage.value,
                "ecl_12_month_eur_m": ecl.ecl_12_month_eur_m,
                "ecl_lifetime_eur_m": ecl.ecl_lifetime_eur_m,
                "ecl_eur_m": ecl.ecl_eur_m,
                "implied_rate": ecl.implied_rate_pct,
                "notes": ecl.notes,
            },
        }

    # ── Health
    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "workbooks": len(store.workbooks)}

    # Expose for tests / CLI
    app.state.store = store
    return app


# ── HTML templates (inline) ─────────────────────────────────────────────────

_INDEX_HTML = """<!doctype html>
<html><head><meta charset='utf-8'><title>ModelForge</title>
<style>
body{font-family:-apple-system,Segoe UI,Helvetica,sans-serif;padding:2rem;max-width:1100px;margin:0 auto;color:#222}
h1{color:#1F3864;border-bottom:2px solid #1F3864;padding-bottom:0.5rem}
table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:0.9rem}
th{background:#1F3864;color:#fff;text-align:left;padding:0.5rem}
td{border:1px solid #ddd;padding:0.5rem;vertical-align:top}
tr:nth-child(even){background:#f4f6fa}
form{padding:1rem;background:#f4f6fa;border-radius:4px;margin:1rem 0}
button{background:#1F3864;color:#fff;border:0;padding:0.5rem 1rem;cursor:pointer;border-radius:3px}
code{background:#f0f0f0;padding:0.1rem 0.3rem;border-radius:2px;font-family:Consolas,monospace}
a{color:#2F5496}
</style></head><body>
<h1>ModelForge Web</h1>
<p>Bulge-tier Excel model factory — HTTP surface. Upload a <code>.xlsx</code>
built by <code>modelforge build</code> to render metadata, export a dossier,
check drift, or diff against another version.</p>
<form action='/upload' method='post' enctype='multipart/form-data'>
  <input type='file' name='file' accept='.xlsx' required />
  <button type='submit'>Upload workbook</button>
</form>
<h2>Uploaded workbooks</h2>
<table><thead><tr>
  <th>ID</th><th>Name</th><th>Sheets</th><th>Primary output</th><th>Actions</th>
</tr></thead><tbody>
__ROWS__
</tbody></table>
<p><small>API endpoints: <code>POST /upload</code>,
<code>GET /workbook/&lt;id&gt;</code>, <code>/dossier</code>, <code>/drift</code>,
<code>GET /diff?a=&amp;b=</code>, <code>POST /risk</code>.</small></p>
</body></html>
"""


_VIEW_HTML = """<!doctype html>
<html><head><meta charset='utf-8'><title>ModelForge — __NAME__</title>
<style>
body{font-family:-apple-system,Segoe UI,Helvetica,sans-serif;padding:2rem;max-width:1000px;margin:0 auto}
h1{color:#1F3864;border-bottom:2px solid #1F3864;padding-bottom:0.5rem}
h2{color:#2F5496;margin-top:2rem}
table{border-collapse:collapse;width:100%;font-size:0.9rem}
th{background:#1F3864;color:#fff;text-align:left;padding:0.5rem}
td{border:1px solid #ddd;padding:0.4rem}
tr:nth-child(even){background:#f4f6fa}
code{background:#f0f0f0;padding:0.1rem 0.3rem;border-radius:2px;font-family:Consolas,monospace}
ul{line-height:1.8}
.actions a{display:inline-block;padding:0.4rem 0.8rem;margin-right:0.5rem;background:#2F5496;color:#fff;text-decoration:none;border-radius:3px}
</style></head><body>
<h1>__NAME__</h1>
<p>ID: <code>__ID__</code> · Primary output: <code>__PRIMARY__</code></p>
<p class='actions'>
  <a href='/workbook/__ID__/dossier'>Download dossier PDF</a>
  <a href='/workbook/__ID__/drift'>Check drift (JSON)</a>
  <a href='/'>← back</a>
</p>
<h2>Sheets</h2>
<ul>__SHEETS__</ul>
<h2>Reproducibility</h2>
<table><thead><tr><th>Field</th><th>Value</th></tr></thead>
<tbody>__REPRO__</tbody></table>
</body></html>
"""
