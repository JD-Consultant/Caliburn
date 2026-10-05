"""The report checker must reject a mistyped experimental table."""

import pytest
from verify_evidence import REPORT_DIR, check_supplemental_evidence


@pytest.mark.parametrize(
    ("original", "mistyped"),
    (
        ("| 前段 | 1 | 159,812 | 10,758 |", "| 前段 | 1 | 159,813 | 10,758 |"),
        ("| 原門檻 | 1 | 8／0 | 27,605 |", "| 原門檻 | 1 | 8／0 | 27,606 |"),
        ("| 合計 | 163 |", "| 合計 | 164 |"),
    ),
)
def test_supplemental_table_transcription_error_is_detected(original, mistyped):
    report = (REPORT_DIR / "report.md").read_text(encoding="utf-8")
    assert original in report
    with pytest.raises(AssertionError):
        check_supplemental_evidence(report.replace(original, mistyped))
