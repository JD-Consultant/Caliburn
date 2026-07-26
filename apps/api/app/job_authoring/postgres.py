"""PostgreSQL adapter for the Job Authoring Core (plan §11, §22).

Every read rehydrates strict Pydantic values, reserializes them canonically,
checks the persisted hash and normalized columns, and fails closed on any
disagreement.  Repository methods never commit; one
``SqlAlchemyAuthoringUnitOfWork`` owns one ``AsyncSession`` transaction.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import TypeVar
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.interview_vnext.domain.evidence import EvidenceStatus
from app.interview_vnext.domain.hashing import canonical_hash as vnext_canonical_hash
from app.interview_vnext.persistence import serialization as vnext_serialization
from app.interview_vnext.persistence.errors import PersistenceError as VNextPersistenceError
from app.interview_vnext.persistence.models import VNextSessionRow

from .canonical import canonical_hash, canonical_json
from .commands import (
    CreateJobDocumentCommand,
    EmployeeProposalDecisionCommand,
    EmployeeTaskBundleCommand,
)
from .contracts import (
    AiTaskBundleProposal,
    EmployeeProposalDecision,
    EvidenceBasisRef,
    JobDocumentDraft,
    JobDocumentRevision,
    ProposalStaleReason,
    TaskProposalView,
)
from .errors import (
    AuthoringError,
    AuthoringErrorCode,
    PersistedAuthoringCorruption,
)
from .ports import (
    AuthoringCommand,
    AuthoringDocumentLock,
    AuthoringDocumentRecord,
    AuthoringProposalRecord,
    AuthoringRevisionRecord,
    DigestProposalSummary,
    EvidenceSourceSnapshot,
    ProposalStatus,
)
from .postgres_models import (
    JobAuthoringDocumentRow,
    JobAuthoringProposalRow,
    JobAuthoringRevisionRow,
)


_ModelT = TypeVar("_ModelT", bound=BaseModel)
_COMMAND_TYPES: Mapping[str, type[AuthoringCommand]] = {
    "create_job_document_command.v1": CreateJobDocumentCommand,
    "employee_task_bundle_command.v1": EmployeeTaskBundleCommand,
    "employee_proposal_decision_command.v1": EmployeeProposalDecisionCommand,
}
_PROPOSAL_SCHEMA = "ai_task_bundle_proposal.v1"
_DECISION_SCHEMA = "employee_proposal_decision.v1"
_SNAPSHOT_SCHEMA = "job_document_draft.v1"
_DIGEST_PENDING_LIMIT = 16


def _corrupt(message: str, **details: object) -> PersistedAuthoringCorruption:
    return PersistedAuthoringCorruption(message, **details)


def _load_model(
    model_type: type[_ModelT],
    text: str,
    expected_hash: str,
    *,
    label: str,
    **details: object,
) -> _ModelT:
    try:
        payload = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise _corrupt(f"persisted {label} is not valid JSON", **details) from exc
    try:
        model = model_type.model_validate(payload)
    except ValidationError as exc:
        raise _corrupt(
            f"persisted {label} failed strict validation", **details
        ) from exc
    if canonical_json(model) != text:
        raise _corrupt(
            f"persisted {label} text is not canonical", **details
        )
    if canonical_hash(model) != expected_hash:
        raise _corrupt(f"persisted {label} hash mismatch", **details)
    return model


def _load_command(row: JobAuthoringRevisionRow) -> AuthoringCommand:
    model_type = _COMMAND_TYPES.get(row.command_schema_id)
    if model_type is None:
        raise _corrupt(
            "persisted revision command schema is unsupported",
            revision_id=row.revision_id,
            schema_id=row.command_schema_id,
        )
    command = _load_model(
        model_type,
        row.command_json,
        row.command_hash,
        label="authoring command",
        revision_id=row.revision_id,
    )
    if command.schema_version != row.command_schema_id:
        raise _corrupt(
            "command schema column does not match payload",
            revision_id=row.revision_id,
        )
    return command


async def _hydrate_revision(
    session: AsyncSession,
    row: JobAuthoringRevisionRow,
    *,
    tenant_id: UUID,
) -> AuthoringRevisionRecord:
    if row.tenant_id != tenant_id:
        raise _corrupt(
            "revision tenant does not match query scope",
            revision_id=row.revision_id,
        )
    if row.snapshot_schema_id != _SNAPSHOT_SCHEMA:
        raise _corrupt(
            "persisted revision snapshot schema is unsupported",
            revision_id=row.revision_id,
            schema_id=row.snapshot_schema_id,
        )
    snapshot = _load_model(
        JobDocumentDraft,
        row.snapshot_json,
        row.snapshot_hash,
        label="job document snapshot",
        revision_id=row.revision_id,
    )
    command = _load_command(row)
    try:
        revision = JobDocumentRevision(
            revision_id=row.revision_id,
            document_id=row.document_id,
            revision_number=row.revision_number,
            parent_revision_id=row.parent_revision_id,
            snapshot=snapshot,
            snapshot_hash=row.snapshot_hash,
            source_kind=row.source_kind,
            command_id=row.command_id,
            occurred_at=row.occurred_at,
        )
        record = AuthoringRevisionRecord(
            tenant_id=row.tenant_id,
            revision=revision,
            command_schema_id=row.command_schema_id,
            command_hash=row.command_hash,
            created_at=row.created_at,
        )
    except ValidationError as exc:
        raise _corrupt(
            "persisted revision columns failed validation",
            revision_id=row.revision_id,
        ) from exc

    mismatches: list[str] = []
    if snapshot.document_id != row.document_id:
        mismatches.append("snapshot.document_id")
    if command.command_id != row.command_id:
        mismatches.append("command.command_id")
    if command.tenant_id != row.tenant_id:
        mismatches.append("command.tenant_id")
    command_document = getattr(command, "document_id", row.document_id)
    if command_document != row.document_id:
        mismatches.append("command.document_id")
    if isinstance(command, CreateJobDocumentCommand):
        if command.session_id != snapshot.session_id:
            mismatches.append("command.session_id")
    if mismatches:
        raise _corrupt(
            "revision normalized columns do not match payload",
            revision_id=row.revision_id,
            mismatched=",".join(mismatches),
        )

    if row.parent_revision_id is not None:
        parent = (
            await session.execute(
                sa.select(
                    JobAuthoringRevisionRow.document_id,
                    JobAuthoringRevisionRow.revision_number,
                ).where(
                    JobAuthoringRevisionRow.tenant_id == tenant_id,
                    JobAuthoringRevisionRow.revision_id == row.parent_revision_id,
                )
            )
        ).one_or_none()
        if parent is None:
            raise _corrupt(
                "revision parent is missing",
                revision_id=row.revision_id,
                parent_revision_id=row.parent_revision_id,
            )
        if (
            parent.document_id != row.document_id
            or parent.revision_number + 1 != row.revision_number
        ):
            raise _corrupt(
                "revision parent lineage is not contiguous",
                revision_id=row.revision_id,
                parent_revision_id=row.parent_revision_id,
            )
    return record


async def _revision_row(
    session: AsyncSession, tenant_id: UUID, revision_id: UUID
) -> JobAuthoringRevisionRow | None:
    return (
        await session.execute(
            sa.select(JobAuthoringRevisionRow).where(
                JobAuthoringRevisionRow.tenant_id == tenant_id,
                JobAuthoringRevisionRow.revision_id == revision_id,
            )
        )
    ).scalar_one_or_none()


async def _load_revision(
    session: AsyncSession, tenant_id: UUID, revision_id: UUID
) -> AuthoringRevisionRecord | None:
    row = await _revision_row(session, tenant_id, revision_id)
    if row is None:
        return None
    return await _hydrate_revision(session, row, tenant_id=tenant_id)


def _apply_document_lock(statement: sa.Select, lock: AuthoringDocumentLock) -> sa.Select:
    if lock == "none":
        return statement
    if lock == "share":
        return statement.with_for_update(read=True)
    if lock == "update":
        return statement.with_for_update()
    raise ValueError(f"unsupported authoring document lock: {lock}")


async def _flush_or_translate(session: AsyncSession, *, context: str) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        message = str(exc.orig or exc)
        if context == "document" and any(
            name in message
            for name in (
                "job_authoring_documents_pkey",
                "uq_ja_docs_tenant_document",
                "uq_ja_docs_tenant_session",
            )
        ):
            raise AuthoringError(AuthoringErrorCode.DOCUMENT_ALREADY_EXISTS) from exc
        if any(
            name in message
            for name in (
                "job_authoring_revisions_pkey",
                "uq_ja_revs_tenant_revision",
                "uq_ja_revs_tenant_command",
                "job_authoring_proposals_pkey",
                "uq_ja_props_tenant_proposal",
                "uq_ja_props_decision_command",
            )
        ):
            raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT) from exc
        if "uq_ja_revs_document_number" in message:
            raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT) from exc
        raise _corrupt("authoring write violated an unexpected database invariant") from exc


class SqlAlchemyAuthoringDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _hydrate(
        self, row: JobAuthoringDocumentRow, tenant_id: UUID
    ) -> AuthoringDocumentRecord:
        if row.tenant_id != tenant_id:
            raise _corrupt(
                "document tenant does not match query scope",
                document_id=row.document_id,
            )
        head = await _load_revision(self._s, tenant_id, row.head_revision_id)
        if head is None:
            raise _corrupt(
                "document head revision is missing", document_id=row.document_id
            )
        revision = head.revision
        if (
            revision.document_id != row.document_id
            or revision.revision_number != row.head_revision_number
            or revision.snapshot_hash != row.head_revision_hash
            or revision.snapshot.session_id != row.session_id
        ):
            raise _corrupt(
                "document head pointer does not match revision",
                document_id=row.document_id,
            )
        try:
            return AuthoringDocumentRecord(
                document_id=row.document_id,
                tenant_id=row.tenant_id,
                session_id=row.session_id,
                head_revision_id=row.head_revision_id,
                head_revision_number=row.head_revision_number,
                head_revision_hash=row.head_revision_hash,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )
        except ValidationError as exc:
            raise _corrupt(
                "persisted document row failed validation",
                document_id=row.document_id,
            ) from exc

    async def get(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        lock: AuthoringDocumentLock = "none",
    ) -> AuthoringDocumentRecord | None:
        statement = _apply_document_lock(
            sa.select(JobAuthoringDocumentRow).where(
                JobAuthoringDocumentRow.tenant_id == tenant_id,
                JobAuthoringDocumentRow.document_id == document_id,
            ),
            lock,
        )
        row = (await self._s.execute(statement)).scalar_one_or_none()
        return None if row is None else await self._hydrate(row, tenant_id)

    async def get_by_session(
        self,
        tenant_id: UUID,
        session_id: UUID,
        *,
        lock: AuthoringDocumentLock = "none",
    ) -> AuthoringDocumentRecord | None:
        statement = _apply_document_lock(
            sa.select(JobAuthoringDocumentRow).where(
                JobAuthoringDocumentRow.tenant_id == tenant_id,
                JobAuthoringDocumentRow.session_id == session_id,
            ),
            lock,
        )
        row = (await self._s.execute(statement)).scalar_one_or_none()
        return None if row is None else await self._hydrate(row, tenant_id)

    async def add(self, record: AuthoringDocumentRecord) -> None:
        self._s.add(JobAuthoringDocumentRow(**record.model_dump()))
        await _flush_or_translate(self._s, context="document")

    async def compare_and_set_head(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        expected_revision_id: UUID,
        expected_revision_number: int,
        expected_revision_hash: str,
        new_revision_id: UUID,
        new_revision_number: int,
        new_revision_hash: str,
        updated_at: datetime,
    ) -> bool:
        result = await self._s.execute(
            sa.update(JobAuthoringDocumentRow)
            .where(
                JobAuthoringDocumentRow.tenant_id == tenant_id,
                JobAuthoringDocumentRow.document_id == document_id,
                JobAuthoringDocumentRow.head_revision_id == expected_revision_id,
                JobAuthoringDocumentRow.head_revision_number
                == expected_revision_number,
                JobAuthoringDocumentRow.head_revision_hash
                == expected_revision_hash,
            )
            .values(
                head_revision_id=new_revision_id,
                head_revision_number=new_revision_number,
                head_revision_hash=new_revision_hash,
                updated_at=updated_at,
            )
            .returning(JobAuthoringDocumentRow.document_id)
        )
        return result.first() is not None


class SqlAlchemyAuthoringRevisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(
        self, tenant_id: UUID, revision_id: UUID
    ) -> AuthoringRevisionRecord | None:
        return await _load_revision(self._s, tenant_id, revision_id)

    async def get_by_command_id(
        self, tenant_id: UUID, command_id: UUID
    ) -> AuthoringRevisionRecord | None:
        row = (
            await self._s.execute(
                sa.select(JobAuthoringRevisionRow).where(
                    JobAuthoringRevisionRow.tenant_id == tenant_id,
                    JobAuthoringRevisionRow.command_id == command_id,
                )
            )
        ).scalar_one_or_none()
        return None if row is None else await _hydrate_revision(
            self._s, row, tenant_id=tenant_id
        )

    async def add(
        self,
        tenant_id: UUID,
        revision: JobDocumentRevision,
        command: AuthoringCommand,
    ) -> None:
        if command.tenant_id != tenant_id or command.command_id != revision.command_id:
            raise _corrupt(
                "revision write scope does not match command",
                revision_id=revision.revision_id,
            )
        if revision.snapshot.document_id != revision.document_id:
            raise _corrupt(
                "revision write snapshot document mismatch",
                revision_id=revision.revision_id,
            )
        command_document = getattr(command, "document_id", revision.document_id)
        if command_document != revision.document_id:
            raise _corrupt(
                "revision write command document mismatch",
                revision_id=revision.revision_id,
            )
        command_json = canonical_json(command)
        snapshot_json = canonical_json(revision.snapshot)
        self._s.add(
            JobAuthoringRevisionRow(
                revision_id=revision.revision_id,
                tenant_id=tenant_id,
                document_id=revision.document_id,
                revision_number=revision.revision_number,
                parent_revision_id=revision.parent_revision_id,
                source_kind=revision.source_kind,
                command_schema_id=command.schema_version,
                command_id=command.command_id,
                command_json=command_json,
                command_hash=canonical_hash(command),
                snapshot_schema_id=revision.snapshot.schema_version,
                snapshot_json=snapshot_json,
                snapshot_hash=revision.snapshot_hash,
                occurred_at=revision.occurred_at,
                created_at=revision.occurred_at,
            )
        )
        await _flush_or_translate(self._s, context="revision")


async def _hydrate_proposal(
    session: AsyncSession,
    row: JobAuthoringProposalRow,
    *,
    tenant_id: UUID,
) -> AuthoringProposalRecord:
    if row.tenant_id != tenant_id:
        raise _corrupt(
            "proposal tenant does not match query scope",
            proposal_id=row.proposal_id,
        )
    if row.proposal_schema_id != _PROPOSAL_SCHEMA:
        raise _corrupt(
            "persisted proposal schema is unsupported",
            proposal_id=row.proposal_id,
            schema_id=row.proposal_schema_id,
        )
    proposal = _load_model(
        AiTaskBundleProposal,
        row.proposal_json,
        row.proposal_hash,
        label="task proposal",
        proposal_id=row.proposal_id,
    )
    mismatches = [
        name
        for name, column, nested in (
            ("proposal_id", row.proposal_id, proposal.proposal_id),
            ("document_id", row.document_id, proposal.document_id),
            ("base_revision_id", row.base_revision_id, proposal.base_revision_id),
            ("base_revision_hash", row.base_revision_hash, proposal.base_revision_hash),
            (
                "evidence_state_version",
                row.evidence_state_version,
                proposal.evidence_state_version,
            ),
            ("evidence_state_hash", row.evidence_state_hash, proposal.evidence_state_hash),
            ("source_kind", row.source_kind, proposal.source_kind),
            ("source_id", row.source_id, proposal.source_id),
            ("created_at", row.created_at, proposal.created_at),
        )
        if column != nested
    ]
    if mismatches:
        raise _corrupt(
            "proposal normalized columns do not match payload",
            proposal_id=row.proposal_id,
            mismatched=",".join(mismatches),
        )

    base = await _load_revision(session, tenant_id, row.base_revision_id)
    if base is None or base.revision.document_id != row.document_id:
        raise _corrupt(
            "proposal base revision is missing or belongs to another document",
            proposal_id=row.proposal_id,
        )
    if (
        base.revision.snapshot_hash != row.base_revision_hash
        or base.revision.snapshot.session_id != proposal.session_id
    ):
        raise _corrupt(
            "proposal base authority does not match persisted revision",
            proposal_id=row.proposal_id,
        )

    decision: EmployeeProposalDecision | None = None
    if row.decision_json is not None:
        if (
            row.decision_schema_id != _DECISION_SCHEMA
            or row.decision_hash is None
        ):
            raise _corrupt(
                "proposal decision metadata is incomplete",
                proposal_id=row.proposal_id,
            )
        decision = _load_model(
            EmployeeProposalDecision,
            row.decision_json,
            row.decision_hash,
            label="employee proposal decision",
            proposal_id=row.proposal_id,
        )
        if decision.schema_version != row.decision_schema_id:
            raise _corrupt(
                "decision schema column does not match payload",
                proposal_id=row.proposal_id,
            )
    elif any(
        value is not None
        for value in (
            row.decision_command_id,
            row.decision_schema_id,
            row.decision_hash,
        )
    ):
        raise _corrupt(
            "proposal decision columns are incomplete",
            proposal_id=row.proposal_id,
        )

    if decision is not None and (
        decision.command_id != row.decision_command_id
        or decision.proposal_id != row.proposal_id
        or decision.result_revision_id != row.result_revision_id
        or decision.decided_at != row.resolved_at
    ):
        raise _corrupt(
            "proposal decision columns do not match payload",
            proposal_id=row.proposal_id,
        )

    if row.result_revision_id is not None:
        result = await _load_revision(session, tenant_id, row.result_revision_id)
        if result is None or result.revision.document_id != row.document_id:
            raise _corrupt(
                "proposal result revision is missing or cross-document",
                proposal_id=row.proposal_id,
            )

    try:
        stale_reason = (
            ProposalStaleReason(row.stale_reason)
            if row.stale_reason is not None
            else None
        )
        view = TaskProposalView(
            proposal=proposal,
            status=row.status,
            decision=decision,
            result_revision_id=row.result_revision_id,
            stale_reason=stale_reason,
            resolved_at=row.resolved_at,
        )
        return AuthoringProposalRecord(
            tenant_id=row.tenant_id,
            view=view,
            proposal_hash=row.proposal_hash,
            created_at=row.created_at,
        )
    except (ValidationError, ValueError) as exc:
        raise _corrupt(
            "persisted proposal lifecycle failed validation",
            proposal_id=row.proposal_id,
        ) from exc


def _terminal_shape_is_valid(
    status: ProposalStatus,
    decision: EmployeeProposalDecision | None,
    result_revision_id: UUID | None,
    stale_reason: ProposalStaleReason | None,
) -> bool:
    if status == "accepted":
        return (
            decision is not None
            and decision.action == "accept"
            and result_revision_id is not None
            and decision.result_revision_id == result_revision_id
            and stale_reason is None
        )
    if status == "edited":
        return (
            decision is not None
            and decision.action == "edit"
            and result_revision_id is not None
            and decision.result_revision_id == result_revision_id
            and stale_reason is None
        )
    if status == "rejected":
        return (
            decision is not None
            and decision.action == "reject"
            and result_revision_id is None
            and stale_reason is None
        )
    if status == "stale":
        return decision is None and result_revision_id is None and stale_reason is not None
    return False


class SqlAlchemyAuthoringProposalRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def _one(
        self, statement: sa.Select, tenant_id: UUID
    ) -> AuthoringProposalRecord | None:
        row = (await self._s.execute(statement)).scalar_one_or_none()
        return None if row is None else await _hydrate_proposal(
            self._s, row, tenant_id=tenant_id
        )

    async def get(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        *,
        for_update: bool = False,
    ) -> AuthoringProposalRecord | None:
        statement = sa.select(JobAuthoringProposalRow).where(
            JobAuthoringProposalRow.tenant_id == tenant_id,
            JobAuthoringProposalRow.proposal_id == proposal_id,
        )
        if for_update:
            statement = statement.with_for_update()
        return await self._one(statement, tenant_id)

    async def get_by_decision_command_id(
        self, tenant_id: UUID, command_id: UUID
    ) -> AuthoringProposalRecord | None:
        return await self._one(
            sa.select(JobAuthoringProposalRow).where(
                JobAuthoringProposalRow.tenant_id == tenant_id,
                JobAuthoringProposalRow.decision_command_id == command_id,
            ),
            tenant_id,
        )

    async def add(self, tenant_id: UUID, proposal: AiTaskBundleProposal) -> None:
        proposal_json = canonical_json(proposal)
        self._s.add(
            JobAuthoringProposalRow(
                proposal_id=proposal.proposal_id,
                tenant_id=tenant_id,
                document_id=proposal.document_id,
                base_revision_id=proposal.base_revision_id,
                base_revision_hash=proposal.base_revision_hash,
                evidence_state_version=proposal.evidence_state_version,
                evidence_state_hash=proposal.evidence_state_hash,
                source_kind=proposal.source_kind,
                source_id=proposal.source_id,
                proposal_schema_id=proposal.schema_version,
                proposal_json=proposal_json,
                proposal_hash=canonical_hash(proposal),
                status="pending",
                decision_command_id=None,
                decision_schema_id=None,
                decision_json=None,
                decision_hash=None,
                result_revision_id=None,
                stale_reason=None,
                created_at=proposal.created_at,
                resolved_at=None,
                updated_at=proposal.created_at,
            )
        )
        await _flush_or_translate(self._s, context="proposal")

    async def decide(
        self,
        tenant_id: UUID,
        proposal_id: UUID,
        *,
        status: ProposalStatus,
        decision: EmployeeProposalDecision | None,
        result_revision_id: UUID | None,
        stale_reason: ProposalStaleReason | None,
        resolved_at: datetime,
        updated_at: datetime,
    ) -> bool:
        if not _terminal_shape_is_valid(
            status, decision, result_revision_id, stale_reason
        ):
            raise _corrupt(
                "invalid pending-to-terminal proposal write shape",
                proposal_id=proposal_id,
            )
        decision_json = canonical_json(decision) if decision is not None else None
        values = {
            "status": status,
            "decision_command_id": decision.command_id if decision else None,
            "decision_schema_id": decision.schema_version if decision else None,
            "decision_json": decision_json,
            "decision_hash": canonical_hash(decision) if decision else None,
            "result_revision_id": result_revision_id,
            "stale_reason": stale_reason.value if stale_reason else None,
            "resolved_at": resolved_at,
            "updated_at": updated_at,
        }
        try:
            result = await self._s.execute(
                sa.update(JobAuthoringProposalRow)
                .where(
                    JobAuthoringProposalRow.tenant_id == tenant_id,
                    JobAuthoringProposalRow.proposal_id == proposal_id,
                    JobAuthoringProposalRow.status == "pending",
                )
                .values(**values)
                .returning(JobAuthoringProposalRow.proposal_id)
            )
        except IntegrityError as exc:
            message = str(exc.orig or exc)
            if "uq_ja_props_decision_command" in message:
                raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT) from exc
            raise _corrupt(
                "proposal decision violated a database invariant",
                proposal_id=proposal_id,
            ) from exc
        rows = result.all()
        if len(rows) > 1:
            raise _corrupt(
                "proposal decision updated more than one row",
                proposal_id=proposal_id,
            )
        return len(rows) == 1

    async def mark_other_pending_stale(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        keep_proposal_id: UUID | None,
        reason: ProposalStaleReason,
        resolved_at: datetime,
        updated_at: datetime,
    ) -> tuple[UUID, ...]:
        predicates = [
            JobAuthoringProposalRow.tenant_id == tenant_id,
            JobAuthoringProposalRow.document_id == document_id,
            JobAuthoringProposalRow.status == "pending",
        ]
        if keep_proposal_id is not None:
            predicates.append(JobAuthoringProposalRow.proposal_id != keep_proposal_id)
        result = await self._s.execute(
            sa.update(JobAuthoringProposalRow)
            .where(*predicates)
            .values(
                status="stale",
                stale_reason=reason.value,
                resolved_at=resolved_at,
                updated_at=updated_at,
            )
            .returning(JobAuthoringProposalRow.proposal_id)
        )
        return tuple(sorted((row.proposal_id for row in result.all()), key=lambda x: x.bytes))

    async def list(
        self,
        tenant_id: UUID,
        document_id: UUID,
        *,
        statuses: tuple[ProposalStatus, ...],
    ) -> tuple[AuthoringProposalRecord, ...]:
        if not statuses:
            return ()
        rows = (
            await self._s.execute(
                sa.select(JobAuthoringProposalRow)
                .where(
                    JobAuthoringProposalRow.tenant_id == tenant_id,
                    JobAuthoringProposalRow.document_id == document_id,
                    JobAuthoringProposalRow.status.in_(statuses),
                )
                .order_by(
                    JobAuthoringProposalRow.created_at.asc(),
                    JobAuthoringProposalRow.proposal_id.asc(),
                )
            )
        ).scalars().all()
        return tuple(
            [
                await _hydrate_proposal(self._s, row, tenant_id=tenant_id)
                for row in rows
            ]
        )

    async def list_for_digest(
        self, tenant_id: UUID, document_id: UUID
    ) -> DigestProposalSummary:
        counts = (
            await self._s.execute(
                sa.select(
                    sa.func.count()
                    .filter(JobAuthoringProposalRow.status == "pending")
                    .label("pending_count"),
                    sa.func.count()
                    .filter(JobAuthoringProposalRow.status == "stale")
                    .label("stale_count"),
                ).where(
                    JobAuthoringProposalRow.tenant_id == tenant_id,
                    JobAuthoringProposalRow.document_id == document_id,
                )
            )
        ).one()
        pending = (
            await self._s.execute(
                sa.select(
                    JobAuthoringProposalRow.created_at,
                    JobAuthoringProposalRow.proposal_id,
                )
                .where(
                    JobAuthoringProposalRow.tenant_id == tenant_id,
                    JobAuthoringProposalRow.document_id == document_id,
                    JobAuthoringProposalRow.status == "pending",
                )
                .order_by(
                    JobAuthoringProposalRow.created_at.asc(),
                    JobAuthoringProposalRow.proposal_id.asc(),
                )
                .limit(_DIGEST_PENDING_LIMIT)
            )
        ).all()
        return DigestProposalSummary(
            pending=tuple((row.created_at, row.proposal_id) for row in pending),
            pending_count=counts.pending_count,
            stale_count=counts.stale_count,
        )


class SqlAlchemyAuthoringEvidenceReader:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def lock_session_state(
        self, tenant_id: UUID, session_id: UUID
    ) -> EvidenceSourceSnapshot:
        row = (
            await self._s.execute(
                sa.select(VNextSessionRow)
                .where(
                    VNextSessionRow.tenant_id == tenant_id,
                    VNextSessionRow.session_id == session_id,
                )
                .with_for_update(read=True)
            )
        ).scalar_one_or_none()
        if row is None:
            raise AuthoringError(
                AuthoringErrorCode.EVIDENCE_INVALID,
                session_id=str(session_id),
            )
        try:
            state = vnext_serialization.load_state(
                row.state_json,
                row.state_hash,
                session_id=row.session_id,
                state_version=row.state_version,
            )
        except VNextPersistenceError as exc:
            raise _corrupt(
                "persisted interview state failed Evidence bridge validation",
                session_id=session_id,
            ) from exc
        nested = state.session
        mismatches = [
            name
            for name, column, value in (
                ("tenant_id", row.tenant_id, nested.tenant_id),
                ("profile_id", row.profile_id, nested.profile_id),
                ("architecture_id", row.architecture_id, nested.architecture_id),
                ("workflow_version", row.workflow_version, nested.workflow_version),
                (
                    "reference_snapshot_id",
                    row.reference_snapshot_id,
                    nested.reference_snapshot_id,
                ),
                ("status", row.status, nested.status.value),
                ("state_schema_version", row.state_schema_version, state.schema_version),
                ("created_at", row.created_at, nested.created_at),
                ("updated_at", row.updated_at, nested.updated_at),
            )
            if column != value
        ]
        if mismatches:
            raise _corrupt(
                "interview session columns do not match state payload",
                session_id=session_id,
                mismatched=",".join(mismatches),
            )
        active = tuple(
            sorted(
                (
                    EvidenceBasisRef(
                        evidence_id=evidence.evidence_id,
                        evidence_hash=vnext_canonical_hash(evidence),
                    )
                    for evidence in state.evidence
                    if evidence.status == EvidenceStatus.ACTIVE
                ),
                key=lambda item: item.evidence_id.bytes,
            )
        )
        return EvidenceSourceSnapshot(
            tenant_id=tenant_id,
            session_id=session_id,
            state_version=row.state_version,
            state_hash=row.state_hash,
            active_evidence=active,
        )


class SqlAlchemyAuthoringUnitOfWork:
    """One instance owns one AsyncSession and is deliberately non-reentrant."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory
        self._session: AsyncSession | None = None
        self._entered = False
        self._committed = False

    async def __aenter__(self) -> "SqlAlchemyAuthoringUnitOfWork":
        if self._entered:
            raise RuntimeError("AuthoringUnitOfWork instances are not re-enterable")
        self._entered = True
        self._session = self._factory()
        self.documents = SqlAlchemyAuthoringDocumentRepository(self._session)
        self.revisions = SqlAlchemyAuthoringRevisionRepository(self._session)
        self.proposals = SqlAlchemyAuthoringProposalRepository(self._session)
        self.evidence = SqlAlchemyAuthoringEvidenceReader(self._session)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self._session is not None
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        assert self._session is not None
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            message = str(exc.orig or exc)
            if "uq_ja_props_decision_command" in message:
                raise AuthoringError(AuthoringErrorCode.IDEMPOTENCY_CONFLICT) from exc
            if "uq_ja_revs_document_number" in message:
                raise AuthoringError(AuthoringErrorCode.REVISION_CONFLICT) from exc
            raise _corrupt("authoring transaction commit failed integrity checks") from exc
        except Exception:
            await self._session.rollback()
            raise
        self._committed = True

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
