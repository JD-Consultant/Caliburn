"""只保存本輪取消基準與模型已見版本，不備份 JD 正文。"""

from typing import NotRequired, TypedDict
from uuid import UUID

from caliburn.modules.agent.state import AgentState


class JobDescriptionState(TypedDict):
    jd_turn_id: UUID
    jd_id: UUID | None
    jd_turn_start_version: int | None
    jd_version: int | None
    jd_manual_before_version: int | None
    jd_completed_version: int | None


class JobDescriptionTurnState(TypedDict):
    workspace_id: UUID
    turn_id: UUID


class JobDescriptionToolState(TypedDict):
    workspace_id: UUID
    turn_id: UUID
    jd_id: UUID | None
    jd_version: int | None
    memory_published_version: NotRequired[int | None]


class JobDescriptionExecutionState(AgentState, JobDescriptionState):
    pass
