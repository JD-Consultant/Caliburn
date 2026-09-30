"""Only model outcome errors are terminal; public exceptions contain no model text."""

import traceback

import pytest

from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_analysis.results import AnalysisOutcomeError, parse_outcome


@pytest.mark.parametrize(
    "text",
    ["PRIVATE_INVALID_JSON", '{"status":"complete","unexpected":"PRIVATE_VALUE"}'],
)
def test_malformed_outcome_has_safe_typed_reason(text: str) -> None:
    with pytest.raises(AnalysisOutcomeError) as captured:
        parse_outcome(text, MemoryLayer.WORK_UNDERSTANDING)
    assert captured.value.reason_code == "analysis_outcome_malformed"
    formatted = "".join(traceback.format_exception(captured.value))
    assert "PRIVATE_INVALID_JSON" not in formatted
    assert "PRIVATE_VALUE" not in formatted


def test_b1_rework_final_is_not_allowed_outcome() -> None:
    text = (
        '{"status":"needs_situation","gaps":[{"target_title":"盤點",'
        '"question":"頻率？","needed_clarification":"確認頻率","interview_sequences":[2]}]}'
    )
    with pytest.raises(AnalysisOutcomeError) as captured:
        parse_outcome(text, MemoryLayer.WORK_SITUATION)
    assert captured.value.reason_code == "analysis_outcome_not_allowed"
