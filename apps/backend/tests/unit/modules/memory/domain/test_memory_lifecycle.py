"""Memory 固定發布、差異、恢復與整理資格的領域行為。"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from caliburn.modules.memory.domain.analysis import MemorySourceWindow
from caliburn.modules.memory.domain.changes import describe_changes
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.errors import (
    DuplicateMemoryTitleError,
    InvalidMemoryPhaseError,
    InvalidMemorySnapshotError,
    InvalidMemorySourceError,
    MemoryAnalysisConflictError,
)
from caliburn.modules.memory.domain.items import WorkSituation, WorkUnderstanding
from caliburn.modules.memory.domain.snapshot import MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory

PUBLISHED_AT = datetime(2026, 11, 6, tzinfo=UTC)


def content(title: str, body: str = "原先的內容") -> MemoryContent:
    return MemoryContent(title=title, description="摘要", body=body)


def publish(memory: WorkMemory, upper: UUID) -> MemorySnapshot:
    return memory.publish(covered_through_message_id=upper, published_at=PUBLISHED_AT)


def source_window(workspace_id: UUID) -> MemorySourceWindow:
    before, through = UUID(int=20), UUID(int=10)
    return MemorySourceWindow(
        workspace_id=workspace_id,
        through_message_id=through,
        message_ids=(before, through),
        required_message_ids=(through,),
    )


def test_source_window_keeps_interview_order_and_rejects_inconsistent_ids() -> None:
    workspace_id, first, second, missing = uuid4(), uuid4(), uuid4(), uuid4()
    window = source_window(workspace_id)
    assert window.message_ids == (UUID(int=20), UUID(int=10))
    assert window.required_message_ids == (window.through_message_id,)
    for upper, allowed, required in (
        (second, (first,), ()),
        (first, (first, first), ()),
        (second, (first, second), (missing,)),
        (second, (first, second), (first, first)),
    ):
        with pytest.raises(InvalidMemorySourceError):
            MemorySourceWindow(
                workspace_id=workspace_id,
                through_message_id=upper,
                message_ids=allowed,
                required_message_ids=required,
            )


def test_snapshot_requires_complete_graph_and_aware_timestamp() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    situation_id = memory.create_situation(content=content("情境"))
    understanding_id = memory.create_understanding(
        content=content("理解"), situation_ids=(situation_id,)
    )
    before = memory.model_dump()
    snapshot = publish(memory, uuid4())
    situation = memory.get_situation(item_id=situation_id)
    understanding = memory.get_understanding(item_id=understanding_id)
    assert snapshot.items == (situation, understanding)
    assert snapshot.version == memory.version == memory.published_version == 3
    assert snapshot.published_at == PUBLISHED_AT
    with pytest.raises(InvalidMemorySourceError):
        MemorySnapshot(
            workspace_id=memory.id,
            version=3,
            covered_through_message_id=uuid4(),
            published_at=PUBLISHED_AT,
            items=(understanding,),
        )
    with pytest.raises(InvalidMemorySnapshotError):
        memory.publish(
            covered_through_message_id=uuid4(),
            published_at=PUBLISHED_AT.replace(tzinfo=None),
        )
    assert memory.version == 3
    assert memory.model_dump(exclude={"version", "published_version"}) == {
        key: value
        for key, value in before.items()
        if key not in {"version", "published_version"}
    }


def test_snapshot_rejects_duplicate_id_across_kinds_and_same_layer_title() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    item_id = memory.create_situation(content=content("情境"))
    situation = memory.get_situation(item_id=item_id)
    same_id = WorkUnderstanding(
        id=item_id,
        workspace_id=memory.id,
        changed_version=1,
        content=content("理解"),
        situation_ids=(),
    )
    same_title = WorkSituation(
        id=uuid4(),
        workspace_id=memory.id,
        changed_version=1,
        content=situation.content,
        interview_message_ids=(),
    )

    with pytest.raises(InvalidMemorySnapshotError):
        MemorySnapshot(
            workspace_id=memory.id,
            version=1,
            covered_through_message_id=uuid4(),
            published_at=PUBLISHED_AT,
            items=(situation, same_id),
        )
    with pytest.raises(DuplicateMemoryTitleError):
        MemorySnapshot(
            workspace_id=memory.id,
            version=1,
            covered_through_message_id=uuid4(),
            published_at=PUBLISHED_AT,
            items=(situation, same_title),
        )


def test_describe_changes_uses_stable_ids_and_preserves_stamp_only_changes() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    item_id = memory.create_situation(content=content("情境"))
    removed_id = memory.create_situation(content=content("移除"))
    baseline = publish(memory, uuid4())
    original = memory.get_situation(item_id=item_id).content
    memory.revise_situation(
        item_id=item_id, content=content("情境", "改寫"), interview_message_ids=()
    )
    memory.revise_situation(item_id=item_id, content=original, interview_message_ids=())
    memory.remove_situation(item_id=removed_id)
    created_id = memory.create_understanding(content=content("新增"))
    current = publish(memory, uuid4())

    changes = describe_changes(baseline, current)

    assert [change.item_id for change in changes] == sorted(
        (item_id, removed_id, created_id)
    )
    by_id = {change.item_id: change for change in changes}
    modified = by_id[item_id]
    assert modified.kind == "situation"
    assert modified.before is not None and modified.after is not None
    assert modified.before.content == modified.after.content == original
    assert modified.before.changed_version < modified.after.changed_version
    assert by_id[removed_id].after is None
    assert by_id[created_id].before is None
    assert by_id[created_id].kind == "understanding"
    assert len(describe_changes(None, current)) == 2
    with pytest.raises(InvalidMemorySnapshotError):
        describe_changes(baseline, WorkMemory.create(workspace_id=uuid4()))


def test_reset_restores_baseline_stamps_and_rejects_wrong_head() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    item_id = memory.create_situation(content=content("情境"))
    first = publish(memory, uuid4())
    baseline = publish(memory, uuid4())
    assert not memory.reset_to_published(baseline)
    assert memory.version == baseline.version
    memory.revise_situation(
        item_id=item_id, content=content("情境", "失敗稿"), interview_message_ids=()
    )
    revised_version = memory.version
    before = memory.model_dump()
    for invalid in (
        None,
        first,
        publish(WorkMemory.create(workspace_id=uuid4()), uuid4()),
    ):
        with pytest.raises(InvalidMemorySnapshotError):
            memory.reset_to_published(invalid)
        assert memory.model_dump() == before

    assert memory.reset_to_published(baseline)
    assert memory.version == revised_version + 1
    assert describe_changes(baseline, memory) == ()
    assert memory.get_situation(item_id=item_id).changed_version == 1
    assert memory.published_version == baseline.version


def test_analysis_begin_and_discard_restore_baseline_once() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    item_id = memory.create_situation(content=content("情境"))
    window = source_window(memory.id)
    baseline = publish(memory, window.message_ids[0])
    memory.revise_situation(
        item_id=item_id,
        content=content("情境", "上一個失敗稿"),
        interview_message_ids=(),
    )
    analysis_id = uuid4()
    memory.begin_analysis(
        analysis_id=analysis_id,
        source_window=window,
        baseline=baseline,
    )
    assert memory.version == 4
    assert describe_changes(baseline, memory) == ()
    analysis = memory.require_analysis(analysis_id=analysis_id, phase="situation")
    assert analysis.source_window == window
    assert analysis.base_published_version == baseline.version
    memory.revise_situation(
        item_id=item_id, content=content("情境", "目前失敗稿"), interview_message_ids=()
    )
    before = memory.model_dump()
    with pytest.raises(MemoryAnalysisConflictError):
        memory.discard_analysis(analysis_id=uuid4(), baseline=baseline)
    with pytest.raises(InvalidMemorySnapshotError):
        memory.discard_analysis(analysis_id=analysis_id, baseline=None)
    assert memory.model_dump() == before

    memory.discard_analysis(analysis_id=analysis_id, baseline=baseline)

    assert memory.version == 6
    assert memory.analysis is None
    assert describe_changes(baseline, memory) == ()
    with pytest.raises(MemoryAnalysisConflictError):
        memory.require_analysis(analysis_id=analysis_id)


def test_handoff_closes_situation_phase_before_publish() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    window = source_window(memory.id)
    analysis_id = uuid4()
    memory.begin_analysis(
        analysis_id=analysis_id,
        source_window=window,
        baseline=None,
    )
    situation_id = memory.create_situation(
        content=content("情境"), interview_message_ids=window.required_message_ids
    )
    before = memory.model_dump()
    with pytest.raises(InvalidMemoryPhaseError):
        publish(memory, window.through_message_id)
    with pytest.raises(MemoryAnalysisConflictError):
        memory.begin_analysis(analysis_id=uuid4(), source_window=window, baseline=None)
    assert memory.model_dump() == before
    with pytest.raises(MemoryAnalysisConflictError):
        memory.handoff(analysis_id=uuid4())
    assert memory.version == 2

    memory.handoff(analysis_id=analysis_id)

    with pytest.raises(InvalidMemoryPhaseError):
        memory.require_analysis(analysis_id=analysis_id, phase="situation")
    with pytest.raises(InvalidMemoryPhaseError):
        memory.handoff(analysis_id=analysis_id)
    with pytest.raises(InvalidMemorySourceError):
        publish(memory, window.message_ids[0])
    assert memory.version == 3
    assert memory.get_situation(item_id=situation_id).changed_version == 2

    snapshot = publish(memory, window.through_message_id)
    assert snapshot.version == memory.version == memory.published_version == 4
    assert memory.analysis is None
    assert snapshot.items[0].changed_version == 2


def test_begin_rejects_cross_workspace_window_without_replacing_draft() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    memory.create_situation(content=content("目前稿"))
    before = memory.model_dump()

    with pytest.raises(InvalidMemorySourceError):
        memory.begin_analysis(
            analysis_id=uuid4(),
            source_window=source_window(uuid4()),
            baseline=None,
        )
    assert memory.model_dump() == before


def test_latest_failure_is_root_state_and_successful_publish_clears_it() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    window = source_window(memory.id)
    failed = uuid4()
    memory.begin_analysis(analysis_id=failed, source_window=window, baseline=None)
    memory.discard_analysis(
        analysis_id=failed,
        baseline=None,
        reason="invalid_completion",
        formal_message_ids=window.message_ids,
    )
    assert memory.failure is not None
    assert memory.failure.analysis_id == failed
    assert memory.failure.formal_message_ids == window.message_ids

    retry = uuid4()
    memory.begin_analysis(analysis_id=retry, source_window=window, baseline=None)
    assert memory.failure is not None
    memory.handoff(analysis_id=retry)
    publish(memory, window.through_message_id)
    assert memory.failure is None
