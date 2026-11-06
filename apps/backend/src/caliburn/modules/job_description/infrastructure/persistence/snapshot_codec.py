"""完整快照 v1 codec：先驗儲存格式，再以 Domain 規則重建。"""

import json
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from caliburn.modules.job_description.application.content import JobDescriptionContent
from caliburn.modules.job_description.application.errors import (
    JobDescriptionHistoryDataError,
)
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)
from caliburn.shared.domain.domain_error import DomainError

SCHEMA_VERSION = 2


def encode_snapshot(job_description: JobDescription) -> dict[str, Any]:
    """JSONB 接受 JSON 相容 object；不把整份 JSON 字串再存進 JSONB。"""
    return JobDescriptionContent.from_domain(job_description).model_dump(mode="json")


def decode_snapshot(
    content: object,
    *,
    schema_version: int,
    workspace_id: UUID,
    job_description_id: UUID,
) -> JobDescription:
    try:
        if type(schema_version) is not int or schema_version not in (1, SCHEMA_VERSION):
            raise ValueError("未知快照格式")
        if not isinstance(content, dict):
            raise ValueError("快照必須是完整 JSON object")
        if schema_version == 2 and "citations" not in content:
            raise ValueError("引用格式快照必須包含完整引用集合")
        if schema_version == 1 and content.get("citations"):
            raise ValueError("舊格式快照不能含來源引用")
        # strict Python mode 不接受 JSON 的 UUID 字串／陣列；明示 JSON 語意，
        # 保留 strict 數字及所有必要欄位，不以 strict=False 擴大接受範圍。
        dto = JobDescriptionContent.model_validate_json(json.dumps(content))
        if (
            dto.job_description_id != job_description_id
            or dto.workspace_id != workspace_id
        ):
            raise ValueError("快照身分不符合已核對範圍")
        for task in dto.tasks:
            for references in (task.knowledge_ids, task.skill_ids):
                if len(references) != len(set(references)):
                    raise ValueError("快照含重複引用，不能透過 Domain 正規化修復")
        return _to_domain(dto)
    except (ValidationError, DomainError, ValueError, TypeError) as error:
        raise JobDescriptionHistoryDataError("歷史內容不符合完整 JD 結構") from error


def _level(value: int | None) -> CompetencyLevel | None:
    return CompetencyLevel(value=value) if value is not None else None


def _to_domain(content: JobDescriptionContent) -> JobDescription:
    jd_id = content.job_description_id
    return JobDescription(
        id=jd_id,
        workspace_id=content.workspace_id,
        job_title=content.job_title,
        organization_unit=content.organization_unit,
        reports_to=content.reports_to,
        purpose=content.purpose,
        baseline_competency_level=_level(content.baseline_competency_level),
        duties=tuple(
            Duty.create(id=x.id, job_description_id=jd_id, name=x.name, scope=x.scope)
            for x in content.duties
        ),
        tasks=tuple(
            JobTask.create(
                id=x.id,
                job_description_id=jd_id,
                duty_id=x.duty_id,
                name=x.name,
                description=x.description,
                competency_level=x.competency_level,
                outcomes=tuple(TaskOutcome(id=y.id, text=y.text) for y in x.outcomes),
                requirements=tuple(
                    TaskRequirement(id=y.id, text=y.text) for y in x.requirements
                ),
                knowledge_ids=x.knowledge_ids,
                skill_ids=x.skill_ids,
            )
            for x in content.tasks
        ),
        knowledge=tuple(
            Knowledge.create(
                id=x.id,
                job_description_id=jd_id,
                name=x.name,
                description=x.description,
            )
            for x in content.knowledge
        ),
        skills=tuple(
            Skill.create(
                id=x.id,
                job_description_id=jd_id,
                name=x.name,
                description=x.description,
            )
            for x in content.skills
        ),
        collaborations=tuple(
            CollaborationEntry(
                id=x.id, collaborator_name=x.collaborator_name, scope=x.scope
            )
            for x in content.collaborations
        ),
        conditions=tuple(
            JobCondition(id=x.id, kind=x.kind, text=x.text) for x in content.conditions
        ),
        citations=content.citations,
    )
