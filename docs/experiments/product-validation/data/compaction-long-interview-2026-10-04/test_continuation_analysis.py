"""Native compaction can return user text as content blocks rather than a string."""

from continuation_analysis import prefix_rows, visible_interview_events

EVENTS = [{"event_id": "e002", "employee_text": "每天15–20張進貨單。"}]


def test_canonical_user_content_is_still_visible_original_text():
    items = [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "每天15–20張進貨單。"}],
        }
    ]
    assert visible_interview_events(items, EVENTS)["standalone_user"] == ["e002"]


def test_app_copy_is_visible_but_not_a_standalone_employee_input():
    items = [
        {
            "role": "user",
            "content": '{"data_kind":"historical_interview","messages":[{"text":"每天15–20張進貨單。"}]}',
        }
    ]
    observed = visible_interview_events(items, EVENTS)
    assert observed["standalone_user"] == []
    assert observed["app_copy"] == ["e002"]


def test_assistant_echo_does_not_count_as_employee_original():
    items = [{"role": "assistant", "content": "每天15–20張進貨單。"}]
    assert visible_interview_events(items, EVENTS)["standalone_user"] == []


def test_opaque_compaction_is_unknown_not_evidence_of_visible_original():
    items = [
        {"type": "compaction", "encrypted_content": {"sha256": "opaque", "bytes": 9}}
    ]
    result = visible_interview_events(items, EVENTS)
    assert result["standalone_user"] == []
    assert result["app_copy"] == []
    assert result["opaque_state_present"] is True


def test_completed_method_counts_reused_compaction_but_not_failed_generation():
    compacted = [{"type": "compaction", "encrypted_content": "opaque"}]
    common = {
        "arm": "compaction_hierarchical_memory",
        "phase": "consultant",
        "event_id": "e052",
        "turn": 52,
    }
    rows = [
        {
            **common,
            "event": "request",
            "path": "/v1/responses/input_tokens",
            "payload": {},
        },
        {
            **common,
            "event": "response",
            "path": "/v1/responses/compact",
            "payload": {"output": compacted},
        },
        {**common, "event": "request", "path": "/v1/responses", "payload": {}},
        {
            **common,
            "event": "response",
            "path": "/v1/responses/compact",
            "payload": {"output": []},
        },
    ]
    assert prefix_rows(rows, compacted) == rows[:2]


def test_public_opaque_hash_still_marks_unknown_compaction_state():
    items = [
        {"type": "compaction", "encrypted_sha256": "opaque", "encrypted_length": 9}
    ]
    assert visible_interview_events(items, EVENTS)["opaque_state_present"] is True
