"""Application 測試的持久邊界記錄器；不模擬鎖、資料庫或回滾。"""

from types import TracebackType
from typing import Self
from uuid import UUID

from caliburn.modules.job_description.application.citation_sources import (
    CitationSources,
)
from caliburn.modules.job_description.application.errors import (
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history_types import (
    RestoreMetadata,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionHistoryReader,
    LoadedJobDescription,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


class RecordingRepository:
    def __init__(self, root: JobDescription | None = None, *, version: int = 4) -> None:
        self.root = root
        self.version = version
        self.original = root.model_dump() if root is not None else None
        self.correlation_id: str | None = None
        self.saved: int | None = None
        self.restore: RestoreMetadata | None = None

    def get_for_update(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> LoadedJobDescription:
        if (
            self.root is None
            or self.root.id != job_description_id
            or self.root.workspace_id != workspace_id
        ):
            raise JobDescriptionNotFoundError("指定 JD 不存在")
        return LoadedJobDescription(self.root, self.version)

    def add(self, root: JobDescription, /, *, correlation_id: str | None = None) -> int:
        self.root = root
        self.correlation_id = correlation_id
        self.saved = 1
        return self.saved

    def save(
        self,
        root: JobDescription,
        *,
        correlation_id: str | None = None,
        restore: RestoreMetadata | None = None,
    ) -> int:
        self.correlation_id = correlation_id
        self.restore = restore
        changed = root.model_dump() != self.original
        self.saved = self.version + int(changed or restore is not None)
        return self.saved


class RecordingUnitOfWork:
    def __init__(self, root: JobDescription | None = None, *, version: int = 4) -> None:
        self.job_descriptions = RecordingRepository(root, version=version)
        self.committed = False
        self.closed = False

    @property
    def citation_sources(self) -> CitationSources:
        raise AssertionError("沒有引用動作的內容用例不應查來源")

    @property
    def history(self) -> JobDescriptionHistoryReader:
        raise AssertionError("內容用例不應額外讀取歷史")

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.closed = True

    def commit(self) -> None:
        self.committed = True
