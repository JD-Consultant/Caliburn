"""JD 唯讀入口及投影契約；每次讀取必須來自同一快照。"""

from typing import Protocol
from uuid import UUID

from caliburn.modules.job_description.application.errors import (
    DutyNotFoundError,
    JobDescriptionNotFoundError,
    KnowledgeNotFoundError,
    SkillNotFoundError,
    TaskNotFoundError,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.query_results import (
    DutyQueryResult,
    KnowledgeQueryResult,
    SkillQueryResult,
    TaskQueryResult,
)


class JobDescriptionQueries(Protocol):
    """每次讀取來自一個唯讀快照；不存在回 None，技術失敗不得冒充缺資料。"""

    def get_job_description(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> JobDescriptionResult | None: ...

    def find_job_description_by_workspace(
        self, *, workspace_id: UUID
    ) -> JobDescriptionResult | None: ...

    def get_task(
        self, *, workspace_id: UUID, job_description_id: UUID, task_id: UUID
    ) -> TaskQueryResult | None: ...

    def get_duty(
        self, *, workspace_id: UUID, job_description_id: UUID, duty_id: UUID
    ) -> DutyQueryResult | None: ...

    def get_knowledge(
        self, *, workspace_id: UUID, job_description_id: UUID, knowledge_id: UUID
    ) -> KnowledgeQueryResult | None: ...

    def get_skill(
        self, *, workspace_id: UUID, job_description_id: UUID, skill_id: UUID
    ) -> SkillQueryResult | None: ...


def get_job_description(
    *, workspace_id: UUID, job_description_id: UUID, queries: JobDescriptionQueries
) -> JobDescriptionResult:
    result = queries.get_job_description(
        workspace_id=workspace_id, job_description_id=job_description_id
    )
    if result is None:
        raise JobDescriptionNotFoundError("指定 JD 不存在")
    return result


def find_job_description_by_workspace(
    *, workspace_id: UUID, queries: JobDescriptionQueries
) -> JobDescriptionResult | None:
    return queries.find_job_description_by_workspace(workspace_id=workspace_id)


def get_task(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    task_id: UUID,
    queries: JobDescriptionQueries,
) -> TaskQueryResult:
    result = queries.get_task(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        task_id=task_id,
    )
    if result is None:
        raise TaskNotFoundError("指定 Task 不存在於此 JD")
    return result


def get_duty(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    duty_id: UUID,
    queries: JobDescriptionQueries,
) -> DutyQueryResult:
    result = queries.get_duty(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        duty_id=duty_id,
    )
    if result is None:
        raise DutyNotFoundError("指定 Duty 不存在於此 JD")
    return result


def get_knowledge(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    knowledge_id: UUID,
    queries: JobDescriptionQueries,
) -> KnowledgeQueryResult:
    result = queries.get_knowledge(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        knowledge_id=knowledge_id,
    )
    if result is None:
        raise KnowledgeNotFoundError("指定 Knowledge 不存在於此 JD")
    return result


def get_skill(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    skill_id: UUID,
    queries: JobDescriptionQueries,
) -> SkillQueryResult:
    result = queries.get_skill(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        skill_id=skill_id,
    )
    if result is None:
        raise SkillNotFoundError("指定 Skill 不存在於此 JD")
    return result
