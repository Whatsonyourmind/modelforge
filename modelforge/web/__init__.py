"""Web SaaS thin layer — v0.5 US-018 MVP.

FastAPI single-file app exposing ModelForge CLI functionality over
HTTP:

    POST /upload            → accept .xlsx, store by content hash,
                              return {workbook_id, primary_output,
                              sheet_names, ...}
    GET  /workbook/{id}     → JSON metadata for an uploaded workbook
    GET  /workbook/{id}/view → HTML render of metadata + primary output
    GET  /workbook/{id}/dossier → PDF audit dossier
    GET  /workbook/{id}/drift   → JSON drift report vs current feeds
    GET  /diff?a=<id1>&b=<id2>  → HTML diff page
    POST /risk              → one-shot Merton + KMV + IFRS 9 ECL
    GET  /                  → simple index HTML with upload form

Designed for local / boutique multi-user use. In-memory registry is
file-system-backed (workbooks persisted under a session directory) so
state survives reloads. For production multi-tenant deployment, swap
the WorkbookStore backend for Postgres + S3 per v1.0 US-022.
"""

from modelforge.web.app import create_app

__all__ = ["create_app"]
