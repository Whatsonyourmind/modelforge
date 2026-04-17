"""Tests for modelforge.dossier (US-009)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from modelforge.dossier import generate_dossier
from modelforge.templates import build_model

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def unitranche_built(tmp_path_factory):
    from modelforge.spec.unitranche import UnitrancheSpec
    p = ROOT / "examples" / "unitranche_cdmo.yaml"
    spec = UnitrancheSpec.model_validate(yaml.safe_load(p.read_bytes()))
    out = tmp_path_factory.mktemp("doss") / "u.xlsx"
    build_model(spec, out, spec_source_bytes=p.read_bytes(), spec_source_path=p)
    return out


def test_generates_pdf(unitranche_built, tmp_path):
    pdf = tmp_path / "test.pdf"
    result = generate_dossier(unitranche_built, pdf)
    assert result.exists()
    assert result.suffix == ".pdf"
    assert result.stat().st_size > 5000  # reasonable minimum


def test_pdf_header_is_valid(unitranche_built, tmp_path):
    pdf = tmp_path / "t.pdf"
    generate_dossier(unitranche_built, pdf)
    # PDF files start with "%PDF-"
    assert pdf.read_bytes()[:5] == b"%PDF-"


def test_default_output_path(unitranche_built):
    pdf = generate_dossier(unitranche_built)
    assert pdf.exists()
    assert pdf.suffix == ".pdf"
    assert "dossier" in pdf.name


def test_missing_workbook_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        generate_dossier(tmp_path / "nonexistent.xlsx")


def test_dossier_is_multi_page(unitranche_built, tmp_path):
    """A meaningful dossier must have content beyond the cover page.
    Rough proxy: size > 15 kB, which a single-page PDF won't reach."""
    pdf = tmp_path / "multi.pdf"
    generate_dossier(unitranche_built, pdf)
    assert pdf.stat().st_size > 15_000


@pytest.mark.parametrize("fname,model_type", [
    ("unitranche_cdmo.yaml", "unitranche"),
    ("credit_memo_cdmo.yaml", "credit_memo"),
    ("project_finance_solar.yaml", "project_finance"),
    ("three_statement_cdmo.yaml", "three_statement"),
    ("dcf_enel.yaml", "dcf"),
    ("merger_tim_iliad.yaml", "merger"),
    ("fairness_amplifon.yaml", "fairness"),
])
def test_dossier_on_template(fname, model_type, tmp_path):
    spec_path = ROOT / "examples" / fname
    if model_type == "unitranche":
        from modelforge.spec.unitranche import UnitrancheSpec as SC
    elif model_type == "credit_memo":
        from modelforge.spec.credit_memo import CreditMemoSpec as SC
    elif model_type == "project_finance":
        from modelforge.spec.project_finance import ProjectFinanceSpec as SC
    elif model_type == "three_statement":
        from modelforge.spec.three_statement import ThreeStatementSpec as SC
    elif model_type == "dcf":
        from modelforge.spec.dcf import DCFSpec as SC
    elif model_type == "merger":
        from modelforge.spec.merger import MergerSpec as SC
    elif model_type == "fairness":
        from modelforge.spec.fairness import FairnessSpec as SC
    spec = SC.model_validate(yaml.safe_load(spec_path.read_bytes()))
    xlsx = tmp_path / f"{model_type}.xlsx"
    build_model(spec, xlsx, spec_source_bytes=spec_path.read_bytes(),
                spec_source_path=spec_path)
    pdf = tmp_path / f"{model_type}.pdf"
    generate_dossier(xlsx, pdf)
    assert pdf.exists()
    assert pdf.stat().st_size > 5000
