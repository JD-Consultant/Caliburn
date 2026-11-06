"""鎖定單一 Plan，將目前根與完整版本留在同一交易。"""

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from caliburn.modules.plan.application.errors import (
    PlanConcurrencyError,
    PlanDataError,
    PlanVersionNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.plan.domain.plan import Plan
from caliburn.modules.plan.domain.snapshot import PlanSnapshot
from caliburn.modules.plan.infrastructure.persistence.orm_models import (
    PlanRow,
    PlanVersionRow,
)
from caliburn.modules.workspace.infrastructure.persistence.public_queries import (
    select_workspace_id,
)


class SqlAlchemyPlanRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._loaded_versions: dict[UUID, int] = {}

    def lock_workspace(self, *, workspace_id: UUID) -> None:
        exists = self._session.scalar(
            select_workspace_id(workspace_id=workspace_id).with_for_update()
        )
        if exists is None:
            raise WorkspaceNotFoundError("Workspace 不存在")

    def get_for_update(self, *, workspace_id: UUID) -> Plan | None:
        row = self._session.scalar(
            select(PlanRow)
            .where(PlanRow.workspace_id == workspace_id)
            .with_for_update()
        )
        if row is None:
            if (
                self._session.scalar(select_workspace_id(workspace_id=workspace_id))
                is None
            ):
                raise WorkspaceNotFoundError("Workspace 不存在")
            return None
        try:
            plan = Plan(id=workspace_id, version=row.version, body=row.body)
            snapshot = self.get_snapshot(workspace_id=workspace_id, version=row.version)
        except (ValueError, PlanVersionNotFoundError) as error:
            raise PlanDataError("Plan 目前版本無法重建") from error
        if snapshot.body != plan.body:
            raise PlanDataError("Plan 目前內容與已保存版本不一致")
        self._loaded_versions[workspace_id] = row.version
        return plan

    def add(self, plan: Plan) -> None:
        self._session.add(
            PlanRow(
                workspace_id=plan.workspace_id, version=plan.version, body=plan.body
            )
        )
        self._session.flush()
        self._session.add(
            PlanVersionRow(
                workspace_id=plan.workspace_id, version=plan.version, body=plan.body
            )
        )
        self._session.flush()

    def save(self, plan: Plan) -> None:
        loaded_version = self._loaded_versions.get(plan.workspace_id)
        if loaded_version is None:
            raise RuntimeError("必須先載入並鎖定 Plan 才能保存")
        saved = self._session.scalar(
            update(PlanRow)
            .where(
                PlanRow.workspace_id == plan.workspace_id,
                PlanRow.version == loaded_version,
            )
            .values(version=plan.version, body=plan.body)
            .returning(PlanRow.workspace_id)
        )
        if saved is None:
            raise PlanConcurrencyError()
        self._session.add(
            PlanVersionRow(
                workspace_id=plan.workspace_id, version=plan.version, body=plan.body
            )
        )
        self._session.flush()

    def get_snapshot(self, *, workspace_id: UUID, version: int) -> PlanSnapshot:
        row = self._session.get(PlanVersionRow, (workspace_id, version))
        if row is None:
            raise PlanVersionNotFoundError("Workspace 沒有指定的 Plan 版本")
        try:
            return PlanSnapshot(
                workspace_id=workspace_id, version=row.version, body=row.body
            )
        except ValueError as error:
            raise PlanDataError("Plan 已保存版本無法重建") from error
