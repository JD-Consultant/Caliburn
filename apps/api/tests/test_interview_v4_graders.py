from evals.interview_v4.contracts import TranscriptTurn
from evals.interview_v4.graders import grade_evidence_quotes, grade_projection_grounding


TRANSCRIPT = (
    TranscriptTurn(seq=1, role="consultant", text="你做什麼？"),
    TranscriptTurn(seq=2, role="employee", text="我每月用 Excel 對帳。"),
)


def test_quote_grader_requires_employee_turn_and_exact_quote():
    good = [{
        "evidence_id": "ev1",
        "source": {"turn_id": 2, "speaker": "employee", "quote": "每月用 Excel 對帳"},
    }]
    result = grade_evidence_quotes(good, TRANSCRIPT)
    assert result.passed is True and result.score == 1.0

    bad = [{
        "evidence_id": "ev2",
        "source": {"turn_id": 1, "speaker": "consultant", "quote": "你做什麼"},
    }]
    result = grade_evidence_quotes(bad, TRANSCRIPT)
    assert result.passed is False
    assert "non_employee_turn" in result.details[0]["reasons"]
    assert "source_speaker_not_employee" in result.details[0]["reasons"]


def test_no_evidence_or_projection_is_not_applicable_not_perfect():
    quote = grade_evidence_quotes([], TRANSCRIPT)
    assert quote.applicable is False and quote.passed is None and quote.score is None

    projection = grade_projection_grounding({}, TRANSCRIPT, set())
    assert projection.applicable is False
    assert projection.passed is None and projection.score is None


def test_projection_hard_fails_on_unsupported_quote():
    document = {
        "ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [{
            "_tid": "t1",
            "competency_blocks": [{"skills": [{
                "_id": "s1",
                "name": "虛構技能",
                "_pending": {
                    "op": "add",
                    "src": {"quote": {"turn_id": 2, "text": "我有高階證照"}}
                }
            }]}]
        }]}]}
    }
    result = grade_projection_grounding(document, TRANSCRIPT, set())
    assert result.passed is False
    assert result.severity == "critical"
    assert result.reason == "unsupported_projection_count=1"
