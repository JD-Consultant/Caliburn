"""依已完成輪次的固定版本查閱差異，或恢復該輪的 JD 修改。"""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from caliburn.modules.job_description.application.content import JobDescriptionContent
from caliburn.modules.job_description.application.errors import (
    JobDescriptionHistoryDataError,
    JobDescriptionHistoryNotFoundError,
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history import turn_changes
from caliburn.modules.job_description.application.history.differences import (
    compare_contents,
)
from caliburn.modules.job_description.application.history.operations import (
    HistoryQueries,
    get_history,
)
from caliburn.modules.job_description.application.history.results import (
    JobDescriptionDifference,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.shared.application.base_dto import BaseDTO


class JobDescriptionTurnNotFoundError(Exception):
    """完成輪次不存在，或不屬於指定 Workspace／JD。"""


class JobDescriptionTurnDataError(Exception):
    """完成輪次固定版本或歷史內容不完整，不能改讀目前版本。"""


@dataclass(frozen=True)
class JobDescriptionTurnVersions:
    workspace_id: UUID
    job_description_id: UUID
    turn_id: UUID
    before_version: int
    after_version: int

    def __post_init__(self) -> None:
        if (
            type(self.before_version) is not int
            or type(self.after_version) is not int
            or self.before_version <= 0
            or self.after_version <= 0
        ):
            raise JobDescriptionTurnDataError("完成輪次的固定 JD 版本不完整")


class CompletedTurnReader(Protocol):
    async def __call__(
        self, *, workspace_id: UUID, turn_id: UUID
    ) -> JobDescriptionTurnVersions | None: ...


class JobDescriptionTurnChangesResult(BaseDTO):
    workspace_id: UUID
    job_description_id: UUID
    turn_id: UUID
    before_version: int
    after_version: int
    before: JobDescriptionContent
    after: JobDescriptionContent
    difference: JobDescriptionDifference


async def get_turn_changes(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    turn_id: UUID,
    completed_turn_reader: CompletedTurnReader,
    queries: HistoryQueries,
) -> JobDescriptionTurnChangesResult:
    versions = await _completed_versions(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        turn_id=turn_id,
        completed_turn_reader=completed_turn_reader,
    )
    return await asyncio.to_thread(_read_changes, versions=versions, queries=queries)


async def restore_completed_turn_changes(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    turn_id: UUID,
    completed_turn_reader: CompletedTurnReader,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
) -> JobDescriptionResult:
    """完成紀錄提供固定兩端；核心用例在根鎖內核對持久修改區段。"""
    versions = await _completed_versions(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        turn_id=turn_id,
        completed_turn_reader=completed_turn_reader,
    )
    return await asyncio.to_thread(
        turn_changes.restore_turn_changes,
        workspace_id=workspace_id,
        input=turn_changes.RestoreTurnChangesInput(
            job_description_id=job_description_id,
            base_version=versions.before_version,
            completed_version=versions.after_version,
            correlation_id=str(turn_id),
        ),
        uow_factory=uow_factory,
    )


async def _completed_versions(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    turn_id: UUID,
    completed_turn_reader: CompletedTurnReader,
) -> JobDescriptionTurnVersions:
    versions = await completed_turn_reader(workspace_id=workspace_id, turn_id=turn_id)
    if versions is None or (
        versions.workspace_id != workspace_id
        or versions.job_description_id != job_description_id
        or versions.turn_id != turn_id
    ):
        raise JobDescriptionTurnNotFoundError("指定範圍沒有此 JD 完成輪次")
    return versions


def _read_changes(
    *, versions: JobDescriptionTurnVersions, queries: HistoryQueries
) -> JobDescriptionTurnChangesResult:
    before = _read_content(versions, versions.before_version, queries)
    after = (
        before
        if versions.before_version == versions.after_version
        else _read_content(versions, versions.after_version, queries)
    )
    return JobDescriptionTurnChangesResult(
        workspace_id=versions.workspace_id,
        job_description_id=versions.job_description_id,
        turn_id=versions.turn_id,
        before_version=versions.before_version,
        after_version=versions.after_version,
        before=before,
        after=after,
        difference=compare_contents(
            before,
            after,
            before_version=versions.before_version,
            after_version=versions.after_version,
        ),
    )


def _read_content(
    versions: JobDescriptionTurnVersions, version: int, queries: HistoryQueries
) -> JobDescriptionContent:
    try:
        saved = get_history(
            workspace_id=versions.workspace_id,
            job_description_id=versions.job_description_id,
            version=version,
            queries=queries,
        )
    except (
        JobDescriptionNotFoundError,
        JobDescriptionHistoryNotFoundError,
        JobDescriptionHistoryDataError,
    ) as error:
        raise JobDescriptionTurnDataError("完成輪次的固定 JD 歷史不可用") from error
    return saved.content
