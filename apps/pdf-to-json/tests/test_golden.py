"""Characterization (golden) test for OCSTransformer.

Pins the transformer's end-to-end behaviour on real sample PDFs. Any change to
observable output surfaces immediately — the safety net for the Phase 3b
god-file decomposition (move-only refactor). Regenerate intentionally with
`uv run python scripts/gen_golden.py` and review the diff.
"""
import json
from pathlib import Path

import pytest

from jd_pdf_to_json.transformers.ocs_transformer import OCSTransformer

HERE = Path(__file__).resolve().parent
PDFS = HERE / "fixtures" / "sample_pdfs"
GOLD = HERE / "fixtures" / "golden"

_PDFS = sorted(PDFS.glob("*.pdf"))


@pytest.mark.parametrize("pdf", _PDFS, ids=[p.stem for p in _PDFS])
def test_transform_matches_golden(pdf: Path) -> None:
    doc = OCSTransformer().transform({"file_path": str(pdf)})
    got = json.loads(json.dumps(doc.model_dump(), ensure_ascii=False, sort_keys=True))
    want = json.loads((GOLD / (pdf.stem + ".json")).read_text(encoding="utf-8"))
    assert got == want
