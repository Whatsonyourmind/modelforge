"""Certified deck pipeline — workbook → Facts → compose → render → stamp.

The load-bearing integration between the model factory and the deck engine:

    spec.yaml ──(modelforge build: trust/moat/styler/determinism/manifest)──▶
    workbook.xlsx + manifest ──(adapter: verify → certify → extract)──▶
    DealFacts/TeaserFacts ──(compose_ic_memo / compose_teaser)──▶
    Presentation IR  + mandatory "Certification & Red Flags" appendix ──▶
    layout → PPTX render → deterministic stamp (hashes in core props)

Fail-closed: the adapter refuses uncertified/tampered workbooks, so a deck
can only ever exist for a workbook whose bytes verify against its manifest
and whose audit verdict is CERTIFIED. The rendered .pptx embeds
``spec_sha256`` + ``workbook_sha256`` in its core properties and is
byte-deterministic for a given workbook.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from modelforge.deck.adapter import (
    DeckAdapterError,
    SUPPORTED_DECK_TEMPLATES,
    WorkbookFacts,
    adapt_workbook,
)
from modelforge.deck.determinism import stamp_pptx

__all__ = [
    "DeckBuildResult",
    "DeckAdapterError",
    "SUPPORTED_DECK_TYPES",
    "SUPPORTED_DECK_TEMPLATES",
    "build_certification_slide",
    "build_deck_from_workbook",
    "render_presentation_to_bytes",
]

SUPPORTED_DECK_TYPES: tuple[str, ...] = ("ic_memo", "teaser")


@dataclass
class DeckBuildResult:
    """What the pipeline hands back to the CLI / MCP tool."""

    pptx_path: Path
    deck_type: str
    theme: str
    slide_count: int
    workbook: Path
    workbook_sha256: str
    spec_sha256: str
    audit_verdict: str
    template: str
    source_refs: dict[str, str] = field(default_factory=dict)
    red_flag_count: int = 0

    def summary(self) -> dict[str, Any]:
        return {
            "pptx": str(self.pptx_path),
            "deck_type": self.deck_type,
            "theme": self.theme,
            "slides": self.slide_count,
            "workbook": str(self.workbook),
            "workbook_sha256": self.workbook_sha256,
            "spec_sha256": self.spec_sha256,
            "audit_verdict": self.audit_verdict,
            "template": self.template,
            "red_flags": self.red_flag_count,
            "source_cells": self.source_refs,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Certification & Red Flags appendix (mandatory final slide)
# ─────────────────────────────────────────────────────────────────────────────


def build_certification_slide(wf: WorkbookFacts):
    """The mandatory final slide: certify verdict, hashes, red flags.

    Uses the ``table_slide`` type whose layout pattern positions exactly the
    three elements emitted here (title + table_area + footnote) — the Trust
    Layer red-flag entries are folded into the table so nothing is dropped
    by the layout engine.
    """
    from modelforge.deck.ir.elements.data import TableContent, TableElement
    from modelforge.deck.ir.elements.text import (
        FootnoteContent,
        FootnoteElement,
        HeadingContent,
        HeadingElement,
    )
    from modelforge.deck.ir.slides.universal import TableSlideSlide

    manifest = wf.manifest
    rows: list[list[Any]] = [
        ["Certification verdict", wf.audit_verdict],
        ["Formula-error cells", str(wf.audit_summary.get("error_cells", 0))],
        ["Workbook", Path(manifest.workbook).name],
        ["Workbook SHA-256", manifest.workbook_sha256],
        ["Spec SHA-256", manifest.spec_sha256],
        ["Template", wf.template],
        ["ModelForge version", manifest.modelforge_version],
    ]

    if wf.red_flags:
        for i, rf in enumerate(wf.red_flags, start=1):
            detail = f"[{rf['severity']}] {rf['rule']}"
            if rf.get("cell"):
                detail += f" @ {rf['cell']}"
            if rf.get("message"):
                detail += f" — {rf['message']}"
            rows.append([f"Red flag {i}", detail])
    else:
        rows.append(["Trust Layer red flags", "none raised (ALL CLEAR)"])

    lineage_lines = "; ".join(
        f"{k}={v}" for k, v in sorted(wf.source_refs.items())
    )
    elements = [
        HeadingElement(content=HeadingContent(text="Certification & Red Flags")),
        TableElement(content=TableContent(headers=["Field", "Value"], rows=rows)),
        FootnoteElement(
            content=FootnoteContent(
                text=(
                    f"spec_sha256={manifest.spec_sha256}; "
                    f"workbook_sha256={manifest.workbook_sha256} — verify "
                    f"with `modelforge verify` against the build manifest."
                )
            )
        ),
    ]
    return TableSlideSlide(
        elements=elements,
        speaker_notes=(
            "Every numeric fact on this deck was extracted from the "
            "certified workbook. Source cells: " + (lineage_lines or "n/a")
        ),
    )


# ─────────────────────────────────────────────────────────────────────────────
# Per-slide lineage stamping (source cell refs in speaker notes)
# ─────────────────────────────────────────────────────────────────────────────

# Slide identity is owned by the composers in modelforge.deck.compose. The
# composers may OMIT data-less slides (comps without comps, sensitivity
# without a grid), so the lineage map is keyed by (slide_type, occurrence)
# rather than by index — speaker notes always cite exactly the facts the
# slide they are attached to displays.
_IC_MEMO_SLIDE_FACTS: dict[tuple[str, int], list[str]] = {
    ("title_slide", 0): [],
    # exec summary (first key_message)
    ("key_message", 0): ["total_uses", "sponsor_equity", "irr_strategic",
                         "exit_year"],
    ("deal_overview", 0): ["deal_name", "total_uses", "sponsor_equity",
                           "senior_debt", "mezz_debt", "rcf_drawn",
                           "exit_year"],
    ("investment_thesis", 0): ["entry_ev", "irr_strategic", "moic_strategic",
                               "ebitda_last_fy"],
    ("stats_callout", 0): ["irr_strategic", "moic_strategic"],  # returns
    ("waterfall_chart", 0): ["sponsor_equity", "exit_ev", "exit_net_debt",
                             "exit_equity"],
    ("capital_structure", 0): ["senior_debt", "mezz_debt", "rcf_drawn",
                               "mgmt_rollover", "sponsor_equity"],
    ("comp_table", 0): [],     # comps (composed only when comps provided)
    ("chart_slide", 0): [],    # sensitivity (composed only when grid provided)
    ("table_slide", 0): [],    # sensitivity plain-table fallback
    ("risk_matrix", 0): [],
    ("two_column_text", 0): ["covenant_breaches"],  # risks & mitigants
    # recommendation (second key_message)
    ("key_message", 1): ["sponsor_equity"],
}

_TEASER_SLIDE_FACTS: dict[tuple[str, int], list[str]] = {
    ("title_slide", 0): [],
    # exec summary (first key_message)
    ("key_message", 0): ["entry_ev", "revenue_last_fy", "ebitda_last_fy",
                         "sponsor_equity"],
    ("deal_overview", 0): ["revenue_last_fy", "ebitda_last_fy"],  # snapshot
    ("investment_thesis", 0): ["irr_strategic", "moic_strategic",
                               "entry_ev"],  # highlights
    ("timeline", 0): [],       # process
    ("key_message", 1): [],    # contact
}


def _stamp_lineage_notes(presentation, wf: WorkbookFacts, deck_type: str) -> None:
    """Append source-cell refs to each slide's speaker notes (in place).

    Slides are matched by (slide_type, occurrence) so the notes stay attached
    to the right slide even when the composer omits data-less slides.
    """
    fact_map = _IC_MEMO_SLIDE_FACTS if deck_type == "ic_memo" else _TEASER_SLIDE_FACTS
    wb_tag = (
        f"Certified workbook {wf.workbook.name} "
        f"(sha256 {wf.manifest.workbook_sha256[:12]}…)"
    )
    occurrence_counter: dict[str, int] = {}
    for slide in presentation.slides:
        slide_type = slide.slide_type
        if hasattr(slide_type, "value"):
            slide_type = slide_type.value
        occ = occurrence_counter.get(slide_type, 0)
        occurrence_counter[slide_type] = occ + 1

        keys = fact_map.get((slide_type, occ), [])
        refs = [
            f"{k}={wf.facts[k].ref}" for k in keys if k in wf.facts
        ]
        note = f"Source: {wb_tag}."
        if refs:
            note += " Source cells: " + "; ".join(refs) + "."
        existing = slide.speaker_notes or ""
        slide.speaker_notes = (existing + "\n" + note).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────


def render_presentation_to_bytes(presentation) -> bytes:
    """Presentation IR → .pptx bytes (layout + render, no disk I/O)."""
    from modelforge.deck.layout import LayoutEngine
    from modelforge.deck.layout.text_measurer import TextMeasurer
    from modelforge.deck.rendering import PptxRenderer
    from modelforge.deck.themes.registry import ThemeRegistry

    theme_registry = ThemeRegistry()
    engine = LayoutEngine(TextMeasurer(), theme_registry)
    layout_results = engine.layout_presentation(presentation)
    theme = theme_registry.get_theme(
        presentation.theme, getattr(presentation, "brand_kit", None)
    )
    return PptxRenderer().render(presentation, layout_results, theme)


def _validate_theme(theme: str) -> None:
    from modelforge.deck.themes.registry import ThemeRegistry

    registry = ThemeRegistry()
    try:
        registry.load_theme(theme)
    except (FileNotFoundError, ValueError) as e:
        available = ", ".join(t["id"] for t in registry.list_themes())
        raise DeckAdapterError(
            f"Unknown theme {theme!r}. Available themes: {available}."
        ) from e


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────


def build_deck_from_workbook(
    xlsx_path: Path | str,
    deck_type: str = "ic_memo",
    theme: Optional[str] = None,
    out_path: Optional[Path | str] = None,
    manifest_path: Optional[Path | str] = None,
) -> DeckBuildResult:
    """Certified workbook → rendered, hash-stamped .pptx deck.

    Fail-closed chain (any failure raises :class:`DeckAdapterError`):
    manifest verify → CERTIFIED audit → supported-template extraction →
    compose (+ mandatory Certification & Red Flags appendix) → render →
    deterministic stamp (zip mtimes + core props derived from
    ``workbook_sha256``; both SHAs embedded in core-property keywords).
    """
    if deck_type not in SUPPORTED_DECK_TYPES:
        raise DeckAdapterError(
            f"deck type {deck_type!r} not supported; choose one of "
            f"{list(SUPPORTED_DECK_TYPES)}."
        )
    if theme is not None:
        _validate_theme(theme)

    wf = adapt_workbook(xlsx_path, manifest_path=manifest_path)

    if deck_type == "ic_memo":
        from modelforge.deck.compose import compose_ic_memo

        presentation = compose_ic_memo(wf.deal_facts())
    else:
        from modelforge.deck.compose import compose_teaser

        presentation = compose_teaser(wf.teaser_facts())

    _stamp_lineage_notes(presentation, wf, deck_type)

    # Mandatory final slide + optional theme override. Rebuild through the
    # model constructor so the appended slide is validated like the rest.
    cert_slide = build_certification_slide(wf)
    presentation = presentation.model_copy(
        update={
            "slides": [*presentation.slides, cert_slide],
            **({"theme": theme} if theme else {}),
        }
    )

    try:
        pptx_bytes = render_presentation_to_bytes(presentation)
    except ImportError as e:
        raise DeckAdapterError(
            "deck rendering requires the deck extras: "
            "pip install 'modelforge-finance[deck]' "
            f"(missing dependency: {getattr(e, 'name', None) or e})"
        ) from e
    except Exception as e:
        raise DeckAdapterError(
            f"Deck rendering failed after a successful adapt/compose: {e!r}"
        ) from e

    xlsx = Path(xlsx_path)
    if out_path is None:
        out = xlsx.with_name(f"{xlsx.stem}_{deck_type}.pptx")
    else:
        out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(pptx_bytes)

    title = presentation.metadata.title if presentation.metadata else None
    stamp_pptx(
        out,
        workbook_sha256=wf.manifest.workbook_sha256,
        spec_sha256=wf.manifest.spec_sha256,
        title=title,
    )

    return DeckBuildResult(
        pptx_path=out,
        deck_type=deck_type,
        theme=presentation.theme,
        slide_count=len(presentation.slides),
        workbook=xlsx,
        workbook_sha256=wf.manifest.workbook_sha256,
        spec_sha256=wf.manifest.spec_sha256,
        audit_verdict=wf.audit_verdict,
        template=wf.template,
        source_refs=wf.source_refs,
        red_flag_count=len(wf.red_flags),
    )
