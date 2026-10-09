"""Resolve a new model intent once; execution reuses the original bound candidate command."""

from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.body_matching import BodyEditError, BodyMatchPolicy
from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.work_memory import candidate_queries, read_queries
from caliburn.features.work_memory.body_edits import DEFAULT_BODY_MATCH_POLICY
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryPermissionError,
    ReviseMemoryObject,
    require_layer_write,
)
from caliburn.features.work_memory.changes import (
    apply_content_changes,
    apply_reference_changes,
    require_unique_title,
    resolve_title,
)
from caliburn.features.work_memory.edit_intents import (
    CreateMemoryIntent,
    DeleteMemoryIntent,
    InterviewReferenceChange,
    InterviewSourceSelection,
    MemoryWriteIntent,
    SituationReferenceChange,
    SituationSourceSelection,
)
from caliburn.features.work_memory.edit_preparation import (
    MemoryStatusPreview,
    MemoryUpdatePreview,
    PreparedMemoryEdit,
    describe_body_change,
    prepare_content_changes,
    validate_changes,
)
from caliburn.features.work_memory.models import MemoryContent, ReferenceChanges
from caliburn.features.work_memory.read_models import MemoryReadView
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_reads import CandidateMemoryRead


class MemoryWritePreparation:
    """Reads and computes only; no locks across CPU work and no business writes."""

    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        cpu: MemoryCpu,
        body_policy: BodyMatchPolicy = DEFAULT_BODY_MATCH_POLICY,
    ) -> None:
        self.sessions = sessions
        self.cpu = cpu
        self.body_policy = body_policy

    async def prepare(
        self,
        binding: CandidateMemoryRead,
        *,
        command_id: UUID,
        layer: MemoryLayer,
        intent: MemoryWriteIntent,
    ) -> PreparedMemoryEdit:
        require_layer_write(binding.stage.phase, layer)
        async with self.sessions() as session:
            if (
                await executions.read_execution(session, binding.scope)
            ).status != ExecutionStatus.ACTIVE:
                raise ExecutionStateError("This execution cannot prepare a new Memory write")
            record = await candidate_queries.require_stage(session, binding.stage)
            position = candidate_queries.batch_position(record)
            view = MemoryReadView(
                position.job_file_id, position.position_id, layer, record.through_sequence
            )
            entries = await read_queries.read_map(session, view)
            if isinstance(intent, CreateMemoryIntent):
                _require_source_layer(layer, intent.sources)
                selected = await _resolve_sources(session, view, intent.sources)
                _require_body_capacity(intent.content.body, self.body_policy)
                require_unique_title(uuid4(), intent.content, entries)
                return PreparedMemoryEdit(
                    CreateMemoryObject(
                        command_id, position, layer, intent.content, frozenset(selected)
                    ),
                    MemoryStatusPreview("created"),
                )
            object_id = resolve_title(entries, intent.target_title)
            if isinstance(intent, DeleteMemoryIntent):
                return PreparedMemoryEdit(
                    DeleteMemoryObject(command_id, position, layer, object_id),
                    MemoryStatusPreview("deleted"),
                )
            validate_changes(intent.changes)
            before = await read_queries.read_object(session, view, object_id)
            current_sources = (
                before.interview_source_ids
                if layer == MemoryLayer.WORK_SITUATION
                else frozenset(item.object_id for item in before.work_situation_references)
            )
            reference_change: ReferenceChanges | None = None
            added: dict[UUID, int | str] = {}
            removed: dict[UUID, int | str] = {}
            additions: InterviewSourceSelection | SituationSourceSelection
            removals: InterviewSourceSelection | SituationSourceSelection
            for change in intent.changes:
                if isinstance(change, InterviewReferenceChange):
                    additions = InterviewSourceSelection(change.add)
                    removals = InterviewSourceSelection(change.remove)
                elif isinstance(change, SituationReferenceChange):
                    additions = SituationSourceSelection(change.add)
                    removals = SituationSourceSelection(change.remove)
                else:
                    continue
                _require_source_layer(layer, additions)
                added = await _resolve_sources(session, view, additions)
                removed = await _resolve_sources(session, view, removals)
                reference_change = ReferenceChanges(frozenset(added), frozenset(removed))
            next_sources = (
                current_sources
                if reference_change is None
                else apply_reference_changes(current_sources, reference_change, frozenset(added))
            )
        # Patch search can be expensive. Release the read session first and keep the
        # event loop responsive; apply later uses this exact position, never latest.
        content_changes = await self.cpu.run(
            prepare_content_changes, before.content, intent.changes, policy=self.body_policy
        )
        after = (
            before.content
            if content_changes is None
            else apply_content_changes(before.content, content_changes)
        )
        require_unique_title(object_id, after, entries)
        preview = await self.cpu.run(
            _update_preview,
            layer,
            before.content,
            after,
            tuple(added[key] for key in added if key in next_sources - current_sources),
            tuple(removed[key] for key in removed if key in current_sources - next_sources),
        )
        return PreparedMemoryEdit(
            ReviseMemoryObject(
                command_id, position, layer, object_id, content_changes, reference_change
            ),
            preview,
        )


def _require_source_layer(
    layer: MemoryLayer, selection: InterviewSourceSelection | SituationSourceSelection
) -> None:
    if (layer == MemoryLayer.WORK_SITUATION) != isinstance(selection, InterviewSourceSelection):
        raise MemoryPermissionError("The source selection belongs to another Memory layer")


async def _resolve_sources(
    session: AsyncSession,
    view: MemoryReadView,
    selection: InterviewSourceSelection | SituationSourceSelection,
) -> dict[UUID, int | str]:
    if isinstance(selection, InterviewSourceSelection):
        if not selection.sequences:
            return {}
        messages = await interviews.read_interview_messages(
            session,
            InterviewReadScope(view.job_file_id, view.through_sequence),
            sequences=selection.sequences,
        )
        return {message.source_id: message.interview_sequence for message in messages}
    if not selection.titles:
        return {}
    entries = await read_queries.read_map(
        session,
        MemoryReadView(
            view.job_file_id, view.position_id, MemoryLayer.WORK_SITUATION, view.through_sequence
        ),
    )
    return {resolve_title(entries, title): title for title in selection.titles}


def _require_body_capacity(body: str, policy: BodyMatchPolicy) -> None:
    if len(body) > policy.max_body_characters:
        raise BodyEditError("patch_limit_exceeded", "Body exceeds the configured editing capacity")


def _update_preview(
    layer: MemoryLayer,
    before: MemoryContent,
    after: MemoryContent,
    added: tuple[int | str, ...],
    removed: tuple[int | str, ...],
) -> MemoryStatusPreview | MemoryUpdatePreview:
    if before == after and not added and not removed:
        return MemoryStatusPreview("unchanged")
    fields: list[Literal["title", "description"]] = []
    if before.title != after.title:
        fields.append("title")
    if before.description != after.description:
        fields.append("description")
    return MemoryUpdatePreview(
        after,
        tuple(fields),
        describe_body_change(before.body, after.body) if before.body != after.body else None,
        "interview_references"
        if layer == MemoryLayer.WORK_SITUATION
        else "work_situation_references",
        added,
        removed,
    )
