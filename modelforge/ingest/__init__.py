"""ModelForge data-room ingestion pipeline.

Turns a directory of PDFs / XLSXs / CSVs into a validated ModelForge YAML
spec. Claude Opus handles classification + structured extraction; every
number traces back to a doc page via the Sources registry.

Public API (populated once pipeline module lands):
    from modelforge.ingest.pipeline import ingest, IngestionResult
"""
