"""Knowledge/skill edits participate in the existing formal JD transaction."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import capability_persistence, persistence, task_persistence
from caliburn.features.job_description.capabilities import (
    EditJdCapabilities,
    JdCapabilitiesRevision,
)
from caliburn.features.job_description.capability_changes import (
    apply_capability_change,
    capability_change_payload,
)
from caliburn.features.job_description.models import (
    JdCommandConflictError,
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
    session: AsyncSession, job_file_id: UUID, command: EditJdCapabilities
) -> JdCapabilitiesRevision | None:
    operation = await persistence.read_operation(session, job_file_id, command.command_id)
    if operation is None:
        return None
    if (
        operation.kind != "edit_capabilities"
        or operation.expected_revision_id != command.expected_revision_id
        or operation.request_payload != capability_change_payload(command.change)
    ):
        raise JdCommandConflictError("command_id was already used with different JD intent")
    return await read_capabilities_at(session, job_file_id, operation.result_revision_id)


async def edit_capabilities(
    session: AsyncSession, job_file_id: UUID, command: EditJdCapabilities
) -> JdCapabilitiesRevision:
    """Call after file lock, original-result lookup and manual admission; do not commit."""
    current = await read_capabilities(session, job_file_id)
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
        document = await persistence.read_document(session, job_file_id)
        document.current_revision_id = result.revision_id
    session.add(
        persistence.JdOperationRecord(
            job_file_id=job_file_id,
            command_id=command.command_id,
            kind="edit_capabilities",
            expected_revision_id=command.expected_revision_id,
            result_revision_id=result.revision_id,
            request_payload=capability_change_payload(command.change),
        )
    )
    await session.flush()
    return result
