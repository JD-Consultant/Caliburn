"""Deterministic gates between framework output and semantic state transitions."""

from __future__ import annotations

from collections.abc import Sequence
import re
from typing import TYPE_CHECKING
from uuid import UUID

from app.consultant.model_runtime import (
    AttemptReceipt,
    AttemptStatus,
    ClassifiedConsultantError,
    ResolvedExecution,
    verify_attempt_budget,
)

if TYPE_CHECKING:
    from app.consultant.context import ContextSelectionReceipt
    from app.consultant.results import (
        AnalysisBasis,
        ConsultantResult,
    )
    from app.consultant.state import EmployeeSource


class ConsultantVerificationError(ClassifiedConsultantError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"verification_{code}", message)


_RISKY_SPECIFIC_CLAIM = re.compile(
    r"(?:\d+(?:[.,]\d+)?\s*(?:%|％|次|筆|件|份|人|元|分鐘|小時|天|日|週|周|月|年|個|項|張|頁|公斤|公克|克|公里|公尺|公分|秒)|依.{0,12}(?:規定|辦法|法|SOP|標準)|[\u4e00-\u9fff]{2,20}(?:基準法|管理法|保護法|處罰法|組織法|施行法|條例|辦法|規則)|公司法|民法|刑法|(?:公司|法規|法律|規章|SOP).{0,12}(?:規定|要求|必須)|SOP|標準作業程序|(?:依據|根據).{0,12}(?:iCAP|Reference|參考資料|外部資料)|according to|policy|law|regulation)",
    re.IGNORECASE,
)


def requires_anchored_employee_quote(text: str) -> bool:
    """Return whether factual text needs an exact employee quote to be reviewable."""

    return bool(_RISKY_SPECIFIC_CLAIM.search(text))


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
            "context_execution_mismatch",
            "context receipt does not match the resolved execution"
        )
    if receipt.total_input_tokens > execution.max_context_tokens:
        raise ConsultantVerificationError(
            "context_token_budget",
            "context exceeded its resolved token budget",
        )
    if not set(receipt.selected_skill_ids) <= set(execution.allowed_skill_ids):
        raise ConsultantVerificationError(
            "context_ineligible_skill",
            "context loaded an ineligible Skill",
        )
    source_ids = [item.source_id for item in receipt.loaded_sources]
    if len(source_ids) != len(set(source_ids)):
        raise ConsultantVerificationError(
            "context_duplicate_source",
            "context loaded a source more than once",
        )


def verify_model_attempts(
    execution: ResolvedExecution,
    receipts: Sequence[AttemptReceipt],
) -> None:
    if not receipts:
        raise ConsultantVerificationError(
            "attempt_missing",
            "model-bearing run has no attempt receipt",
        )
    attempt_ids = [receipt.attempt_id for receipt in receipts]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ConsultantVerificationError(
            "attempt_duplicate_id",
            "model attempt receipt ID was reused",
        )
    if len({receipt.product_run_id for receipt in receipts}) != 1:
        raise ConsultantVerificationError(
            "attempt_mixed_run",
            "model attempts span more than one product run",
        )
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
                "attempt_execution_mismatch",
                "model attempt receipt does not match the resolved execution"
            )
        if receipt.status is AttemptStatus.SUCCEEDED:
            if not receipt.actual_model or not receipt.actual_provider:
                raise ConsultantVerificationError(
                    "attempt_route_missing",
                    "successful model attempt is missing its actual route"
                )
            if receipt.usage.total_tokens is None:
                raise ConsultantVerificationError(
                    "attempt_usage_missing",
                    "successful model attempt is missing provider usage"
                )
            if execution.max_cost_usd is not None and receipt.cost_usd is None:
                raise ConsultantVerificationError(
                    "attempt_cost_missing",
                    "successful model attempt is missing provider cost"
                )
    verify_attempt_budget(execution, receipts)


def verify_consultant_result(
    result: ConsultantResult,
    *,
    execution: ResolvedExecution,
    document_id: UUID,
    current_source_id: UUID,
    selected_skill_ids: Sequence[str],
    loaded_skill_ids: Sequence[str],
    employee_sources: Sequence[EmployeeSource],
    known_work_ids: Sequence[UUID] | None = None,
    known_subject_ids: Sequence[UUID] | None = None,
) -> None:
    """Fail closed before framework output becomes durable semantic state."""

    from app.consultant.state import SourceProcessingStatus, SourceValidity

    selected = set(selected_skill_ids)
    loaded = set(loaded_skill_ids)
    if not loaded <= selected:
        raise ConsultantVerificationError(
            "loaded_unselected_skill",
            "run loaded an unselected Skill",
        )
    result_skill_ids = {
        skill_id
        for basis in result.analysis_bases()
        for skill_id in basis.skill_ids
    }
    if not result_skill_ids <= selected:
        raise ConsultantVerificationError(
            "result_unselected_skill",
            "result used an unselected Skill",
        )
    if not result_skill_ids <= loaded:
        raise ConsultantVerificationError(
            "result_unloaded_skill",
            "result used a Skill that was not loaded",
        )
    if not selected <= set(execution.allowed_skill_ids):
        raise ConsultantVerificationError(
            "selected_ineligible_skill",
            "run selected an ineligible Skill",
        )

    source_by_id = {source.source_id: source for source in employee_sources}
    if len(source_by_id) != len(employee_sources):
        raise ConsultantVerificationError(
            "duplicate_employee_source",
            "duplicate employee source supplied to verifier",
        )
    if any(source.document_id != document_id for source in employee_sources):
        raise ConsultantVerificationError(
            "cross_document_source",
            "employee source crosses document scope",
        )
    current_source = source_by_id.get(current_source_id)
    if current_source is None:
        raise ConsultantVerificationError(
            "unknown_current_source",
            "verified result does not include its current answer source",
        )
    if current_source.processing_status is not SourceProcessingStatus.COMMITTED:
        raise ConsultantVerificationError(
            "pending_current_source",
            "current answer source is not committed",
        )
    exact_pair_replay = False
    supersession_target_id: UUID | None = None
    if result.source_supersession is not None:
        supersession_target_id = result.source_supersession.superseded_source_id
        superseded_source = source_by_id.get(
            supersession_target_id
        )
        if superseded_source is None:
            raise ConsultantVerificationError(
                "unknown_supersession_source",
                "source supersession targets an unknown source",
            )
        if superseded_source.document_id != document_id:
            raise ConsultantVerificationError(
                "cross_document_supersession",
                "source supersession crosses document scope",
            )
        if superseded_source.source_id == current_source_id:
            raise ConsultantVerificationError(
                "self_supersession",
                "source supersession cannot target the current answer source",
            )
        exact_pair_replay = (
            superseded_source.validity is SourceValidity.SUPERSEDED
            and superseded_source.superseded_by_source_id == current_source_id
            and current_source.supersedes_source_id == superseded_source.source_id
        )
        if (
            superseded_source.validity is not SourceValidity.CURRENT
            and not exact_pair_replay
        ):
            raise ConsultantVerificationError(
                "superseded_target",
                "source supersession target is already superseded",
            )
        if superseded_source.processing_status is not SourceProcessingStatus.COMMITTED:
            raise ConsultantVerificationError(
                "pending_supersession_target",
                "source supersession target is not committed",
            )
    if any(
        source.validity is not SourceValidity.CURRENT
        and not (exact_pair_replay and source.source_id == supersession_target_id)
        for source in employee_sources
    ):
        raise ConsultantVerificationError(
            "superseded_employee_source",
            "superseded employee source cannot support current result",
        )

    if known_work_ids is not None:
        known_work = set(known_work_ids)
        referenced_work = {
            work_id
            for change in result.understanding_changes
            for work_id in change.work_ids
        }
        if result.required_clarification is not None:
            referenced_work.update(result.required_clarification.affected_work_ids)
        if not referenced_work <= known_work:
            raise ConsultantVerificationError(
                "unknown_work",
                "result references an unknown application ID for interview work"
            )
    if known_subject_ids is not None:
        known_subjects = set(known_subject_ids)
        referenced_subjects = {
            item.subject_id
            for item in (*result.attention_changes, *result.gaps)
            if item.subject_id is not None
        }
        if not referenced_subjects <= known_subjects:
            raise ConsultantVerificationError(
                "unknown_subject",
                "result references an unknown application ID for a subject"
            )

    for basis in result.analysis_bases():
        _verify_analysis_basis(
            basis,
            selected_skill_ids=selected,
            source_by_id=source_by_id,
        )

    for text, basis in result.factual_texts():
        if requires_anchored_employee_quote(text) and not basis.quote_anchors:
            raise ConsultantVerificationError(
                "quote_required",
                "quantities, named rules and external claims require an anchored employee quote"
            )


def _verify_analysis_basis(
    basis: AnalysisBasis,
    *,
    selected_skill_ids: set[str],
    source_by_id: dict,
) -> None:
    if not set(basis.skill_ids) <= selected_skill_ids:
        raise ConsultantVerificationError(
            "basis_unselected_skill",
            "semantic claim depends on an unselected Skill",
        )
    if not set(basis.source_ids) <= set(source_by_id):
        raise ConsultantVerificationError(
            "basis_unknown_source",
            "semantic claim depends on an unknown source",
        )
    for anchor in basis.quote_anchors:
        source = source_by_id.get(anchor.source_id)
        if source is None:
            raise ConsultantVerificationError(
                "anchor_unknown_source",
                "quote anchor references an unknown source",
            )
        if anchor.end > len(source.text):
            raise ConsultantVerificationError(
                "anchor_out_of_bounds",
                "quote anchor exceeds employee source",
            )
        if source.text[anchor.start : anchor.end] != anchor.quote:
            raise ConsultantVerificationError(
                "anchor_mismatch",
                "quote anchor does not match employee source",
            )
