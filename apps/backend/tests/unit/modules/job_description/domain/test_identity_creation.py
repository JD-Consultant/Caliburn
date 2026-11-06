"""新增身分由 Domain 配發，引用與後續修改沿用生成的 ID。"""

from uuid import UUID, uuid7

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def test_creation_generates_uuid7_but_reconstitution_requires_an_identity() -> None:
    """首次建立配發 UUIDv7；復水不得以缺少 ID 的資料冒充新建。"""
    workspace_id = uuid7()
    jd = JobDescription.create(workspace_id=workspace_id)
    assert jd.id.version == 7
    assert jd.workspace_id == workspace_id
    assert JobDescription.create(workspace_id=workspace_id).id != jd.id
    restored = JobDescription.model_validate(jd.model_dump())
    assert restored.id == jd.id

    with pytest.raises(ValidationError):
        JobDescription.model_validate({"workspace_id": workspace_id})
    with pytest.raises(ValidationError):
        jd.id = uuid7()


def test_additions_generate_identifiers_and_preserve_mixed_definition_order() -> None:
    """新舊 K/S 交錯引用、O/P 與其他成員都取得自己的 UUIDv7。"""
    jd = JobDescription(id=UUID(int=1), workspace_id=UUID(int=2))
    duty_id = jd.add_duty(name="資料整理")
    knowledge_id = jd.add_knowledge(name="既有知識")
    skill_id = jd.add_skill(name="既有技能")
    task_id = jd.add_task(
        name="查詢資料",
        duty_id=duty_id,
        outcomes=("查詢報表", "明細清單"),
        requirements=("內容正確",),
        knowledge=(knowledge_id, ("新知識", None), knowledge_id),
        skills=(("新技能", "分析能力"), skill_id),
    )
    outcome_id = jd.add_outcome(task_id=task_id, text="附錄")
    requirement_id = jd.add_requirement(task_id=task_id, text="按時交付")
    collaboration_id = jd.add_collaboration(collaborator_name="人資")
    condition_id = jd.add_condition(kind=ConditionKind.QUALIFICATION, text="熟悉資料")

    task = jd.get_task(task_id=task_id)
    assert task.duty_id == duty_id
    assert task.knowledge_ids == (knowledge_id, jd.knowledge[1].id)
    assert task.skill_ids == (jd.skills[1].id, skill_id)
    assert task.outcomes[-1].id == outcome_id
    assert task.requirements[-1].id == requirement_id
    assert jd.collaborations[0].id == collaboration_id
    assert jd.conditions[0].id == condition_id
    identities = (
        duty_id,
        task_id,
        *(entry.id for entry in jd.knowledge),
        *(entry.id for entry in jd.skills),
        *(entry.id for entry in task.outcomes),
        *(entry.id for entry in task.requirements),
        collaboration_id,
        condition_id,
    )
    assert all(identity.version == 7 for identity in identities)
    assert len(identities) == len(set(identities))
