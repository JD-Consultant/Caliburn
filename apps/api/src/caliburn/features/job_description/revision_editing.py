"""Route the same JD edit rules to a formal head or one private candidate position.

The workflow owns admission and locking. This module never commits, admits a writer,
publishes a Turn, or changes the formal head as a shortcut for editing a candidate.
"""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    area_persistence,
    candidate_persistence,
    capability_persistence,
    collaborator_persistence,
    condition_persistence,
    persistence,
    source_persistence,
    task_persistence,
    work_queries,
)
from caliburn.features.job_description.areas import (
    EditJdAreas,
    ResponsibilityArea,
    area_change_payload,
)
from caliburn.features.job_description.candidates import CandidateStateError, JdCandidateScope
from caliburn.features.job_description.capabilities import Capability, EditJdCapabilities
from caliburn.features.job_description.capability_changes import capability_change_payload
from caliburn.features.job_description.collaborators import (
    Collaborator,
    EditJdCollaborators,
    collaborator_change_payload,
)
from caliburn.features.job_description.compound_edits import CompoundItem
from caliburn.features.job_description.conditions import (
    EditJdConditions,
    JobCondition,
    condition_change_payload,
)
from caliburn.features.job_description.edit_changes import (
    JdContentEdit,
    JdEditChanges,
    apply_content_changes,
)
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    JdProfile,
    JdProfileRevision,
    ReviseJdProfile,
    StaleJdRevisionError,
    apply_profile_changes,
    profile_change_payload,
)
from caliburn.features.job_description.source_inheritance import inherited_source_references
from caliburn.features.job_description.sources import JdSourceReference
from caliburn.features.job_description.task_changes import task_edit_payload
from caliburn.features.job_description.tasks import EditJdTasks, WorkTask
from caliburn.features.job_description.work_models import JdWorkRevision


def _content_intent(command: JdContentEdit) -> tuple[str, object]:
    match command:
        case ReviseJdProfile():
            return "revise_profile", profile_change_payload(command.changes)
        case EditJdAreas():
            return "edit_areas", area_change_payload(command.change)
        case EditJdTasks():
            return "edit_tasks", task_edit_payload(command.change)
        case EditJdCapabilities():
            return "edit_capabilities", capability_change_payload(command.change)
        case EditJdCollaborators():
            return "edit_collaborators", collaborator_change_payload(command.change)
        case EditJdConditions():
            return "edit_conditions", condition_change_payload(command.change)


async def recover_content_edit(
    session: AsyncSession,
    job_file_id: UUID,
    command: JdContentEdit,
    *,
    candidate: JdCandidateScope | None = None,
) -> UUID | None:
    """只讀原結果；人工入口在新寫入准入前呼叫。"""
    operation = await read_edit_operation(session, job_file_id, command.command_id, candidate)
    if operation is None:
        return None
    kind, payload = _content_intent(command)
    require_matching_edit_intent(
        operation,
        kind=kind,
        expected_revision_id=command.expected_revision_id,
        request_payload=payload,
    )
    return operation.result_revision_id


async def apply_content_edit(
    session: AsyncSession,
    job_file_id: UUID,
    command: JdContentEdit,
    *,
    candidate: JdCandidateScope | None = None,
) -> UUID:
    """呼叫者先鎖定、查原結果並准入；本函式不 commit。"""
    current = await read_edit_revision(session, job_file_id, candidate)
    if current != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    profile = await persistence.read_revision(session, job_file_id, current)
    kind, payload = _content_intent(command)
    if (
        isinstance(command, ReviseJdProfile)
        and apply_profile_changes(profile.profile, command.changes) == profile.profile
    ):
        await record_edit(
            session,
            job_file_id,
            command_id=command.command_id,
            kind=kind,
            expected_revision_id=current,
            result_revision_id=current,
            request_payload=payload,
            candidate=candidate,
        )
        return current
    work = await work_queries.read_work_at(session, job_file_id, current)
    references = await source_persistence.read_source_references(session, job_file_id, current)
    changes = apply_content_changes(
        profile.profile, work, references, command, review_changed_content=candidate is not None
    )
    return await persist_edit(
        session,
        job_file_id,
        profile.profile,
        work,
        references,
        changes,
        command_id=command.command_id,
        kind=kind,
        request_payload=payload,
        candidate=candidate,
    )


async def _insert_content(
    session: AsyncSession, job_file_id: UUID, item: CompoundItem | None
) -> None:
    match item:
        case ResponsibilityArea():
            await area_persistence.insert_area_content(session, job_file_id, item)
        case WorkTask():
            await task_persistence.insert_task_content(session, job_file_id, item)
        case Capability():
            await capability_persistence.insert_capability_content(session, job_file_id, item)
        case Collaborator():
            await collaborator_persistence.insert_collaborator_content(session, job_file_id, item)
        case JobCondition():
            await condition_persistence.insert_condition_content(session, job_file_id, item)


async def persist_edit(
    session: AsyncSession,
    job_file_id: UUID,
    profile: JdProfile,
    work: JdWorkRevision,
    references: tuple[JdSourceReference, ...],
    changes: JdEditChanges,
    *,
    command_id: UUID,
    kind: str,
    request_payload: object,
    candidate: JdCandidateScope | None,
    result_payload: object | None = None,
) -> UUID:
    """只保存最終差異與原 receipt；未變 section 沿既有選擇複製規則。"""
    revision = work.revision_id
    if changes.differs_from(profile, work, references):
        revision = uuid4()
        await _insert_content(session, job_file_id, changes.changed_content)
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(revision, changes.profile),
            parent_revision_id=work.revision_id,
            areas=changes.work.areas if changes.work.areas != work.areas else None,
            tasks=changes.work.tasks if changes.work.tasks != work.tasks else None,
            capabilities=changes.work.capabilities
            if changes.work.capabilities != work.capabilities
            else None,
            task_links=changes.work.task_links
            if changes.work.task_links != work.task_links
            else None,
            collaborators=changes.work.collaborators
            if changes.work.collaborators != work.collaborators
            else None,
            conditions=changes.work.conditions
            if changes.work.conditions != work.conditions
            else None,
        )
    await record_edit(
        session,
        job_file_id,
        command_id=command_id,
        kind=kind,
        expected_revision_id=work.revision_id,
        result_revision_id=revision,
        request_payload=request_payload,
        candidate=candidate,
        source_references=changes.references,
        result_payload=result_payload,
    )
    return revision


async def require_open_candidate(
    session: AsyncSession, job_file_id: UUID, scope: JdCandidateScope
) -> candidate_persistence.JdCandidateRecord:
    candidate = await candidate_persistence.read_candidate(session, job_file_id, scope.execution_id)
    if candidate is None or candidate.status != "open":
        raise CandidateStateError("Candidate position is unavailable or superseded")
    formal = await persistence.read_document(session, job_file_id)
    if formal.current_revision_id != candidate.base_revision_id:
        raise StaleJdRevisionError("The formal JD no longer matches this candidate's base")
    return candidate


async def read_edit_revision(
    session: AsyncSession, job_file_id: UUID, candidate: JdCandidateScope | None
) -> UUID:
    if candidate is None:
        return (await persistence.read_document(session, job_file_id)).current_revision_id
    return (await require_open_candidate(session, job_file_id, candidate)).current_revision_id


async def read_edit_operation(
    session: AsyncSession, job_file_id: UUID, command_id: UUID, candidate: JdCandidateScope | None
) -> persistence.JdOperationRecord | None:
    operation = await persistence.read_operation(session, job_file_id, command_id)
    if operation is not None and (
        operation.candidate_execution_id != (candidate.execution_id if candidate else None)
    ):
        raise JdCommandConflictError("command_id belongs to a different JD editing scope")
    return operation


def require_matching_edit_intent(
    operation: persistence.JdOperationRecord,
    *,
    kind: str,
    expected_revision_id: UUID,
    request_payload: object,
) -> None:
    """Qualify a complete replay intent after the caller's file/candidate scope lookup."""
    if (
        operation.kind != kind
        or operation.expected_revision_id != expected_revision_id
        or operation.request_payload != request_payload
    ):
        raise JdCommandConflictError("command_id was already used with different JD intent")


async def record_edit(
    session: AsyncSession,
    job_file_id: UUID,
    *,
    command_id: UUID,
    kind: str,
    expected_revision_id: UUID,
    result_revision_id: UUID,
    request_payload: object,
    candidate: JdCandidateScope | None,
    source_references: tuple[JdSourceReference, ...] | None = None,
    result_payload: object | None = None,
) -> None:
    if result_revision_id != expected_revision_id:
        references = source_references
        if references is None:
            references = await inherited_source_references(
                session,
                job_file_id,
                expected_revision_id,
                result_revision_id,
                review_changed_content=candidate is not None,
            )
        await source_persistence.insert_source_references(
            session, job_file_id, result_revision_id, references
        )
    if candidate is None:
        document = await persistence.read_document(session, job_file_id)
        document.current_revision_id = result_revision_id
    else:
        draft = await require_open_candidate(session, job_file_id, candidate)
        draft.current_revision_id = result_revision_id
    session.add(
        persistence.JdOperationRecord(
            job_file_id=job_file_id,
            command_id=command_id,
            kind=kind,
            expected_revision_id=expected_revision_id,
            result_revision_id=result_revision_id,
            request_payload=request_payload,
            result_payload=result_payload,
            candidate_execution_id=candidate.execution_id if candidate else None,
        )
    )
    await session.flush()
