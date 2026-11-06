"""單一 JD 的工作聚合、交易內保存資訊與歷史讀取契約。"""

from dataclasses import dataclass, field
from typing import Protocol
from uuid import UUID

from caliburn.modules.job_description.application.citation_sources import (
    CitationSources,
)
from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
)
from caliburn.modules.job_description.application.history_types import (
    DEFAULT_HISTORY_PAGE_SIZE,
    HistoryEntry,
    HistoryPage,
    RestoreMetadata,
)
from caliburn.modules.job_description.domain.models.citation_review import (
    CitationSupport,
    capture_citation_support,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.shared.application.base_unit_of_work import BaseUnitOfWork


@dataclass(frozen=True)
class LoadedJobDescription:
    job_description: JobDescription
    version: int
    citation_support: CitationSupport = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "citation_support", capture_citation_support(self.job_description)
        )

    def require_version(self, *, expected_version: int) -> None:
        if self.version != expected_version:
            raise JobDescriptionConcurrencyError("JD 版本已變更，未修改")


@dataclass(frozen=True)
class HistoricalJobDescription:
    """供歷史投影或恢復使用的工作內容，不作公開可變回傳。"""

    job_description: JobDescription
    entry: HistoryEntry


class JobDescriptionRepository(Protocol):
    """每個 UoW 至多 add 或 save 一次（含 no-op），保存內可多次 flush。"""

    def get_for_update(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> LoadedJobDescription:
        """先鎖定並載入指定 Workspace 的 JD；缺少時拋 JobDescriptionNotFoundError。"""
        ...

    def add(
        self, job_description: JobDescription, /, *, correlation_id: str | None = None
    ) -> int:
        """保存新根及初始歷史，不提交。"""
        ...

    def save(
        self,
        job_description: JobDescription,
        *,
        correlation_id: str | None = None,
        restore: RestoreMetadata | None = None,
    ) -> int:
        """保存已載入根的差異；一般 no-op 不造歷史，明確恢復一律增版。"""
        ...


class JobDescriptionHistoryReader(Protocol):
    def list(
        self,
        *,
        workspace_id: UUID,
        job_description_id: UUID,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
        page_token: str | None = None,
        correlation_id: str | None = None,
        reverts_correlation_id: str | None = None,
    ) -> HistoryPage: ...

    def get(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription:
        """只接受指定範圍已成立的版本，解碼完整內容。"""
        ...


class JobDescriptionUnitOfWork(BaseUnitOfWork, Protocol):
    @property
    def citation_sources(self) -> CitationSources: ...
    @property
    def job_descriptions(self) -> JobDescriptionRepository: ...

    @property
    def history(self) -> JobDescriptionHistoryReader: ...
