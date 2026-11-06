"""JD 是完整內容的唯一編修入口。"""

from uuid import UUID

from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge


def test_add_complete_task_creates_owned_content_and_deduplicates_references() -> None:
    jd = JobDescription(id=UUID(int=1), workspace_id=UUID(int=2))
    duty_id = jd.add_duty(name="分析")
    existing_knowledge_id = jd.add_knowledge(name="既有流程知識")

    task_id = jd.add_task(
        name=" 整理流程 ",
        duty_id=duty_id,
        competency_level=3,
        outcomes=("流程圖",),
        requirements=("確認流程完整",),
        knowledge=(existing_knowledge_id, ("流程知識", None), existing_knowledge_id),
        skills=(("流程整理", None),),
    )

    task = jd.get_task(task_id=task_id)
    assert task.name.value == "整理流程" and task.duty_id == duty_id
    assert task.knowledge_ids == (existing_knowledge_id, jd.knowledge[1].id)
    assert task.skill_ids == (jd.skills[0].id,)
    assert task.competency_level is not None and task.competency_level.value == 3
    assert task.outcomes[0].id.version == 7 and task.outcomes[0].text == "流程圖"
    assert task.requirements[0].id.version == 7
    assert task.requirements[0].text == "確認流程完整"
    assert jd.knowledge[1].name.value == "流程知識"
    assert jd.skills[0].name.value == "流程整理"
    assert task.job_description_id == jd.id


def test_deletion_cleans_all_tasks_and_preserves_unclassified_order() -> None:
    jd = JobDescription(
        id=UUID(int=1),
        workspace_id=UUID(int=2),
        duties=(
            Duty.create(job_description_id=UUID(int=1), id=UUID(int=10), name="分類"),
        ),
        knowledge=(
            Knowledge.create(
                job_description_id=UUID(int=1), id=UUID(int=20), name="知識"
            ),
        ),
        tasks=(
            JobTask.create(
                job_description_id=UUID(int=1),
                id=UUID(int=40),
                name="A",
                duty_id=UUID(int=10),
                knowledge_ids=(UUID(int=20),),
            ),
            JobTask.create(
                job_description_id=UUID(int=1),
                id=UUID(int=41),
                name="B",
                knowledge_ids=(UUID(int=20),),
            ),
            JobTask.create(
                job_description_id=UUID(int=1),
                id=UUID(int=42),
                name="C",
                duty_id=UUID(int=10),
            ),
            JobTask.create(job_description_id=UUID(int=1), id=UUID(int=43), name="D"),
        ),
    )
    first = jd.get_task(task_id=UUID(int=40))

    jd.remove_duty(duty_id=UUID(int=10))
    jd.remove_knowledge(knowledge_id=UUID(int=20))

    assert tuple(task.name.value for task in jd.tasks) == ("B", "D", "A", "C")
    assert all(task.duty_id is None and task.knowledge_ids == () for task in jd.tasks)
    assert jd.get_task(task_id=first.id) is first
    assert jd.duties == jd.knowledge == ()
