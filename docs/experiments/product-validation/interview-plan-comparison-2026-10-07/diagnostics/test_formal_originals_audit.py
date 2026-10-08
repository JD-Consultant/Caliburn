"""Source identity and literal-body counterexamples; no I/O or provider."""

import pytest
from formal_originals_audit import verify_turn


def fixture():
    command = {"command_id": "command", "text": "相同原話\n"}
    accepted = {"command_id": "command", "source_id": "current", "execution_id": "new-turn"}
    old = {
        "source_id": "old",
        "speaker": "employee",
        "interview_text": command["text"],
        "interview_sequence": 1,
        "execution_id": None,
    }
    current = {**old, "source_id": "current", "interview_sequence": 3}
    return command, accepted, [old, current]


def test_old_same_text_cannot_replace_current_accepted_source():
    command, accepted, messages = fixture()
    with pytest.raises(ValueError, match="current accepted source"):
        verify_turn(command, accepted, messages[:1])


def test_current_source_is_checked_and_old_same_text_remains_historical():
    command, accepted, messages = fixture()
    witness = verify_turn(command, accepted, messages)
    assert witness["accepted_source_id"] == "current"
    assert witness["earlier_same_text_source_ids"] == ["old"]
    assert witness["formal_interview_sequence"] == 3


def test_literal_body_whitespace_is_not_normalized():
    command, accepted, messages = fixture()
    messages[-1]["interview_text"] = "相同原話"
    with pytest.raises(ValueError):
        verify_turn(command, accepted, messages)


def test_accepted_command_mismatch_is_rejected():
    command, accepted, messages = fixture()
    accepted["command_id"] = "other-command"
    with pytest.raises(ValueError, match="command"):
        verify_turn(command, accepted, messages)


def test_assistant_or_duplicate_current_source_is_rejected():
    command, accepted, messages = fixture()
    messages[-1]["speaker"] = "consultant"
    with pytest.raises(ValueError, match="employee"):
        verify_turn(command, accepted, messages)
    messages[-1]["speaker"] = "employee"
    with pytest.raises(ValueError, match="exactly once"):
        verify_turn(command, accepted, messages + [messages[-1]])
