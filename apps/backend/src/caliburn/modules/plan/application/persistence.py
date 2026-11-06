"""Plan 用例擁有的短交易與完整版本儲存契約。"""

from typing import Protocol
from uuid import UUID

from caliburn.modules.plan.domain.plan import Plan
from caliburn.modules.plan.domain.snapshot import PlanSnapshot
from caliburn.shared.application.base_unit_of_work import BaseUnitOfWork


class PlanRepository(Protocol):
    def lock_workspace(self, *, workspace_id: UUID) -> None:
        """初始化前鎖 Workspace；不存在即拒絕。"""
        ...

    def get_for_update(self, *, workspace_id: UUID) -> Plan | None:
        """鎖定並驗證目前 Plan；None 僅表示現存 Workspace 尚未初始化。"""
        ...

    def add(self, plan: Plan) -> None:
        """寫入新根及首版，留在呼叫者交易中。"""
        ...

    def save(self, plan: Plan) -> None:
        """以載入時版本保護目前列與新快照，無隱式 commit。"""
        ...

    def get_snapshot(self, *, workspace_id: UUID, version: int) -> PlanSnapshot:
        """只取指定 Workspace 已保存版本，不提供產品歷史列表。"""
        ...


class PlanUnitOfWork(BaseUnitOfWork, Protocol):
    @property
    def plans(self) -> PlanRepository: ...
