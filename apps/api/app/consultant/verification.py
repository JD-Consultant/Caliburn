"""Deterministic gates between framework output and semantic state transitions."""

from __future__ import annotations

from collections.abc import Sequence
import re
from typing import TYPE_CHECKING
from uuid import UUID

from app.consultant.model_runtime import (
    AttemptReceipt,
    AttemptStatus,
    ResolvedExecution,
    verify_attempt_budget,
)

if TYPE_CHECKING:
    from app.consultant.context import ContextSelectionReceipt
    from app.consultant.results import AnalysisBasis, ConsultantResult
    from app.consultant.state import EmployeeSource


class ConsultantVerificationError(RuntimeError):
    pass


_UUID = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
_SUPPORTED_DOCUMENT_PATHS = (
    re.compile(r"^/job_title$"),
    re.compile(r"^/work_description$"),
    re.compile(r"^/duties$"),
    re.compile(rf"^/duties/{_UUID}$"),
    re.compile(rf"^/duties/{_UUID}/(?:statement|display_order)$"),
    re.compile(r"^/tasks$"),
    re.compile(rf"^/tasks/{_UUID}$"),
    re.compile(
        rf"^/tasks/{_UUID}/(?:duty_id|statement|action|object|purpose_result|context|frequency_text|responsibility_role|enablers|display_order)$"
    ),
    re.compile(r"^/opks$"),
    re.compile(rf"^/opks/{_UUID}$"),
    re.compile(rf"^/opks/{_UUID}/(?:text|display_order|task_ids|indicator_ids)$"),
)
_RISKY_SPECIFIC_CLAIM = re.compile(
    r"(?:\d|依.{0,12}(?:規定|辦法|法|SOP|標準)|[\u4e00-\u9fff]{2,20}(?:基準法|管理法|保護法|處罰法|組織法|施行法|條例|辦法|規則)|公司法|民法|刑法|(?:公司|法規|法律|規章|SOP).{0,12}(?:規定|要求|必須)|SOP|標準作業程序|(?:依據|根據).{0,12}(?:iCAP|Reference|參考資料|外部資料)|according to|policy|law|regulation)",
    re.IGNORECASE,
)
_ALLOWED_COLLECTION_PAYLOAD_KEYS = {
    "duty_id",
    "task_id",
    "item_id",
    "kind",
    "statement",
    "action",
    "object",
    "purpose_result",
    "context",
    "frequency_text",
    "responsibility_role",
    "enablers",
    "display_order",
    "text",
    "task_ids",
    "indicator_ids",
    "name",
}


def verify_context_selection(
    execution: ResolvedExecution,
    receipt: ContextSelectionReceipt,
) -> None:
    if (
        receipt.profile_id != execution.profile_id
        or receipt.profile_revision != execution.profile_revision
        or receipt.policy_id != execution.policy_id
        or receipt.policy_revision != execution.policy_revision
    ):
        raise ConsultantVerificationError(
            "context receipt does not match the resolved execution"
        )
    if receipt.total_input_tokens > execution.max_context_tokens:
        raise ConsultantVerificationError("context exceeded its resolved token budget")
    if not set(receipt.selected_skill_ids) <= set(execution.allowed_skill_ids):
        raise ConsultantVerificationError("context loaded an ineligible Skill")
    source_ids = [item.source_id for item in receipt.loaded_sources]
    if len(source_ids) != len(set(source_ids)):
        raise ConsultantVerificationError("context loaded a source more than once")


def verify_model_attempts(
    execution: ResolvedExecution,
    receipts: Sequence[AttemptReceipt],
) -> None:
    if not receipts:
        raise ConsultantVerificationError("model-bearing run has no attempt receipt")
    attempt_ids = [receipt.attempt_id for receipt in receipts]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ConsultantVerificationError("model attempt receipt ID was reused")
    if len({receipt.product_run_id for receipt in receipts}) != 1:
        raise ConsultantVerificationError("model attempts span more than one product run")
    for receipt in receipts:
        if (
            receipt.requested_model != execution.requested_model
            or receipt.provider_allowlist != execution.provider_allowlist
            or receipt.profile_id != execution.profile_id
            or receipt.profile_revision != execution.profile_revision
            or receipt.policy_id != execution.policy_id
            or receipt.policy_revision != execution.policy_revision
            or receipt.effective_parameters != execution.effective_parameters
        ):
            raise ConsultantVerificationError(
                "model attempt receipt does not match the resolved execution"
            )
        if receipt.status is AttemptStatus.SUCCEEDED:
            if not receipt.actual_model or not receipt.actual_provider:
                raise ConsultantVerificationError(
                    "successful model attempt is missing its actual route"
                )
            if receipt.usage.total_tokens is None:
                raise ConsultantVerificationError(
                    "successful model attempt is missing provider usage"
                )
            if execution.max_cost_usd is not None and receipt.cost_usd is None:
                raise ConsultantVerificationError(
                    "successful model attempt is missing provider cost"
                )
    verify_attempt_budget(execution, receipts)


def verify_consultant_result(
    result: ConsultantResult,
    *,
    execution: ResolvedExecution,
    document_id: UUID,
    selected_skill_ids: Sequence[str],
    loaded_skill_ids: Sequence[str],
    employee_sources: Sequence[EmployeeSource],
) -> None:
    """Fail closed before framework output becomes durable semantic state."""

    from app.consultant.results import OpksKind
    from app.consultant.state import SourceValidity

    selected = set(selected_skill_ids)
    loaded = set(loaded_skill_ids)
    if not loaded <= selected:
        raise ConsultantVerificationError("run loaded an unselected Skill")
    if not set(result.used_skill_ids) <= selected:
        raise ConsultantVerificationError("result used an unselected Skill")
    if not set(result.used_skill_ids) <= loaded:
        raise ConsultantVerificationError("result used a Skill that was not loaded")
    if not selected <= set(execution.allowed_skill_ids):
        raise ConsultantVerificationError("run selected an ineligible Skill")

    source_by_id = {source.source_id: source for source in employee_sources}
    if len(source_by_id) != len(employee_sources):
        raise ConsultantVerificationError("duplicate employee source supplied to verifier")
    if any(source.validity is not SourceValidity.CURRENT for source in employee_sources):
        raise ConsultantVerificationError("superseded employee source cannot support current result")
    if any(source.document_id != document_id for source in employee_sources):
        raise ConsultantVerificationError("employee source crosses document scope")

    for basis in result.analysis_bases():
        _verify_analysis_basis(
            basis,
            selected_skill_ids=selected,
            source_by_id=source_by_id,
        )

    for change in result.reviewable_document_changes:
        if not any(pattern.fullmatch(change.path) for pattern in _SUPPORTED_DOCUMENT_PATHS):
            raise ConsultantVerificationError(
                f"unsupported document change path: {change.path}"
            )
        _verify_document_payload(change.after)
        _verify_change_operation(change.operation.value, change.path)
        if not change.path.startswith("/opks") and (
            change.opks_kind is not None
            or change.task_ids
            or change.indicator_ids
        ):
            raise ConsultantVerificationError(
                "non-OPKS change cannot carry OPKS linkage fields"
            )
        if change.path.startswith("/opks"):
            if change.opks_kind is None:
                raise ConsultantVerificationError("OPKS change requires an OPKS kind")
            if change.opks_kind in {OpksKind.OUTPUT, OpksKind.PERFORMANCE_INDICATOR}:
                if len(change.task_ids) != 1:
                    raise ConsultantVerificationError(
                        "O/P changes must reference exactly one Task"
                    )
                if change.indicator_ids:
                    raise ConsultantVerificationError(
                        "O/P changes cannot reference performance indicators"
                    )
            elif not change.task_ids:
                raise ConsultantVerificationError(
                    "document-level K/S changes require Task linkages"
                )
            if change.opks_kind in {OpksKind.KNOWLEDGE, OpksKind.SKILL}:
                if not change.basis.quote_anchors:
                    raise ConsultantVerificationError(
                        "active K/S requires anchored employee evidence"
                    )

    for text, basis in result.factual_texts():
        if _RISKY_SPECIFIC_CLAIM.search(text) and not basis.quote_anchors:
            raise ConsultantVerificationError(
                "quantities, named rules and external claims require an anchored employee quote"
            )


def _verify_analysis_basis(
    basis: AnalysisBasis,
    *,
    selected_skill_ids: set[str],
    source_by_id: dict,
) -> None:
    if not set(basis.skill_ids) <= selected_skill_ids:
        raise ConsultantVerificationError("semantic claim depends on an unselected Skill")
    if not set(basis.source_ids) <= set(source_by_id):
        raise ConsultantVerificationError("semantic claim depends on an unknown source")
    for anchor in basis.quote_anchors:
        source = source_by_id.get(anchor.source_id)
        if source is None:
            raise ConsultantVerificationError("quote anchor references an unknown source")
        if anchor.end > len(source.text):
            raise ConsultantVerificationError("quote anchor exceeds employee source")
        if source.text[anchor.start : anchor.end] != anchor.quote:
            raise ConsultantVerificationError("quote anchor does not match employee source")


def _verify_document_payload(value: object) -> None:
    if isinstance(value, dict):
        unknown = set(value) - _ALLOWED_COLLECTION_PAYLOAD_KEYS
        if unknown:
            raise ConsultantVerificationError(
                f"unsupported payload fields: {sorted(unknown)}"
            )
        for nested in value.values():
            _verify_document_payload(nested)
    elif isinstance(value, list):
        for nested in value:
            _verify_document_payload(nested)


def _verify_change_operation(operation: str, path: str) -> None:
    entity_path = re.fullmatch(rf"/(?:duties|tasks|opks)/{_UUID}", path) is not None
    collection_path = path in {"/duties", "/tasks", "/opks"}
    if operation == "add" and not collection_path:
        raise ConsultantVerificationError("add operation requires a collection path")
    if operation == "withdraw" and not entity_path:
        raise ConsultantVerificationError("withdraw operation requires an entity path")
    if operation in {"merge", "split"} and not (collection_path or entity_path):
        raise ConsultantVerificationError(
            f"{operation} operation requires a Duty, Task or OPKS entity path"
        )
    if operation == "reassign" and not re.fullmatch(
        rf"/tasks/{_UUID}/duty_id", path
    ):
        raise ConsultantVerificationError(
            "reassign operation requires a Task duty_id path"
        )
    if operation == "reorder" and not path.endswith("/display_order"):
        raise ConsultantVerificationError(
            "reorder operation requires a display_order path"
        )
