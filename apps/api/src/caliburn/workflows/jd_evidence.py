"""Human evidence reads: formal JD only, original fixed chains, no alignment side effects."""

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewMessage, InterviewReadScope
from caliburn.features.job_description import persistence as jd
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.change_queries import read_change_snapshot
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.source_targets import source_target_contents
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    SourceTargetKind,
)
from caliburn.features.job_description.work_queries import JdWorkRevision, read_work_at
from caliburn.features.job_files.queries import read_job_file
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory.revisions import (
    MemoryObjectRevision,
    MemoryRevisionNotFoundError,
)
from caliburn.workflows.jd_source_queries import (
    JdSourceChanges,
    read_fixed_memory_source,
    read_memory_source_changes,
    read_memory_source_titles,
)


class JdEvidenceNotFoundError(LookupError):
    """The citation or child is not in this formal JD's selected source chain."""


class JdEvidenceStaleError(RuntimeError):
    """Reload the formal source overview rather than mixing JD revisions."""


class JdEvidenceComparisonError(ValueError):
    """The citation's reviewed JD target cannot be reconstructed reliably."""


@dataclass(frozen=True, slots=True)
class EvidenceEntry:
    citation_id: UUID
    target_label: str
    source_kind: str
    source_label: str
    needs_recheck: bool
    target: JdSourceTarget
    jd_changed: bool
    source_changed: bool


@dataclass(frozen=True, slots=True)
class EvidenceOverview:
    revision_id: UUID
    references: tuple[EvidenceEntry, ...]


@dataclass(frozen=True, slots=True)
class EvidenceLink:
    source_ref: str
    kind: str
    label: str


@dataclass(frozen=True, slots=True)
class MemoryEvidence:
    revision: MemoryObjectRevision
    references: tuple[EvidenceLink, ...]


@dataclass(frozen=True, slots=True)
class JdEvidenceChanges:
    reference: JdSourceReference
    before: tuple[str | None, ...]
    after: tuple[str | None, ...]
    source_changes: JdSourceChanges | None


SPEAKER_LABELS = {"app": "系統開場", "employee": "員工", "consultant": "顧問"}


def interview_label(message: InterviewMessage) -> str:
    return f"訪談序號 {message.interview_sequence} · {SPEAKER_LABELS[message.speaker]}"


class JdEvidenceWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_overview(self, job_file_id: UUID) -> EvidenceOverview:
        async with self.sessions() as session:
            await read_job_file(session, job_file_id)
            document = await jd.read_document(session, job_file_id)
            revision_id = document.current_revision_id
            references = await source_persistence.read_source_references(
                session, job_file_id, revision_id
            )
            work = await read_work_at(session, job_file_id, revision_id)
            labels = _target_labels(work)
            snapshot = await memory.read_latest_snapshot(session, job_file_id)
            # A later frontier may grow, but cannot precede this already-published snapshot.
            frontier = await interviews.read_history_frontier(session, job_file_id)
            entries = []
            # Repeated citations share source reads for this fixed overview only.
            source_labels: dict[InterviewSource | MemorySource, tuple[str, bool]] = {}
            for reference in references:
                source = reference.source
                if source not in source_labels:
                    if isinstance(source, InterviewSource):
                        (message,) = await interviews.read_interview_sources(
                            session,
                            InterviewReadScope(job_file_id, frontier),
                            source_ids=(source.source_id,),
                        )
                        source_labels[source] = (interview_label(message), False)
                    else:
                        if snapshot is None:
                            raise MemoryRevisionNotFoundError("Published comparison is unavailable")
                        # Publication fixes the situation chain in the root revision,
                        # including a new revision for changed links with identical text.
                        # Expand child bodies only when the user requests the actual diff.
                        current, historical, changed = await read_memory_source_titles(
                            session,
                            job_file_id=job_file_id,
                            source=source,
                            snapshot_id=snapshot.snapshot_id,
                            interview_through_sequence=frontier,
                        )
                        # The label describes original evidence, not its current replacement.
                        original_label = historical or current
                        if original_label is None:
                            raise MemoryRevisionNotFoundError(
                                "The original evidence title is unavailable"
                            )
                        source_labels[source] = (original_label, changed)
                label, changed = source_labels[source]
                entries.append(
                    EvidenceEntry(
                        reference.citation_id,
                        labels[reference.target],
                        "interview" if isinstance(source, InterviewSource) else source.layer.value,
                        label,
                        reference.needs_review or changed,
                        reference.target,
                        reference.needs_review,
                        changed,
                    )
                )
            return EvidenceOverview(revision_id, tuple(entries))

    async def read_content(
        self,
        job_file_id: UUID,
        revision_id: UUID,
        citation_id: UUID,
        source_ref: str | None = None,
    ) -> MemoryEvidence | InterviewMessage:
        async with self.sessions() as session:
            reference, frontier = await _formal_reference(
                session, job_file_id, revision_id, citation_id
            )
            source = reference.source
            if isinstance(source, InterviewSource):
                (message,) = await interviews.read_interview_sources(
                    session,
                    InterviewReadScope(job_file_id, frontier),
                    source_ids=(source.source_id,),
                )
                if source_ref not in (None, f"interview_{message.interview_sequence}"):
                    raise JdEvidenceNotFoundError("No such source in this citation")
                return message
            root = await read_fixed_memory_source(
                session, job_file_id=job_file_id, source=source, interview_through_sequence=frontier
            )
            snapshot = await memory.read_snapshot(session, job_file_id, source.snapshot_id)
            scope = InterviewReadScope(job_file_id, snapshot.covered_through_sequence)
            if source_ref is None:
                return await _memory_content(session, source, root, scope)
            # Select children by fixed edges, never a caller-supplied arbitrary revision.
            revisions = [root]
            for link in sorted(root.work_situation_references, key=lambda item: item.object_id):
                child = await memory.read_snapshot_object(
                    session, job_file_id, source.snapshot_id, link.object_id
                )
                if child.revision_id != link.revision_id:
                    raise MemoryRevisionNotFoundError("The fixed evidence chain is inconsistent")
                if source_ref == f"situation_{child.object_id.hex}":
                    return await _memory_content(session, source, child, scope)
                revisions.append(child)
            source_ids = tuple(
                dict.fromkeys(
                    source_id
                    for revision in revisions
                    for source_id in revision.interview_references
                )
            )
            messages = (
                await interviews.read_interview_sources(session, scope, source_ids=source_ids)
                if source_ids
                else []
            )
            for message in messages:
                if source_ref == f"interview_{message.interview_sequence}":
                    return message
            raise JdEvidenceNotFoundError("No such source in this citation")

    async def read_changes(
        self, job_file_id: UUID, revision_id: UUID, citation_id: UUID
    ) -> JdEvidenceChanges:
        async with self.sessions() as session:
            snapshot = await memory.read_latest_snapshot(session, job_file_id)
            reference, frontier = await _formal_reference(
                session, job_file_id, revision_id, citation_id
            )
            before, after = await _reviewed_target_contents(
                session, job_file_id, revision_id, reference
            )
            if isinstance(reference.source, InterviewSource):
                await interviews.read_interview_sources(
                    session,
                    InterviewReadScope(job_file_id, frontier),
                    source_ids=(reference.source.source_id,),
                )
                return JdEvidenceChanges(reference, before, after, None)
            if snapshot is None:
                raise MemoryRevisionNotFoundError("Published comparison is unavailable")
            source_changes = await read_memory_source_changes(
                session,
                job_file_id=job_file_id,
                reference=reference,
                snapshot_id=snapshot.snapshot_id,
                interview_through_sequence=frontier,
            )
            return JdEvidenceChanges(reference, before, after, source_changes)


async def _reviewed_target_contents(
    session: AsyncSession,
    job_file_id: UUID,
    revision_id: UUID,
    reference: JdSourceReference,
) -> tuple[tuple[str | None, ...], tuple[str | None, ...]]:
    reviewed_id = reference.reviewed_revision_id
    if reviewed_id is None:
        raise JdEvidenceComparisonError("The citation has no persisted review baseline")
    reviewed_references = await source_persistence.read_source_references(
        session, job_file_id, reviewed_id
    )
    reviewed = next(
        (item for item in reviewed_references if item.citation_id == reference.citation_id), None
    )
    if (
        reviewed is None
        or reviewed.target != reference.target
        or reviewed.source != reference.source
        or reviewed.needs_review
        or reviewed.reviewed_revision_id != reviewed_id
    ):
        raise JdEvidenceComparisonError("The citation does not match its stored review baseline")
    # Fixed reference FKs guarantee these revisions exist in this file. Read each
    # endpoint by identity; the previous Turn is unrelated to citation review.
    before = await read_change_snapshot(session, job_file_id, reviewed_id)
    after = (
        before
        if reviewed_id == revision_id
        else await read_change_snapshot(session, job_file_id, revision_id)
    )
    old_targets = source_target_contents(before.profile, before.work)
    new_targets = source_target_contents(after.profile, after.work)
    if reference.target not in old_targets or reference.target not in new_targets:
        raise JdEvidenceComparisonError("The reviewed JD target is unavailable")
    return old_targets[reference.target], new_targets[reference.target]


async def _formal_reference(
    session: AsyncSession, job_file_id: UUID, revision_id: UUID, citation_id: UUID
) -> tuple[JdSourceReference, int]:
    await read_job_file(session, job_file_id)
    document = await jd.read_document(session, job_file_id)
    if revision_id != document.current_revision_id:
        raise JdEvidenceStaleError("The formal JD changed; reload its evidence overview")
    references = await source_persistence.read_source_references(session, job_file_id, revision_id)
    reference = next((item for item in references if item.citation_id == citation_id), None)
    if reference is None:
        raise JdEvidenceNotFoundError("No such citation in this formal JD")
    return reference, await interviews.read_history_frontier(session, job_file_id)


async def _memory_content(
    session: AsyncSession,
    source: MemorySource,
    revision: MemoryObjectRevision,
    scope: InterviewReadScope,
) -> MemoryEvidence:
    links = []
    for reference in sorted(revision.work_situation_references, key=lambda item: item.object_id):
        child = await memory.read_snapshot_object(
            session, scope.job_file_id, source.snapshot_id, reference.object_id
        )
        if child.revision_id != reference.revision_id:
            raise MemoryRevisionNotFoundError("The fixed evidence chain is inconsistent")
        links.append(
            EvidenceLink(f"situation_{child.object_id.hex}", "work_situation", child.content.title)
        )
    if revision.interview_references:
        messages = await interviews.read_interview_sources(
            session, scope, source_ids=tuple(revision.interview_references)
        )
        links.extend(
            EvidenceLink(
                f"interview_{message.interview_sequence}", "interview", interview_label(message)
            )
            for message in sorted(messages, key=lambda value: value.interview_sequence)
        )
    return MemoryEvidence(revision, tuple(links))


def _target_labels(work: JdWorkRevision) -> dict[JdSourceTarget, str]:
    labels = {
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field): label
        for field, label in (
            (ProfileField.JOB_TITLE, "職務名稱"),
            (ProfileField.ORGANIZATION_UNIT, "所屬單位"),
            (ProfileField.REPORTS_TO, "直屬主管"),
            (ProfileField.PURPOSE, "職務目的"),
        )
    }
    for area in work.areas:
        labels[JdSourceTarget(SourceTargetKind.AREA, area.area_id)] = (
            f"職責：{area.title or area.scope_text}"
        )
    for task in work.tasks:
        label = f"任務：{task.title or task.description}"
        labels[JdSourceTarget(SourceTargetKind.TASK, task.task_id)] = label
        for detail in task.details:
            labels[
                JdSourceTarget(SourceTargetKind.DETAIL, detail.detail_id, task_id=task.task_id)
            ] = f"{label} · {'成果' if detail.kind.value == 'outcome' else '要求'}：{detail.text}"
    capabilities = {item.capability_id: item for item in work.capabilities}
    for capability in work.capabilities:
        label = "知識" if capability.kind.value == "knowledge" else "技能"
        labels[JdSourceTarget(SourceTargetKind.CAPABILITY, capability.capability_id)] = (
            f"{label}：{capability.name or capability.description}"
        )
    for link in work.task_links:
        task_label = labels[JdSourceTarget(SourceTargetKind.TASK, link.task_id)]
        capability = capabilities[link.capability_id]
        labels[
            JdSourceTarget(
                SourceTargetKind.TASK_CAPABILITY, link.capability_id, task_id=link.task_id
            )
        ] = f"{task_label} · 使用：{capability.name or capability.description}"
    for item in work.collaborators:
        labels[JdSourceTarget(SourceTargetKind.COLLABORATOR, item.collaborator_id)] = (
            f"協作：{item.name or item.scope_text}"
        )
    for condition in work.conditions:
        labels[JdSourceTarget(SourceTargetKind.CONDITION, condition.condition_id)] = (
            f"共通條件：{condition.text}"
        )
    return labels
