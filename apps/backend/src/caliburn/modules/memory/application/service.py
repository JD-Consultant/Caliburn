"""在同一交易核對版本、目前分析階段與訪談來源。"""

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID

from caliburn.modules.memory.application.errors import (
    MemoryConcurrencyError,
    MemoryFailureBlockedError,
)
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.persistence import (
    CompletedInterviewTurns,
    MemoryUnitOfWork,
)
from caliburn.modules.memory.application.results import MemoryUpdateResult
from caliburn.modules.memory.domain.analysis import (
    MemoryFailureReason,
    MemorySourceWindow,
)
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory

RETRY_AFTER_NEW_MESSAGES = 6


class MemoryService:
    def __init__(
        self,
        uow_factory: Callable[[], MemoryUnitOfWork],
        *,
        completed_turns: CompletedInterviewTurns,
    ) -> None:
        self._uow_factory = uow_factory
        self._completed_turns = completed_turns

    def start(
        self, context: MemoryWriteContext, *, through_message_id: UUID
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            baseline = _baseline(uow, memory)
            completed = self._completed_turns.completed_turn_ids(workspace_id=memory.id)
            window = uow.sources.bind_window(
                workspace_id=memory.id,
                through_message_id=through_message_id,
                covered_through_message_id=(
                    baseline.covered_through_message_id
                    if baseline is not None
                    else None
                ),
                completed_turn_ids=completed,
            )
            if window is None:
                return MemoryUpdateResult(version=memory.version, changed=False)
            if memory.failure is not None:
                current_ids = uow.sources.formal_message_ids(
                    workspace_id=memory.id, completed_turn_ids=completed
                )
                new_ids = set(current_ids).difference(memory.failure.formal_message_ids)
                if len(new_ids) < RETRY_AFTER_NEW_MESSAGES:
                    raise MemoryFailureBlockedError("最終失敗後仍需新的正式訪談")
            memory.begin_analysis(
                analysis_id=context.analysis_id, source_window=window, baseline=baseline
            )
            return _save(uow, context, memory)

    def create_situation(
        self,
        context: MemoryWriteContext,
        *,
        content: MemoryContent,
        interview_message_ids: tuple[UUID, ...] = (),
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="situation"
            )
            uow.sources.require_sources(
                window=analysis.source_window,
                message_ids=frozenset(interview_message_ids),
            )
            item_id = memory.create_situation(
                content=content, interview_message_ids=interview_message_ids
            )
            return _save(uow, context, memory, item_id=item_id)

    def revise_situation(
        self,
        context: MemoryWriteContext,
        *,
        item_id: UUID,
        content: MemoryContent,
        interview_message_ids: tuple[UUID, ...],
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="situation"
            )
            uow.sources.require_sources(
                window=analysis.source_window,
                message_ids=frozenset(interview_message_ids),
            )
            memory.revise_situation(
                item_id=item_id,
                content=content,
                interview_message_ids=interview_message_ids,
            )
            return _save(uow, context, memory, item_id=item_id)

    def delete_situation(
        self, context: MemoryWriteContext, *, item_id: UUID
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            memory.require_analysis(analysis_id=context.analysis_id, phase="situation")
            memory.remove_situation(item_id=item_id)
            return _save(uow, context, memory, item_id=item_id)

    def create_understanding(
        self,
        context: MemoryWriteContext,
        *,
        content: MemoryContent,
        situation_ids: tuple[UUID, ...] = (),
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="understanding"
            )
            _require_analysis_sources(uow, memory, analysis.source_window)
            item_id = memory.create_understanding(
                content=content, situation_ids=situation_ids
            )
            return _save(uow, context, memory, item_id=item_id)

    def revise_understanding(
        self,
        context: MemoryWriteContext,
        *,
        item_id: UUID,
        content: MemoryContent,
        situation_ids: tuple[UUID, ...],
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="understanding"
            )
            _require_analysis_sources(uow, memory, analysis.source_window)
            memory.revise_understanding(
                item_id=item_id, content=content, situation_ids=situation_ids
            )
            return _save(uow, context, memory, item_id=item_id)

    def delete_understanding(
        self, context: MemoryWriteContext, *, item_id: UUID
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="understanding"
            )
            _require_analysis_sources(uow, memory, analysis.source_window)
            memory.remove_understanding(item_id=item_id)
            return _save(uow, context, memory, item_id=item_id)

    def handoff(self, context: MemoryWriteContext) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="situation"
            )
            _require_analysis_sources(uow, memory, analysis.source_window)
            memory.handoff(analysis_id=context.analysis_id)
            return _save(uow, context, memory)

    def publish(self, context: MemoryWriteContext) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            analysis = memory.require_analysis(
                analysis_id=context.analysis_id, phase="understanding"
            )
            _require_analysis_sources(uow, memory, analysis.source_window)
            snapshot = memory.publish(
                covered_through_message_id=analysis.source_window.through_message_id,
                published_at=datetime.now(UTC),
            )
            return _save(uow, context, memory, snapshot=snapshot)

    def discard(
        self, context: MemoryWriteContext, *, reason: MemoryFailureReason | None = None
    ) -> MemoryUpdateResult:
        with self._uow_factory() as uow:
            memory = _load(uow, context)
            memory.require_analysis(analysis_id=context.analysis_id)
            formal_ids: tuple[UUID, ...] = ()
            if reason is not None:
                formal_ids = uow.sources.formal_message_ids(
                    workspace_id=memory.id,
                    completed_turn_ids=self._completed_turns.completed_turn_ids(
                        workspace_id=memory.id
                    ),
                )
            memory.discard_analysis(
                analysis_id=context.analysis_id,
                baseline=_baseline(uow, memory),
                reason=reason,
                formal_message_ids=formal_ids,
            )
            return _save(uow, context, memory)


def _load(uow: MemoryUnitOfWork, context: MemoryWriteContext) -> WorkMemory:
    memory = uow.memories.get_for_update(workspace_id=context.workspace_id)
    if memory is None:
        memory = WorkMemory.create(workspace_id=context.workspace_id)
    if memory.version != context.expected_version:
        raise MemoryConcurrencyError()
    return memory


def _save(
    uow: MemoryUnitOfWork,
    context: MemoryWriteContext,
    memory: WorkMemory,
    *,
    item_id: UUID | None = None,
    snapshot: MemorySnapshot | None = None,
) -> MemoryUpdateResult:
    changed = memory.version != context.expected_version
    if changed:
        uow.memories.save(memory, snapshot=snapshot)
        uow.commit()
    return MemoryUpdateResult(memory.version, changed, item_id, snapshot)


def _baseline(uow: MemoryUnitOfWork, memory: WorkMemory) -> MemorySnapshot | None:
    if memory.published_version is None:
        return None
    return uow.memories.get_snapshot(
        workspace_id=memory.workspace_id, version=memory.published_version
    )


def _require_analysis_sources(
    uow: MemoryUnitOfWork, memory: WorkMemory, window: MemorySourceWindow
) -> None:
    source_ids = set(window.message_ids)
    for situation in memory.situations:
        source_ids.update(situation.interview_message_ids)
    uow.sources.require_sources(window=window, message_ids=frozenset(source_ids))
