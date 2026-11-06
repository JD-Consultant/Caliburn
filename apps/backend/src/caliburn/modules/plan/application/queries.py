"""不建立根的目前 Plan 查詢契約。"""

from typing import Protocol
from uuid import UUID

from caliburn.modules.plan.application.results import PlanView


class PlanQueries(Protocol):
    def get_current(self, *, workspace_id: UUID) -> PlanView:
        """區分無 Workspace、尚未初始化與資料／查詢失敗。"""
        ...
