"""Stored body compatibility and truthful operation-result reconstruction."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError
import pytest

from jd_relational.result_transport import ResultValidationError
from jd_relational.storage.receipts import SavedOperation, WriteObservation, body_for


def row(status="no_change"):
    base = uuid4()
    return {"document_id": "synthetic-doc", "operation_id": uuid4(), "request_digest": "a" * 64,
            "origin": "manual", "ai_run_id": None, "base_revision_id": base,
            "result_revision_id": base if status == "no_change" else uuid4() if status == "committed" else None,
            "status": status, "receipt": body_for("jd_set_text", status).model_dump(mode="json"),
            "created_at": datetime.now(timezone.utc)}


@pytest.mark.parametrize("status", ["committed", "no_change", "invalid_input", "target_missing", "stale_view",
                                    "relationship_conflict", "dependent_items", "save_failed"])
def test_terminal_row_reconstructs_same_stable_result_and_no_external_tokens(status):
    value = row(status)
    saved = SavedOperation.from_row(value)
    assert saved.status == status and saved.operation_id == value["operation_id"]
    assert saved.body.model_dump(mode="json") == value["receipt"]
    assert not any("ref" in key for key in value["receipt"])
    assert WriteObservation(saved.document_id, saved.operation_id, saved).confirmed


@pytest.mark.parametrize("patch", [
    {"format_version": 2}, {"unexpected": "silently discarded data"},
    {"next_action": "reconcile_operation"}, {"command_kind": "arbitrary_sql"},
])
def test_unsupported_stored_body_is_not_silently_upgraded(patch):
    value = row()
    value["receipt"].update(patch)
    with pytest.raises(ValidationError):
        SavedOperation.from_row(value)


def test_stored_error_cannot_contradict_sql_status():
    value = row("committed")
    value["receipt"] = body_for("jd_set_text", "stale_view").model_dump(mode="json")
    with pytest.raises(ResultValidationError):
        SavedOperation.from_row(value)


def test_observation_cannot_confirm_a_different_operation_or_arbitrary_effect():
    saved = SavedOperation.from_row(row())
    with pytest.raises(ValueError, match="invalid_observation_scope"):
        WriteObservation(saved.document_id, uuid4(), saved)
    with pytest.raises(ValueError, match="invalid_observation"):
        WriteObservation(saved.document_id, saved.operation_id, None, "changed")
    with pytest.raises(ValueError, match="invalid_terminal_status"):
        body_for("jd_set_text", "outcome_unknown")
