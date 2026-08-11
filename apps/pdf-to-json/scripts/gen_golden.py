"""Generate golden transform outputs from sample PDFs.

Run once to establish the behaviour baseline, or re-run when behaviour changes
*intentionally* (then review the golden diff). Used by tests/test_golden.py as
the characterization net for the transformer decomposition (Phase 3b).

Note: OCSTransformer.transform() only reads raw_data['file_path'] (it re-opens the
PDF itself), so we pass that directly — characterizing the transformer end-to-end.
"""
import json
from pathlib import Path

from jd_pdf_to_json.transformers.ocs_transformer import OCSTransformer

HERE = Path(__file__).resolve().parent.parent
PDFS = HERE / "tests" / "fixtures" / "sample_pdfs"
GOLD = HERE / "tests" / "fixtures" / "golden"


def main() -> None:
    GOLD.mkdir(parents=True, exist_ok=True)
    tx = OCSTransformer()
    for pdf in sorted(PDFS.glob("*.pdf")):
        doc = tx.transform({"file_path": str(pdf)})
        out = GOLD / (pdf.stem + ".json")
        out.write_text(
            json.dumps(doc.model_dump(), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print("wrote", out.name)


if __name__ == "__main__":
    main()
