"""以同一資料庫視圖讀取 Workspace 與目前 Plan。"""

from uuid import UUID

from sqlalchemy import Engine, and_, select
from sqlalchemy.orm import Session

from caliburn.modules.plan.application.errors import (
    PlanDataError,
    PlanQueryError,
    WorkspaceNotFoundError,
)
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.domain.plan import Plan
from caliburn.modules.plan.infrastructure.persistence.orm_models import (
    PlanRow,
    PlanVersionRow,
)
from caliburn.modules.workspace.infrastructure.persistence.public_queries import (
    select_workspace_id,
)


class SqlAlchemyPlanQueries:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_current(self, *, workspace_id: UUID) -> PlanView:
        workspace = select_workspace_id(workspace_id=workspace_id).subquery()
        statement = (
            select(workspace.c.id, PlanRow, PlanVersionRow)
            .select_from(workspace)
            .outerjoin(PlanRow, PlanRow.workspace_id == workspace.c.id)
            .outerjoin(
                PlanVersionRow,
                and_(
                    PlanVersionRow.workspace_id == PlanRow.workspace_id,
                    PlanVersionRow.version == PlanRow.version,
                ),
            )
        )
        try:
            with Session(self._engine) as session:
                row = session.execute(statement).one_or_none()
                if row is None:
                    raise WorkspaceNotFoundError("Workspace 不存在")
                _, current, snapshot = row
                if current is None:
                    return PlanView(workspace_id=workspace_id, version=None, body=None)
                if snapshot is None or snapshot.body != current.body:
                    raise PlanDataError("Plan 目前內容與已保存版本不一致")
                try:
                    plan = Plan(
                        id=workspace_id, version=current.version, body=current.body
                    )
                except ValueError as error:
                    raise PlanDataError("Plan 目前版本無法重建") from error
                return PlanView(
                    workspace_id=workspace_id,
                    version=plan.version,
                    body=plan.body,
                )
        except WorkspaceNotFoundError, PlanDataError:
            raise
        except Exception as error:
            raise PlanQueryError("Plan 查詢或資源釋放失敗") from error
