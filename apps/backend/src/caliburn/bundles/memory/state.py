"""保存顧問當輪發布版與歷史預載 capture；不保存模型引用別名。"""

from typing import TypedDict
from uuid import UUID

from caliburn.modules.agent.state import AgentState


class ConsultantMemoryState(TypedDict):
    memory_published_version: int | None
    memory_interview_ids: tuple[UUID, ...]
    memory_consolidation_requested: bool


class ConsultantState(AgentState, ConsultantMemoryState):
    pass
