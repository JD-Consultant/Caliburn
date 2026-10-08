"""Fixed JD evidence edits participate in the caller's existing short transaction."""

from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import (
    persistence,
    revision_editing,
    source_persistence,
    work_queries,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import (
    JdCommandConflictError,
    JdProfileRevision,
    StaleJdRevisionError,
)
from caliburn.features.job_description.source_changes import (
    apply_source_changes,
    source_change_payload,
)
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import InvalidJdSourceError, ReviseJdSources


async def recover_source_result(
    session: AsyncSession,
    job_file_id: UUID,
    command: ReviseJdSources,
    *,
    candidate: JdCandidateScope | None = None,
) -> UUID | None:
    original = await revision_editing.read_edit_operation(
        session, job_file_id, command.command_id, candidate
    )
    if original is None:
        return None
    if (
        original.kind != "edit_sources"
        or original.expected_revision_id != command.expected_revision_id
        or original.request_payload != source_change_payload(command)
    ):
        raise JdCommandConflictError("command_id was used with different source intent")
    return original.result_revision_id


async def revise_sources(
    session: AsyncSession,
    job_file_id: UUID,
    command: ReviseJdSources,
    *,
    candidate: JdCandidateScope | None = None,
) -> UUID:
    """Call after scope/replay checks; App resolves source identities, not models."""
    current = await revision_editing.read_edit_revision(session, job_file_id, candidate)
    if current != command.expected_revision_id:
        raise StaleJdRevisionError("The selected JD source target is no longer current")
    profile = await persistence.read_revision(session, job_file_id, current)
    work = await work_queries.read_work_at(session, job_file_id, current)
    if command.target not in source_target_contents(profile.profile, work):
        raise InvalidJdSourceError("The selected JD source target does not exist")
    original = await source_persistence.read_source_references(session, job_file_id, current)
    updated = apply_source_changes(original, command)
    result = current
    if updated != original:
        result = uuid4()
        await persistence.insert_revision(
            session,
            job_file_id,
            JdProfileRevision(result, profile.profile),
            parent_revision_id=current,
        )
    await revision_editing.record_edit(
        session,
        job_file_id,
        command_id=command.command_id,
        kind="edit_sources",
        expected_revision_id=current,
        result_revision_id=result,
        request_payload=source_change_payload(command),
        candidate=candidate,
        source_references=updated,
    )
    return result
