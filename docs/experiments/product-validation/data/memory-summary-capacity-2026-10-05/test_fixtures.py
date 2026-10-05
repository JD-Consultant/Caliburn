"""No provider calls: prevent source leakage and invalid research references."""

import json

import pytest
from fixtures import capture_batches, reader_context, validate_references


def messages():
    return [
        {"interview_sequence": n, "speaker": "employee", "text": f"source-{n}"}
        for n in range(1, 106)
    ]


def material():
    return {
        "messages": messages(),
        "maps": {"work_situation": {"items": []}, "work_understanding": {"items": []}},
        "objects": {"work_situation:接貨": {}},
        "jd_draft": {"text": "Do not leak this draft"},
    }


def test_capture_consumes_only_1_to_104_once_with_prior_question():
    batches = capture_batches(messages())
    assert [
        (b[0]["interview_sequence"], b[-1]["interview_sequence"]) for b in batches
    ] == [(1, 24), (25, 56), (57, 88), (89, 104)]
    assert [m["interview_sequence"] for b in batches for m in b] == list(range(1, 105))


def test_capture_refuses_missing_or_reordered_sources():
    with pytest.raises(ValueError):
        capture_batches(messages()[1:])
    source = messages()
    source[20], source[21] = source[21], source[20]
    with pytest.raises(ValueError):
        capture_batches(source)


def test_memory_starts_with_maps_and_one_recent_message_not_body_or_jd():
    context = reader_context(material(), "memory", "核對工作")
    data = json.loads(context[0]["content"])
    assert set(data) == {
        "notice",
        "recent_interview",
        "work_situation_map",
        "work_understanding_map",
    }
    assert [m["interview_sequence"] for m in data["recent_interview"]] == [105]
    assert context[1] == {"role": "user", "content": "核對工作"}


def test_flat_receives_entire_summary_without_early_interview_preload():
    context = reader_context(material(), "flat", "核對工作", "完整摘要\n保留數值")
    data = json.loads(context[0]["content"])
    assert data["work_summary"] == "完整摘要\n保留數值"
    assert set(data) == {"notice", "recent_interview", "work_summary"}
    with pytest.raises(ValueError):
        reader_context(material(), "flat", "核對工作", " ")


def test_empty_reference_list_cannot_be_a_supported_submission():
    assert validate_references(material(), "flat", [])["status"] == "rejected"


def test_reference_validation_rejects_future_and_unavailable_memory():
    raw = {"kind": "interview", "interview_sequence": 94, "target_title": None}
    memory = {
        "kind": "work_situation",
        "interview_sequence": None,
        "target_title": "接貨",
    }
    assert (
        validate_references(material(), "memory", [raw, memory])["status"] == "accepted"
    )
    assert validate_references(material(), "flat", [raw])["status"] == "accepted"
    assert validate_references(material(), "flat", [memory])["status"] == "rejected"
    assert (
        validate_references(material(), "memory", [{**raw, "interview_sequence": 106}])[
            "status"
        ]
        == "rejected"
    )
