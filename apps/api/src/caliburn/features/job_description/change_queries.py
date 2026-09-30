"""Read the original JD ledger and fixed values; execution qualification stays with its owner."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.job_description import candidate_persistence, persistence, source_persistence
from caliburn.features.job_description.models import JdProfile, ProfileField
from caliburn.features.job_description.sources import JdSourceReference
from caliburn.features.job_description.work_queries import JdWorkRevision, read_work_at


class JdChangeHistoryUnavailableError(LookupError):
    """A required historical endpoint or original operation cannot be recovered."""


@dataclass(frozen=True, slots=True)
class JdChangeSnapshot:
    profile: JdProfile
    work: JdWorkRevision
    sources: tuple[JdSourceReference, ...]


@dataclass(frozen=True, slots=True)
class ManualJdOperation:
    before_revision_id: UUID
    after_revision_id: UUID
    kind: str
    item_ids: frozenset[UUID]
    profile_fields: frozenset[ProfileField]


@dataclass(frozen=True, slots=True)
class ManualJdRange:
    base_revision_id: UUID
    start_revision_id: UUID
    initial_base: bool
    operations: tuple[ManualJdOperation, ...]


async def read_manual_change_range(
    session: AsyncSession,
    job_file_id: UUID,
    execution_id: UUID,
    *,
    start_revision_id: UUID,
    previous_completed_execution_id: UUID | None,
) -> ManualJdRange:
    """Caller supplies the completed execution selected by public history ownership."""
    current = await candidate_persistence.read_candidate(session, job_file_id, execution_id)
    if current is None or current.status != "open" or current.base_revision_id != start_revision_id:
        raise JdChangeHistoryUnavailableError(
            "The current candidate does not match the fixed start"
        )
    since = None
    if previous_completed_execution_id is None:
        base = (await persistence.read_document(session, job_file_id)).initial_revision_id
    else:
        previous = await candidate_persistence.read_candidate(
            session, job_file_id, previous_completed_execution_id
        )
        if previous is None or previous.status != "adopted":
            raise JdChangeHistoryUnavailableError("The completed Turn has no adopted JD position")
        base, since = previous.current_revision_id, previous.created_at
    chain = dict(
        await persistence.read_revision_interval(
            session,
            job_file_id,
            base_revision_id=base,
            end_revision_id=start_revision_id,
        )
    )
    if base not in chain:
        raise JdChangeHistoryUnavailableError("The fixed JD base is not a retained ancestor")
    ordered = [start_revision_id]
    while ordered[-1] != base:
        parent = chain.get(ordered[-1])
        if parent is None or parent in ordered:
            raise JdChangeHistoryUnavailableError("The JD ancestry is incomplete")
        ordered.append(parent)
    ordered.reverse()
    indexes = {revision_id: index for index, revision_id in enumerate(ordered)}
    records = await persistence.read_manual_operations(
        session,
        job_file_id,
        tuple(ordered),
        created_before=current.created_at,
        created_since=since,
    )
    effects = {
        record.result_revision_id: record.expected_revision_id
        for record in records
        if record.expected_revision_id != record.result_revision_id
    }
    if any(effects.get(revision_id) != chain[revision_id] for revision_id in ordered[1:]):
        raise JdChangeHistoryUnavailableError(
            "A formal revision lacks its original manual operation"
        )
    records = tuple(
        sorted(
            records,
            key=lambda record: (
                indexes[record.expected_revision_id],
                record.expected_revision_id != record.result_revision_id,
                record.created_at,
                record.command_id,
            ),
        )
    )
    return ManualJdRange(
        base,
        start_revision_id,
        previous_completed_execution_id is None,
        tuple(_operation(record) for record in records),
    )


async def read_change_snapshot(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID
) -> JdChangeSnapshot:
    profile = await persistence.read_revision(session, job_file_id, revision_id)
    return JdChangeSnapshot(
        profile.profile,
        await read_work_at(session, job_file_id, revision_id),
        await source_persistence.read_source_references(session, job_file_id, revision_id),
    )


def _operation(record: persistence.JdOperationRecord) -> ManualJdOperation:
    """Project target hints only; original bodies stay in the immutable revision owner."""
    item_ids: set[UUID] = set()
    fields: set[ProfileField] = set()
    identity_keys = {
        "area_id",
        "task_id",
        "detail_id",
        "capability_id",
        "collaborator_id",
        "condition_id",
        "item_id",
    }

    def visit(value: object) -> None:
        if isinstance(value, list):
            for child in value:
                visit(child)
        elif isinstance(value, dict):
            for key, child in value.items():
                if key in identity_keys and child is not None:
                    if not isinstance(child, str):
                        raise JdChangeHistoryUnavailableError("Invalid original JD target identity")
                    try:
                        item_ids.add(UUID(child))
                    except ValueError as error:
                        raise JdChangeHistoryUnavailableError(
                            "Invalid original JD target identity"
                        ) from error
                elif key == "field" and (
                    record.kind == "revise_profile" or value.get("kind") == "profile_field"
                ):
                    try:
                        fields.add(ProfileField(child))
                    except (ValueError, TypeError) as error:
                        raise JdChangeHistoryUnavailableError(
                            "Invalid original profile field"
                        ) from error
                elif isinstance(child, (dict, list)):
                    visit(child)

    if not isinstance(record.request_payload, (dict, list)):
        raise JdChangeHistoryUnavailableError("Invalid original JD operation payload")
    visit(record.request_payload)
    return ManualJdOperation(
        record.expected_revision_id,
        record.result_revision_id,
        record.kind,
        frozenset(item_ids),
        frozenset(fields),
    )
