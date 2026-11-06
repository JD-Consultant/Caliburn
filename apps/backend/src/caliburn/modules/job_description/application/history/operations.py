"""Workspace 範圍內的版本查閱、內容比較與安全恢復。"""

from collections.abc import Callable
from typing import Protocol
from uuid import UUID

from pydantic import ConfigDict, PositiveInt, TypeAdapter, validate_call

from caliburn.modules.job_description.application.content import JobDescriptionContent
from caliburn.modules.job_description.application.history.differences import (
    compare_contents,
)
from caliburn.modules.job_description.application.history.results import (
    JobDescriptionDifference,
    JobDescriptionHistoryResult,
)
from caliburn.modules.job_description.application.history_types import (
    DEFAULT_HISTORY_PAGE_SIZE,
    CorrelationId,
    HistoryPage,
    RestoreMetadata,
    normalize_history_page_size,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    HistoricalJobDescription,
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.transaction_retry import (
    retry_transaction,
)
from caliburn.modules.job_description.application.writing import (
    save_and_commit,
)
from caliburn.shared.application.base_dto import BaseDTO

_CORRELATION = TypeAdapter(CorrelationId | None)
_VERSION = TypeAdapter(PositiveInt)


class HistoryQueries(Protocol):
    """每次查讀使用獨立唯讀快照，不開啟可寫 UoW。"""

    def list_history(
        self,
        *,
        workspace_id: UUID,
        job_description_id: UUID,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
        page_token: str | None = None,
        correlation_id: str | None = None,
        reverts_correlation_id: str | None = None,
    ) -> HistoryPage: ...

    def get_history(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription: ...


class RestoreJobDescriptionInput(BaseDTO):
    job_description_id: UUID
    target_version: PositiveInt
    expected_version: PositiveInt
    correlation_id: CorrelationId | None = None
    reverts_correlation_id: CorrelationId | None = None


def list_history(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    queries: HistoryQueries,
    page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
    page_token: str | None = None,
    correlation_id: CorrelationId | None = None,
    reverts_correlation_id: CorrelationId | None = None,
) -> HistoryPage:
    page_size = normalize_history_page_size(page_size)
    correlation_id = _CORRELATION.validate_python(correlation_id, strict=True)
    reverts_correlation_id = _CORRELATION.validate_python(
        reverts_correlation_id, strict=True
    )
    return queries.list_history(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        page_size=page_size,
        page_token=page_token,
        correlation_id=correlation_id,
        reverts_correlation_id=reverts_correlation_id,
    )


def get_history(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    version: int,
    queries: HistoryQueries,
) -> JobDescriptionHistoryResult:
    version = _VERSION.validate_python(version, strict=True)
    historical = queries.get_history(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        version=version,
    )
    return JobDescriptionHistoryResult(
        content=JobDescriptionContent.from_domain(historical.job_description),
        entry=historical.entry,
    )


def compare_history(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    before_version: int,
    after_version: int,
    queries: HistoryQueries,
) -> JobDescriptionDifference:
    before_version = _VERSION.validate_python(before_version, strict=True)
    after_version = _VERSION.validate_python(after_version, strict=True)
    old = get_history(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        version=before_version,
        queries=queries,
    )
    new = (
        old
        if before_version == after_version
        else get_history(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            version=after_version,
            queries=queries,
        )
    )
    return compare_contents(
        old.content,
        new.content,
        before_version=before_version,
        after_version=after_version,
    )


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def restore(
    *,
    workspace_id: UUID,
    input: RestoreJobDescriptionInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
) -> JobDescriptionResult:
    """核對原版本後保存目標內容為新版本，即使內容相同也新增歷史。"""
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        loaded.require_version(expected_version=input.expected_version)
        historical = uow.history.get(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
            version=input.target_version,
        )
        result = save_and_commit(
            historical.job_description,
            uow=uow,
            correlation_id=input.correlation_id,
            restore=RestoreMetadata(
                target_version=input.target_version,
                reverts_correlation_id=input.reverts_correlation_id,
            ),
        )
    return result
