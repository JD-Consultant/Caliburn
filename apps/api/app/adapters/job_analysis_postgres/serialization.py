"""Fail-closed serialization for migration 0012 rows."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.job_analysis.application import (
    ACTIVE_QUESTION_SCHEMA_ID,
    COMPLETED_TURN_SCHEMA_ID,
    CONSULTANT_OPENING_SCHEMA_ID,
    DIRECT_EDIT_SCHEMA_ID,
    OPKS_ITEM_SCHEMA_ID,
    OPKS_DIRECT_EDIT_SCHEMA_ID,
    OPKS_PROPOSAL_DECISION_SCHEMA_ID,
    OPKS_GENERATION_SCHEMA_ID,
    OPKS_PROPOSAL_SCHEMA_ID,
    PROPOSAL_DECISION_SCHEMA_ID,
    PROPOSAL_SCHEMA_ID,
    JD_HEADER_DIRECT_EDIT_SCHEMA_ID,
    JD_HEADER_SCHEMA_ID,
    WORK_MODEL_SCHEMA_ID,
    ActiveQuestion,
    CompletedTurnPayload,
    ConsultantOpeningPayload,
    DirectEditPayload,
    JdHeaderDirectEditPayload,
    DocumentRecord,
    JournalEntry,
    OpksDirectEditPayload,
    OpksProposalDecisionPayload,
    OpksGenerationPayload,
    ProposalDecisionPayload,
)
from app.job_analysis.domain import (
    CurrentWorkModel,
    JdHeader,
    JdTask,
    OpksItem,
    OpksProposal,
    Proposal,
)


class PersistedJobAnalysisCorruption(RuntimeError):
    """A persisted row cannot be trusted as a current product authority."""


def _fail(label: str, detail: object, cause: Exception | None = None):
    error = PersistedJobAnalysisCorruption(f"persisted {label} is invalid: {detail}")
    if cause is None:
        raise error
    raise error from cause


def dump_work_model(value: CurrentWorkModel) -> dict[str, Any]:
    return value.model_dump(mode="json")


def load_work_model(*, schema_id: str, payload: object) -> CurrentWorkModel:
    if schema_id != WORK_MODEL_SCHEMA_ID:
        _fail("work model schema", schema_id)
    try:
        return CurrentWorkModel.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("Work Model", exc, exc)


def dump_jd_header(value: JdHeader) -> dict[str, Any]:
    return value.model_dump(mode="json")


def load_jd_header(*, schema_id: str, payload: object) -> JdHeader:
    if schema_id != JD_HEADER_SCHEMA_ID:
        _fail("jd header schema", schema_id)
    try:
        return JdHeader.model_validate(payload)
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("JD Header", exc, exc)


def dump_active_question(value: ActiveQuestion | None) -> dict[str, Any] | None:
    if value is None:
        return None
    return {
        "schema_id": ACTIVE_QUESTION_SCHEMA_ID,
        "payload": value.model_dump(mode="json"),
    }


def load_active_question(payload: object) -> ActiveQuestion | None:
    if payload is None:
        return None
    if not isinstance(payload, dict):
        _fail("active question envelope", type(payload).__name__)
    if payload.get("schema_id") != ACTIVE_QUESTION_SCHEMA_ID:
        _fail("active question schema", payload.get("schema_id"))
    try:
        return ActiveQuestion.model_validate(payload.get("payload"))
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("Active Question", exc, exc)


def load_document(row: Any) -> DocumentRecord:
    return DocumentRecord(
        document_id=row.document_id,
        title=row.title,
        jd_header=load_jd_header(
            schema_id=row.jd_header_schema_id,
            payload=row.jd_header_json,
        ),
        work_model=load_work_model(
            schema_id=row.work_model_schema_id,
            payload=row.work_model_json,
        ),
        active_question=load_active_question(row.active_question_json),
        authority_generation=row.authority_generation,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def dump_jd_task_enablers(task: JdTask) -> list[dict[str, Any]]:
    return [enabler.model_dump(mode="json") for enabler in task.enablers]


def load_jd_task(row: Any) -> JdTask:
    try:
        return JdTask.model_validate(
            {
                "task_id": row.task_id,
                "statement": row.statement,
                "purpose_result": row.purpose_result,
                "context": row.context,
                "frequency_text": row.frequency_text,
                "responsibility_role": row.responsibility_role,
                "enablers": row.enablers_json,
                "display_order": row.display_order,
            }
        )
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("JD Task", exc, exc)


_OPKS_ITEM_RELATIONAL_FIELDS = {"entity_id", "entity_kind"}


def dump_opks_item_payload(item: OpksItem) -> dict[str, Any]:
    return item.model_dump(mode="json", exclude=_OPKS_ITEM_RELATIONAL_FIELDS)


def load_opks_item(row: Any) -> OpksItem:
    if row.item_schema_id != OPKS_ITEM_SCHEMA_ID:
        _fail("OPKS item schema", row.item_schema_id)
    if not isinstance(row.item_payload, dict):
        _fail("OPKS item payload", type(row.item_payload).__name__)
    duplicate = _OPKS_ITEM_RELATIONAL_FIELDS & set(row.item_payload)
    if duplicate:
        _fail("OPKS item payload", f"duplicates relational fields {sorted(duplicate)}")
    try:
        return OpksItem.model_validate(
            {
                **row.item_payload,
                "entity_id": row.entity_id,
                "entity_kind": row.entity_kind,
            }
        )
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("OPKS item", exc, exc)


_OPKS_PROPOSAL_RELATIONAL_FIELDS = {
    "proposal_id",
    "operation_id",
    "entity_id",
    "entity_kind",
    "action",
    "status",
    "base_authority_generation",
    "created_at",
    "resolved_at",
}


def dump_opks_proposal_payload(proposal: OpksProposal) -> dict[str, Any]:
    return proposal.model_dump(
        mode="json",
        exclude=_OPKS_PROPOSAL_RELATIONAL_FIELDS,
    )


def load_opks_proposal(row: Any) -> OpksProposal:
    if row.proposal_schema_id != OPKS_PROPOSAL_SCHEMA_ID:
        _fail("OPKS Proposal schema", row.proposal_schema_id)
    if not isinstance(row.proposal_payload, dict):
        _fail("OPKS Proposal payload", type(row.proposal_payload).__name__)
    duplicate = _OPKS_PROPOSAL_RELATIONAL_FIELDS & set(row.proposal_payload)
    if duplicate:
        _fail(
            "OPKS Proposal payload",
            f"duplicates relational fields {sorted(duplicate)}",
        )
    try:
        return OpksProposal.model_validate(
            {
                **row.proposal_payload,
                "proposal_id": row.proposal_id,
                "operation_id": row.operation_id,
                "entity_id": row.entity_id,
                "entity_kind": row.entity_kind,
                "action": row.action,
                "status": row.status,
                "base_authority_generation": row.base_authority_generation,
                "created_at": row.created_at,
                "resolved_at": row.resolved_at,
            }
        )
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("OPKS Proposal", exc, exc)


_PROPOSAL_RELATIONAL_FIELDS = {
    "proposal_id",
    "status",
    "caused_by_decision_id",
}


def dump_proposal_payload(proposal: Proposal) -> dict[str, Any]:
    return proposal.model_dump(
        mode="json",
        exclude=_PROPOSAL_RELATIONAL_FIELDS,
    )


def load_proposal(row: Any) -> Proposal:
    if row.proposal_schema_id != PROPOSAL_SCHEMA_ID:
        _fail("Proposal schema", row.proposal_schema_id)
    if not isinstance(row.proposal_payload, dict):
        _fail("Proposal payload", type(row.proposal_payload).__name__)
    duplicate = _PROPOSAL_RELATIONAL_FIELDS & set(row.proposal_payload)
    if duplicate:
        _fail("Proposal payload", f"duplicates relational fields {sorted(duplicate)}")
    try:
        return Proposal.model_validate(
            {
                **row.proposal_payload,
                "proposal_id": row.proposal_id,
                "status": row.status,
                "caused_by_decision_id": row.caused_by_decision_id,
            }
        )
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("Proposal", exc, exc)


_JOURNAL_PAYLOAD_TYPES = {
    CONSULTANT_OPENING_SCHEMA_ID: ConsultantOpeningPayload,
    COMPLETED_TURN_SCHEMA_ID: CompletedTurnPayload,
    DIRECT_EDIT_SCHEMA_ID: DirectEditPayload,
    JD_HEADER_DIRECT_EDIT_SCHEMA_ID: JdHeaderDirectEditPayload,
    OPKS_DIRECT_EDIT_SCHEMA_ID: OpksDirectEditPayload,
    OPKS_PROPOSAL_DECISION_SCHEMA_ID: OpksProposalDecisionPayload,
    OPKS_GENERATION_SCHEMA_ID: OpksGenerationPayload,
    PROPOSAL_DECISION_SCHEMA_ID: ProposalDecisionPayload,
}


def dump_journal_payload(entry: JournalEntry) -> dict[str, Any]:
    return entry.payload.model_dump(mode="json")


def load_journal(row: Any) -> JournalEntry:
    payload_type = _JOURNAL_PAYLOAD_TYPES.get(row.payload_schema_id)
    if payload_type is None:
        _fail("Journal schema", row.payload_schema_id)
    try:
        payload = payload_type.model_validate(row.payload)
        return JournalEntry(
            document_id=row.document_id,
            entry_id=row.entry_id,
            kind=row.kind,
            payload_schema_id=row.payload_schema_id,
            payload=payload,
            created_at=row.created_at,
        )
    except (ValidationError, TypeError, ValueError) as exc:
        _fail("Journal entry", exc, exc)
