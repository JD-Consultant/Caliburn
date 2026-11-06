"""局部查詢的同快照 JD 版本；不宣稱呼叫端其他快取已同步。"""

from uuid import UUID

from pydantic import PositiveInt

from caliburn.modules.job_description.application.content import (
    DutyResult,
    KnowledgeResult,
    SkillResult,
    TaskResult,
)
from caliburn.shared.application.base_dto import BaseDTO


class DutyQueryResult(BaseDTO):
    job_description_id: UUID
    jd_version: PositiveInt
    duty: DutyResult


class TaskQueryResult(BaseDTO):
    job_description_id: UUID
    jd_version: PositiveInt
    task: TaskResult


class KnowledgeQueryResult(BaseDTO):
    job_description_id: UUID
    jd_version: PositiveInt
    knowledge: KnowledgeResult


class SkillQueryResult(BaseDTO):
    job_description_id: UUID
    jd_version: PositiveInt
    skill: SkillResult
