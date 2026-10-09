"""Knowledge/skill edits share fixed JD revisions and a caller-selected editing scope."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    capability_persistence,
    persistence,
    revision_editing,
    task_persistence,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    EditJdCapabilities,
    JdCapabilitiesRevision,
)
from caliburn.features.job_description.capability_changes import (
    apply_capability_change,
    capability_change_payload,
)
from caliburn.features.job_description.models import (
    JdProfileRevision,
    StaleJdRevisionError,
)


async def read_capabilities_at(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdCapabilitiesRevision:
    return JdCapabilitiesRevision(
        revision_id,
        await capability_persistence.read_capabilities(session, job_file_id, revision_id),
        await capability_persistence.read_task_links(session, job_file_id, revision_id),
    )


async def read_capabilities(session: AsyncSession, job_file_id: UUID) -> JdCapabilitiesRevision:
    head = await persistence.read_document(session, job_file_id)
    return await read_capabilities_at(session, job_file_id, head.current_revision_id)


async def recover_capability_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdCapabilities,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdCapabilitiesRevision | None:
    operation = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if operation is None:
        return None
    revision_editing.require_matching_edit_intent(
        operation,
        kind="edit_capabilities",
        expected_revision_id=command.expected_revision_id,
        request_payload=capability_change_payload(command.change),
    )
    return await read_capabilities_at(session, job_file_id, operation.result_revision_id)


async def edit_capabilities(
    session: AsyncSession,
    job_file_id: UUID,
    command: EditJdCapabilities,
    *,
    candidate: JdCandidateScope | None = None,
) -> JdCapabilitiesRevision:
    """Call after file lock, original-result lookup and scope admission; do not commit."""
    revision_id = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    current = await read_capabilities_at(session, job_file_id, revision_id)
    if current.revision_id != command.expected_revision_id:
        raise StaleJdRevisionError("Read the current JD before submitting a new edit")
    task_ids = await task_persistence.read_task_ids(session, job_file_id, current.revision_id)
    capabilities, links, new_content = apply_capability_change(
        current.capabilities,
        current.task_links,
        task_ids,
        command.change,
    )
    result = current
    if capabilities != current.capabilities or links != current.task_links:
        if new_content is not None:
            await capability_persistence.insert_capability_content(
                session, job_file_id, new_content
            )
        profile = await persistence.read_revision(session, job_file_id, current.revision_id)
        result = JdCapabilitiesRevision(uuid4(), capabilities, links)
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(result.revision_id, profile.profile),
            parent_revision_id=current.revision_id,
            capabilities=capabilities,
            task_links=links,
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="edit_capabilities",
        expected_revision_id=command.expected_revision_id,
        result_revision_id=result.revision_id,
        request_payload=capability_change_payload(command.change),
        candidate=candidate,
    )
    return result
