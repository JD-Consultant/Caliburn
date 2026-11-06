"""以 mypy 檢查泛型 Factory、聚合根與 Workspace ports 的型別契約。"""

from uuid import UUID

from caliburn.modules.workspace.application.persistence import (
    WorkspaceRepository,
    WorkspaceUnitOfWork,
)
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.shared.application.base_repository import BaseRepository
from caliburn.shared.application.base_unit_of_work import BaseUnitOfWork
from caliburn.shared.domain.base_aggregate_root import BaseAggregateRoot
from caliburn.shared.domain.base_factory import BaseFactory


class IntervieweeNameFactory:
    def create(self, *, value: str) -> IntervieweeName:
        return IntervieweeName(value=value)


def build[**ParamsT, ProductT](
    factory: BaseFactory[ParamsT, ProductT],
    *args: ParamsT.args,
    **kwargs: ParamsT.kwargs,
) -> ProductT:
    """Factory 協定保留 keyword-only 輸入與具體回傳型別。"""
    return factory.create(*args, **kwargs)


def create_name() -> IntervieweeName:
    return build(IntervieweeNameFactory(), value="王小明")


def accept_root(workspace: Workspace) -> BaseAggregateRoot[UUID]:
    return workspace


def accept_repository(repository: WorkspaceRepository) -> BaseRepository[Workspace]:
    return repository


def accept_unit_of_work(unit_of_work: WorkspaceUnitOfWork) -> BaseUnitOfWork:
    return unit_of_work
