"""Original observation -> external refs, without querying or replaying a write."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import traceback
from uuid import UUID

import pytest

from jd_relational.observation_projection import ProjectionError, project_observation
from jd_relational.references import ReferenceCodec, ReferenceValidationError
from jd_relational.result_transport import validate_result
from jd_relational.storage.receipts import ERRORS, ReceiptError, SavedOperation, WriteObservation, body_for


DOC = "synthetic-projection-document"
OP = UUID(int=10)
BASE = UUID(int=20)
RESULT = UUID(int=21)
KEY = b"projection-test-only-signing-key!1"
DATASET = "synthetic-projection-dataset"


@pytest.fixture
def codec():
    return ReferenceCodec(KEY, DATASET)


def observation(status="committed"):
    receipt = SavedOperation(DOC, OP, "a" * 64, "manual", None, BASE,
        RESULT if status == "committed" else BASE if status == "no_change" else None,
        status, body_for("jd_set_text", status), datetime(2026, 9, 13, tzinfo=timezone.utc))
    return WriteObservation(DOC, OP, receipt)


def resolve(codec, token, role):
    return codec.resolve(token, document_id=DOC, roles={role}, purposes={"observation"})


@pytest.mark.parametrize("status", ["committed", "no_change", *ERRORS])
def test_every_confirmed_terminal_preserves_original_receipt_semantics(codec, status):
    value = observation(status)
    original = deepcopy(value)
    result = project_observation(value, codec)
    assert validate_result(result) == result
    assert result["status"] == status and result["receipt_durability"] == "confirmed"
    assert result["effect"] == ("changed" if status == "committed" else "unchanged")
    assert result["next_action"] == value.receipt.body.next_action
    operation = resolve(codec, result["operation_ref"], "operation")
    assert operation.entity_id == str(OP) and operation.revision_id is None
    if status in ("committed", "no_change"):
        revision = resolve(codec, result["result_revision_ref"], "revision")
        assert revision.revision_id == str(value.receipt.result_revision_id)
        assert revision.entity_id is None and result["error"] is None
    else:
        assert result["result_revision_ref"] is None
        assert result["error"] == {**value.receipt.body.error.model_dump(), "related_refs": []}
    if status == "committed":
        change = resolve(codec, result["change_ref"], "change")
        assert change.entity_id == str(OP) and change.revision_id == str(RESULT)
    else:
        assert result["change_ref"] is None
    assert value == original


def test_later_saved_revision_and_new_signing_key_do_not_replace_original_success(codec):
    original = observation()
    original_copy = deepcopy(original)
    old_result = project_observation(original, codec)
    later_receipt = replace(original.receipt, operation_id=UUID(int=11), base_revision_id=RESULT,
                            result_revision_id=UUID(int=99))
    later = WriteObservation(DOC, later_receipt.operation_id, later_receipt)
    changed_key = ReferenceCodec(b"different-projection-signing-key!2", DATASET)
    later_result = project_observation(later, changed_key)
    result = project_observation(original, changed_key)
    assert resolve(changed_key, later_result["result_revision_ref"], "revision").revision_id == str(UUID(int=99))
    assert resolve(changed_key, result["result_revision_ref"], "revision").revision_id == str(RESULT)
    assert resolve(changed_key, result["change_ref"], "change").entity_id == str(OP)
    assert result["operation_ref"] != old_result["operation_ref"]
    with pytest.raises(ReferenceValidationError):
        resolve(codec, result["operation_ref"], "operation")
    non_refs = set(result) - {"operation_ref", "result_revision_ref", "change_ref"}
    assert {key: result[key] for key in non_refs} == {key: old_result[key] for key in non_refs}
    assert original == original_copy and original.receipt.base_revision_id == BASE


@pytest.mark.parametrize("effect,status", [("unknown", "outcome_unknown"), ("unchanged", "save_failed")])
def test_unconfirmed_observation_keeps_original_operation_and_requires_reconciliation(codec, effect, status):
    value = WriteObservation(DOC, OP, None, effect)
    original = deepcopy(value)
    result = project_observation(value, codec)
    assert validate_result(result) == result
    assert (result["status"], result["effect"], result["receipt_durability"], result["next_action"]) == (
        status, effect, "unconfirmed", "reconcile_operation")
    assert resolve(codec, result["operation_ref"], "operation").entity_id == str(OP)
    assert result["result_revision_ref"] is None and result["change_ref"] is None
    assert result["error"]["code"] == status and result["error"]["related_refs"] == []
    assert value == original


def test_unconfirmed_projection_never_borrows_a_later_known_success(codec):
    unknown = WriteObservation(DOC, OP, None, "unknown")
    project_observation(observation(), codec)
    result = project_observation(unknown, codec)
    assert result["status"] == "outcome_unknown" and result["receipt_durability"] == "unconfirmed"
    assert result["result_revision_ref"] is None and unknown.receipt is None


def test_confirmed_failure_without_a_base_revision_retains_its_original_saved_message(codec):
    value = observation("invalid_input")
    original_error = ReceiptError(code="invalid_input", message="原先保存的具體說明😀\n不套用新版訊息")
    body = value.receipt.body.model_copy(update={"error": original_error})
    receipt = replace(value.receipt, base_revision_id=None, body=body)
    value = WriteObservation(DOC, OP, receipt)
    result = project_observation(value, codec)
    assert result["error"] == {"code": "invalid_input", "message": original_error.message, "related_refs": []}
    assert result["result_revision_ref"] is None and result["change_ref"] is None
    assert result["next_action"] == "correct_arguments" and value.receipt.base_revision_id is None


def test_contradictory_saved_error_body_is_not_silently_rewritten(codec):
    value = observation("invalid_input")
    contradictory = value.receipt.body.model_copy(update={"error": ReceiptError(code="stale_view", message="原錯誤")})
    value = WriteObservation(DOC, OP, replace(value.receipt, body=contradictory))
    with pytest.raises(ProjectionError, match="^projection_failed$"):
        project_observation(value, codec)
    assert value.receipt.body.error.code == "stale_view" and value.status == "invalid_input"


@pytest.mark.parametrize("bad", [None, {}, {"status": "committed"}, "committed", 1])
def test_only_explicit_write_observation_is_accepted(codec, bad):
    with pytest.raises(ProjectionError, match="^projection_failed$"):
        project_observation(bad, codec)


@pytest.mark.parametrize("stage", [1, 2, 3])
def test_codec_failure_at_any_issued_ref_is_projection_failure_not_save_failure(stage):
    class BrokenCodec(ReferenceCodec):
        def __init__(self):
            super().__init__(KEY, DATASET)
            self.calls = 0

        def issue(self, reference):
            self.calls += 1
            if self.calls == stage:
                raise RuntimeError("synthetic-private-signing-detail")
            return super().issue(reference)

    value = observation()
    original = deepcopy(value)
    with pytest.raises(ProjectionError) as error:
        project_observation(value, BrokenCodec())
    assert str(error.value) == "projection_failed" and error.value.__cause__ is None
    assert "synthetic-private-signing-detail" not in "".join(traceback.format_exception(error.value))
    assert value == original and value.confirmed and value.status == "committed"
    assert project_observation(value, ReferenceCodec(KEY, DATASET))["status"] == "committed"


def test_invalid_projected_dto_is_not_reclassified_as_a_failed_save(codec):
    class InvalidTokenCodec(ReferenceCodec):
        def issue(self, reference):
            return ""

    value = observation()
    original = deepcopy(value)
    with pytest.raises(ProjectionError, match="^projection_failed$"):
        project_observation(value, InvalidTokenCodec(KEY, DATASET))
    assert value == original and value.status == "committed"


@pytest.mark.parametrize("status,base,result", [
    ("committed", None, RESULT), ("committed", BASE, None), ("committed", BASE, BASE),
    ("no_change", BASE, RESULT), ("no_change", None, None), ("save_failed", BASE, RESULT),
])
def test_contradictory_internal_terminal_identity_cannot_be_hidden_by_ref_projection(codec, status, base, result):
    value = observation(status)
    receipt = replace(value.receipt, base_revision_id=base, result_revision_id=result)
    value = WriteObservation(DOC, OP, receipt)
    with pytest.raises(ProjectionError, match="^projection_failed$"):
        project_observation(value, codec)
