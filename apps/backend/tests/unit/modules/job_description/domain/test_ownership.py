"""JD 根建立成員時賦予歸屬，完整復水拒絕跨 JD 成員。"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.entry_name import EntryName
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.shared.domain.domain_error import DomainError


@pytest.mark.parametrize("entity_type", [Duty, JobTask, Knowledge, Skill])
def test_internal_entity_requires_immutable_jd_ownership(
    entity_type: type[Duty] | type[JobTask] | type[Knowledge] | type[Skill],
) -> None:
    with pytest.raises(ValidationError) as error:
        entity_type.model_validate(
            {"id": UUID(int=10), "name": EntryName(value="分析")}
        )
    assert [detail["loc"] for detail in error.value.errors()] == [
        ("job_description_id",)
    ]

    entry = entity_type.create(
        id=UUID(int=10), job_description_id=UUID(int=1), name="分析"
    )
    assert entity_type.model_validate(entry) is entry
    with pytest.raises(ValidationError):
        entry.__setattr__("job_description_id", UUID(int=2))
    assert entry.job_description_id == UUID(int=1)


@pytest.mark.parametrize("collection", ["duties", "tasks", "knowledge", "skills"])
def test_complete_construction_rejects_members_of_another_jd(collection: str) -> None:
    with pytest.raises(DomainError):
        JobDescription.model_validate(
            {
                "id": UUID(int=1),
                "workspace_id": UUID(int=2),
                collection: (
                    {
                        "id": UUID(int=10),
                        "job_description_id": UUID(int=99),
                        "name": EntryName(value="其他 JD 的內容"),
                    },
                ),
            }
        )


def test_root_assigns_ownership_to_every_new_member() -> None:
    jd = JobDescription(id=UUID(int=1), workspace_id=UUID(int=2))
    duty_id = jd.add_duty(name="職責")
    knowledge_id = jd.add_knowledge(name="知識")
    skill_id = jd.add_skill(name="技能")
    task_id = jd.add_task(
        name="任務",
        duty_id=duty_id,
        knowledge=(knowledge_id, ("新知識", "說明")),
        skills=(skill_id, ("新技能", "說明")),
    )

    assert all(item.job_description_id == jd.id for item in jd.duties)
    assert all(item.job_description_id == jd.id for item in jd.tasks)
    assert all(item.job_description_id == jd.id for item in jd.knowledge)
    assert all(item.job_description_id == jd.id for item in jd.skills)
    task = jd.get_task(task_id=task_id)
    assert task.knowledge_ids == (knowledge_id, jd.knowledge[1].id)
    assert task.skill_ids == (skill_id, jd.skills[1].id)
