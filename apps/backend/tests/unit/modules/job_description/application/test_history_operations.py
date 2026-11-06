"""歷史用例的版本前置、保存來源與完整結果；持久快照另以 PG 驗證。"""

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid7

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionHistoryNotFoundError,
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history.operations import (
    RestoreJobDescriptionInput,
    compare_history,
    get_history,
    restore,
)
from caliburn.modules.job_description.application.history_types import (
    DEFAULT_HISTORY_PAGE_SIZE,
    HistoryEntry,
    HistoryPage,
)
from caliburn.modules.job_description.application.persistence import (
    HistoricalJobDescription,
    JobDescriptionHistoryReader,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


class RecordedHistory:
    def __init__(self, root: JobDescription, *, version: int = 2) -> None:
        self.root = root
        self.version = version
        self.read_versions: list[int] = []

    def get(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription:
        self.read_versions.append(version)
        if (
            workspace_id != self.root.workspace_id
            or job_description_id != self.root.id
            or version != self.version
        ):
            raise JobDescriptionHistoryNotFoundError("指定範圍無此歷史版本")
        return HistoricalJobDescription(
            self.root,
            HistoryEntry(
                job_description_id=self.root.id,
                version=version,
                kind="edited",
                recorded_at=datetime(2026, 10, 26, tzinfo=UTC),
            ),
        )

    def list(
        self,
        *,
        workspace_id: UUID,
        job_description_id: UUID,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
        page_token: str | None = None,
        correlation_id: str | None = None,
        reverts_correlation_id: str | None = None,
    ) -> HistoryPage:
        raise AssertionError("此用例不應列舉歷史")

    def get_history(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription:
        return self.get(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            version=version,
        )

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
        return self.list(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            page_size=page_size,
            page_token=page_token,
            correlation_id=correlation_id,
            reverts_correlation_id=reverts_correlation_id,
        )


class RestoreUnitOfWork(RecordingUnitOfWork):
    def __init__(self, root: JobDescription, history: RecordedHistory) -> None:
        super().__init__(root, version=4)
        self.recorded_history = history

    @property
    def history(self) -> JobDescriptionHistoryReader:
        return self.recorded_history


def test_restoring_same_content_still_saves_new_version_and_source_metadata() -> None:
    root = JobDescription(id=uuid7(), workspace_id=uuid7(), purpose="目前內容")
    history = RecordedHistory(root.model_copy(deep=True))
    unit = RestoreUnitOfWork(root, history)

    result = restore(
        workspace_id=root.workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=root.id,
            target_version=2,
            expected_version=4,
            correlation_id="restore-1",
            reverts_correlation_id="edit-1",
        ),
        uow_factory=lambda: unit,
    )

    assert result.job_description_id == root.id
    assert result.purpose == root.purpose
    assert result.version == 5
    assert unit.job_descriptions.correlation_id == "restore-1"
    metadata = unit.job_descriptions.restore
    assert metadata is not None
    assert metadata.target_version == 2
    assert metadata.reverts_correlation_id == "edit-1"
    assert unit.committed and unit.closed


def test_stale_restore_rejects_before_reading_history_or_saving() -> None:
    root = JobDescription(id=uuid7(), workspace_id=uuid7())
    history = RecordedHistory(root)
    unit = RestoreUnitOfWork(root, history)
    with pytest.raises(JobDescriptionConcurrencyError):
        restore(
            workspace_id=root.workspace_id,
            input=RestoreJobDescriptionInput(
                job_description_id=root.id,
                target_version=999,
                expected_version=3,
            ),
            uow_factory=lambda: unit,
        )
    assert history.read_versions == []
    assert unit.job_descriptions.saved is None
    assert not unit.committed


def test_restore_rejects_another_workspace_before_reading_history() -> None:
    root = JobDescription(id=uuid7(), workspace_id=uuid7())
    history = RecordedHistory(root)
    unit = RestoreUnitOfWork(root, history)
    with pytest.raises(JobDescriptionNotFoundError):
        restore(
            workspace_id=uuid7(),
            input=RestoreJobDescriptionInput(
                job_description_id=root.id,
                target_version=2,
                expected_version=4,
            ),
            uow_factory=lambda: unit,
        )
    assert history.read_versions == []
    assert unit.job_descriptions.saved is None
    assert not unit.committed


def test_history_queries_preserve_workspace_and_requested_version() -> None:
    root = JobDescription(id=uuid7(), workspace_id=uuid7(), purpose="原文")
    history = RecordedHistory(root)
    result = get_history(
        workspace_id=root.workspace_id,
        job_description_id=root.id,
        version=2,
        queries=history,
    )
    assert result.content.purpose == "原文"
    assert result.entry.version == 2
    with pytest.raises(JobDescriptionHistoryNotFoundError):
        get_history(
            workspace_id=uuid7(),
            job_description_id=root.id,
            version=2,
            queries=history,
        )
    difference = compare_history(
        workspace_id=root.workspace_id,
        job_description_id=root.id,
        before_version=2,
        after_version=2,
        queries=history,
    )
    assert difference.job_description_id == root.id
    assert difference.before_version == difference.after_version == 2
    assert difference.items == ()
    assert difference.collections == ()


@pytest.mark.parametrize("value", [0, -1, True, "2", 1.5])
def test_history_version_is_validated_before_reading(value: object) -> None:
    root = JobDescription(id=uuid7(), workspace_id=uuid7())
    history = RecordedHistory(root)
    with pytest.raises(ValidationError):
        get_history(
            workspace_id=root.workspace_id,
            job_description_id=root.id,
            version=cast(int, value),
            queries=history,
        )
    assert history.read_versions == []
