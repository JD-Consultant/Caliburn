"""Condition commands share fixed JD revisions and a caller-selected editing scope."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import condition_persistence, persistence, revision_editing
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.condition_changes import apply_condition_change
from caliburn.features.job_description.conditions import (
    EditJdConditions,
    JdConditionsRevision,
    condition_change_payload,
)
from caliburn.features.job_description.models import (
    JdProfileRevision,
    StaleJdRevisionError,
)


async def read_conditions(session: AsyncSession, job_file_id: UUID) -> JdConditionsRevision:
    head = await persistence.read_document(session, job_file_id)
    return JdConditionsRevision(
        head.current_revision_id,
        await condition_persistence.read_conditions(session, job_file_id, head.current_revision_id),
    )


async def recover_condition_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdConditions,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdConditionsRevision | None:
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if operation is None:
        return None
    revision_editing.require_matching_edit_intent(
        operation,
        kind="edit_conditions",
        expected_revision_id=command.expected_revision_id,
        request_payload=condition_change_payload(command.change),
    )
    return JdConditionsRevision(
        operation.result_revision_id,
        await condition_persistence.read_conditions(
            session, job_file_id, operation.result_revision_id
        ),
    )


async def edit_conditions(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdConditions,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdConditionsRevision:
    """Call after original-result lookup, file lock and scope admission; do not commit."""
    revision_id = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    current = JdConditionsRevision(
        revision_id, await condition_persistence.read_conditions(session, job_file_id, revision_id)
    )
    if current.revision_id != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    conditions, new_content = apply_condition_change(current.conditions, command.change)
    result = current
    if conditions != current.conditions:
        if new_content is not None:
            await condition_persistence.insert_condition_content(session, job_file_id, new_content)
        profile = await persistence.read_revision(session, job_file_id, current.revision_id)
        result = JdConditionsRevision(uuid4(), conditions)
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(result.revision_id, profile.profile),
            parent_revision_id=current.revision_id,
            conditions=conditions,
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="edit_conditions",
        expected_revision_id=command.expected_revision_id,
        result_revision_id=result.revision_id,
        request_payload=condition_change_payload(command.change),
        candidate=candidate,
    )
    return result
