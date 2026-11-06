"""完成輪差異只讀固定歷史；缺件與錯歸屬不能冒充無變更。"""

import asyncio
from collections.abc import Coroutine
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import get_ident
from typing import cast
from uuid import UUID, uuid7

import pytest

from caliburn.modules.job_description.application.errors import (
    JobDescriptionHistoryDataError,
    JobDescriptionHistoryNotFoundError,
    JobDescriptionNotFoundError,
    JobDescriptionQueryError,
)
from caliburn.modules.job_description.application.history_types import (
    DEFAULT_HISTORY_PAGE_SIZE,
    HistoryEntry,
    HistoryPage,
)
from caliburn.modules.job_description.application.persistence import (
    HistoricalJobDescription,
)
from caliburn.modules.job_description.application.turn_history import (
    JobDescriptionTurnChangesResult,
    JobDescriptionTurnDataError,
    JobDescriptionTurnNotFoundError,
    JobDescriptionTurnVersions,
    get_turn_changes,
)
from caliburn.modules.job_description.domain.models.citation import InterviewReference
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


@dataclass(frozen=True)
class SavedSnapshot:
    """保存不可變 JSON；每次查詢重建合法根，不共享可變 Domain 物件。"""

    content_json: str
    entry: HistoryEntry


class SavedHistory:
    def __init__(self) -> None:
        root = JobDescription.create(workspace_id=uuid7())
        root.update_details(
            job_title="設備員",
            organization_unit="維修部",
            reports_to="組長",
            purpose="原職務目的",
            baseline_competency_level=3,
        )
        duty = root.add_duty(name="維護", scope="原範圍")
        knowledge = root.add_knowledge(name="機械原理", description="結構與運作")
        skill = root.add_skill(name="故障診斷", description="定位原因")
        root.add_task(
            name="檢查設備",
            duty_id=duty,
            competency_level=4,
            outcomes=("點檢紀錄",),
            requirements=("交班前完成",),
            knowledge=(knowledge,),
            skills=(skill,),
        )
        root.add_collaboration(collaborator_name="維修組", scope="缺陷交接")
        root.add_condition(kind=ConditionKind.WORK_ENVIRONMENT, text="現場")
        root.add_citation(
            target_kind="duty",
            target_id=duty,
            source=InterviewReference(
                workspace_id=root.workspace_id, message_id=uuid7()
            ),
        )
        self.versions = JobDescriptionTurnVersions(
            workspace_id=root.workspace_id,
            job_description_id=root.id,
            turn_id=uuid7(),
            before_version=2,
            after_version=5,
        )
        before = self._save(root, 2)
        root.update_details(
            job_title="設備員",
            organization_unit="維修部",
            reports_to="組長",
            purpose="輪次完成目的",
            baseline_competency_level=3,
        )
        root.add_task(name="交接設備", description="輪末已保存")
        after = self._save(root, 5)
        self.snapshots: tuple[SavedSnapshot, ...] = (before, after)
        self.reads: list[tuple[UUID, UUID, int]] = []
        self.read_threads: list[int] = []
        self.error: Exception | None = None

    @staticmethod
    def _save(root: JobDescription, version: int) -> SavedSnapshot:
        return SavedSnapshot(
            content_json=root.model_dump_json(),
            entry=HistoryEntry(
                job_description_id=root.id,
                version=version,
                kind="edited",
                recorded_at=datetime(2026, 11, 6, tzinfo=UTC),
            ),
        )

    def get_history(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription:
        self.reads.append((workspace_id, job_description_id, version))
        self.read_threads.append(get_ident())
        if self.error is not None:
            raise self.error
        for snapshot in self.snapshots:
            if snapshot.entry.version == version:
                return HistoricalJobDescription(
                    job_description=JobDescription.model_validate_json(
                        snapshot.content_json
                    ),
                    entry=snapshot.entry,
                )
        raise JobDescriptionHistoryNotFoundError("固定版本遺失")

    def list_history(
        self,
        *,
        workspace_id: UUID,
        job_description_id: UUID,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
        page_token: str | None = None,
        correlation_id: str | None = None,
        reverts_correlation_id: str | None = None,
    ) -> HistoryPage:
        raise AssertionError("完成輪不准列舉歷史或以 correlation 推導版本")


class CompletedReader:
    def __init__(self, result: JobDescriptionTurnVersions | None) -> None:
        self.result = result
        self.calls: list[tuple[UUID, UUID]] = []

    async def __call__(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> JobDescriptionTurnVersions | None:
        self.calls.append((workspace_id, turn_id))
        return self.result


def read(
    history: SavedHistory, reader: CompletedReader
) -> Coroutine[object, object, JobDescriptionTurnChangesResult]:
    versions = history.versions
    return get_turn_changes(
        workspace_id=versions.workspace_id,
        job_description_id=versions.job_description_id,
        turn_id=versions.turn_id,
        completed_turn_reader=reader,
        queries=history,
    )


def test_completed_turn_uses_only_fixed_versions_and_preserves_full_content() -> None:
    history = SavedHistory()
    reader = CompletedReader(history.versions)
    caller_thread = get_ident()
    result = asyncio.run(read(history, reader))
    versions = history.versions
    assert reader.calls == [(versions.workspace_id, versions.turn_id)]
    assert history.reads == [
        (versions.workspace_id, versions.job_description_id, 2),
        (versions.workspace_id, versions.job_description_id, 5),
    ]
    assert all(thread != caller_thread for thread in history.read_threads)
    assert result.before.purpose == "原職務目的"
    assert result.after.purpose == "輪次完成目的"
    assert result.before_version == result.difference.before_version == 2
    assert result.after_version == result.difference.after_version == 5
    assert result.before.citations == result.after.citations
    equipment_task = next(
        task for task in result.after.tasks if task.name == "檢查設備"
    )
    assert equipment_task.outcomes[0].text == "點檢紀錄"
    assert equipment_task.requirements[0].text == "交班前完成"
    assert (
        result.after.knowledge and result.after.skills and result.after.collaborations
    )
    assert result.after.conditions and result.after.duties
    assert any(
        item.change == "added" and item.kind == "task"
        for item in result.difference.items
    )
    assert any(
        field.before == "原職務目的" and field.after == "輪次完成目的"
        for item in result.difference.items
        for field in item.fields
    )


def test_same_version_is_legal_and_reads_once_for_empty_difference() -> None:
    history = SavedHistory()
    result = asyncio.run(
        read(history, CompletedReader(replace(history.versions, after_version=2)))
    )
    assert len(history.reads) == 1
    assert result.before == result.after
    assert result.difference.items == ()
    assert result.difference.collections == ()


@pytest.mark.parametrize(
    "mismatch", [None, "workspace_id", "job_description_id", "turn_id"]
)
def test_missing_or_mismatched_completion_rejects_before_history(
    mismatch: str | None,
) -> None:
    history = SavedHistory()
    versions = history.versions
    if mismatch is None:
        changed = None
    elif mismatch == "workspace_id":
        changed = replace(versions, workspace_id=uuid7())
    elif mismatch == "job_description_id":
        changed = replace(versions, job_description_id=uuid7())
    else:
        changed = replace(versions, turn_id=uuid7())
    with pytest.raises(JobDescriptionTurnNotFoundError):
        asyncio.run(read(history, CompletedReader(changed)))
    assert history.reads == []


@pytest.mark.parametrize("value", [0, -1, True, False, "2", 2.0, 2.5, None])
@pytest.mark.parametrize("field", ["before_version", "after_version"])
def test_version_locator_rejects_invalid_values_without_coercion(
    field: str, value: object
) -> None:
    history = SavedHistory()
    with pytest.raises(JobDescriptionTurnDataError):
        if field == "before_version":
            replace(history.versions, before_version=cast(int, value))
        else:
            replace(history.versions, after_version=cast(int, value))


def test_older_completed_seen_version_with_no_net_change_returns_empty_difference() -> (
    None
):
    history = SavedHistory()
    first = history.snapshots[0]
    history.snapshots = (
        replace(
            first,
            entry=first.entry.model_copy(update={"version": 1, "kind": "created"}),
        ),
        replace(first, entry=first.entry.model_copy(update={"version": 3})),
    )
    history.versions = replace(history.versions, before_version=3, after_version=1)
    result = asyncio.run(read(history, CompletedReader(history.versions)))
    assert [version for _, _, version in history.reads] == [3, 1]
    assert result.before_version == result.difference.before_version == 3
    assert result.after_version == result.difference.after_version == 1
    assert result.before == result.after
    assert result.difference.items == ()
    assert result.difference.collections == ()


def test_reverse_versions_compare_in_supplied_direction_without_sorting() -> None:
    history = SavedHistory()
    history.versions = replace(history.versions, before_version=5, after_version=2)
    result = asyncio.run(read(history, CompletedReader(history.versions)))
    assert [version for _, _, version in history.reads] == [5, 2]
    assert result.before.purpose == "輪次完成目的"
    assert result.after.purpose == "原職務目的"
    assert any(
        field.before == "輪次完成目的" and field.after == "原職務目的"
        for item in result.difference.items
        for field in item.fields
    )
    assert any(
        item.kind == "task" and item.change == "removed"
        for item in result.difference.items
    )


@pytest.mark.parametrize(
    "error_type",
    [
        JobDescriptionNotFoundError,
        JobDescriptionHistoryNotFoundError,
        JobDescriptionHistoryDataError,
    ],
)
def test_known_fixed_history_failure_is_turn_data_error(
    error_type: type[Exception],
) -> None:
    history = SavedHistory()
    history.error = error_type("已確認固定歷史不可用")
    with pytest.raises(JobDescriptionTurnDataError) as caught:
        asyncio.run(read(history, CompletedReader(history.versions)))
    assert caught.value.__cause__ is history.error


def test_history_query_technical_failure_is_not_misreported_as_missing_data() -> None:
    history = SavedHistory()
    history.error = JobDescriptionQueryError("查詢故障")
    with pytest.raises(JobDescriptionQueryError) as caught:
        asyncio.run(read(history, CompletedReader(history.versions)))
    assert caught.value is history.error


def test_missing_after_snapshot_cannot_become_empty_difference() -> None:
    history = SavedHistory()
    history.snapshots = history.snapshots[:1]
    with pytest.raises(JobDescriptionTurnDataError):
        asyncio.run(read(history, CompletedReader(history.versions)))
