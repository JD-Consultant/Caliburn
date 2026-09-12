"""Project an existing App write observation into the shared external result.

Only the storage observation supplies terminal truth. Token issuance and DTO
validation establish neither commit nor durability. There is no DB read, current
head lookup, receipt mutation or command replay on this path.
"""

from .references import ReferenceCodec, SignedReference
from .result_transport import validate_result
from .storage.receipts import ERRORS, SavedOperation, WriteObservation


class ProjectionError(ValueError):
    """Projection failed; the underlying write observation remains unchanged."""


def project_observation(observation: WriteObservation, codec: ReferenceCodec) -> dict:
    """Issue observation-only refs for the original operation and result.

    Reissued tokens may differ after a signing-key change; the operation,
    result revision and original receipt semantics must remain the same.
    Any projection failure raises a fixed error rather than a save-failed DTO.
    """
    try:
        if not isinstance(observation, WriteObservation):
            raise ValueError("invalid_observation_type")
        receipt = observation.receipt
        if receipt is None:
            effect = observation.unresolved_effect
            if effect not in {"unknown", "unchanged"}:
                raise ValueError("invalid_unconfirmed_effect")
            status = "outcome_unknown" if effect == "unknown" else "save_failed"
            message = ("尚未確認原操作的保存結果；請先查回原操作。" if effect == "unknown" else
                       "已確認 JD 未變更，但尚未確認永久回執；請先查回原操作。")
            result = {"status": status, "effect": effect, "receipt_durability": "unconfirmed",
                      "error": {"code": status, "message": message, "related_refs": []},
                      "next_action": "reconcile_operation"}
        else:
            if (not isinstance(receipt, SavedOperation) or observation.unresolved_effect is not None
                    or receipt.document_id != observation.document_id or receipt.operation_id != observation.operation_id):
                raise ValueError("invalid_confirmed_scope")
            status = receipt.status
            base, final = receipt.base_revision_id, receipt.result_revision_id
            if status == "committed":
                if base is None or final is None or base == final:
                    raise ValueError("invalid_committed_identity")
            elif status == "no_change":
                if base is None or final is None or base != final:
                    raise ValueError("invalid_no_change_identity")
            elif status not in ERRORS or final is not None:
                raise ValueError("invalid_failure_identity")
            result = {"status": status, "effect": "changed" if status == "committed" else "unchanged",
                      "receipt_durability": "confirmed", "next_action": receipt.body.next_action,
                      "error": {**receipt.body.error.model_dump(), "related_refs": []} if receipt.body.error else None}

        operation_id = str(observation.operation_id)
        result["operation_ref"] = codec.issue(SignedReference(
            document_id=observation.document_id, revision_id=None, purpose="observation",
            role="operation", kind="operation", entity_id=operation_id))
        result["result_revision_ref"] = None
        result["change_ref"] = None
        if receipt is not None and receipt.status in {"committed", "no_change"}:
            revision_id = str(receipt.result_revision_id)
            result["result_revision_ref"] = codec.issue(SignedReference(
                document_id=observation.document_id, revision_id=revision_id,
                purpose="observation", role="revision", kind="revision"))
            if receipt.status == "committed":
                result["change_ref"] = codec.issue(SignedReference(
                    document_id=observation.document_id, revision_id=revision_id, purpose="observation",
                    role="change", kind="change", entity_id=operation_id))
        return validate_result(result)
    except Exception:
        raise ProjectionError("projection_failed") from None
