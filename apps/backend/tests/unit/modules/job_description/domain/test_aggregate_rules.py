"""完整 JD 聚合的不變條件、複合新增、刪除與總覽順序。"""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import (
    CollaborationNotFoundError,
    DuplicateIdentityError,
    DuplicateNameError,
    DutyNotFoundError,
    InvalidDefinitionOrderError,
    InvalidTaskReferenceError,
    JobConditionNotFoundError,
    KnowledgeNotFoundError,
    SkillNotFoundError,
    TaskNotFoundError,
)
from caliburn.modules.job_description.domain.models import job_description as root_model
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
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

JD_ID = UUID(int=1)


@pytest.fixture
def populated() -> JobDescription:
    return JobDescription(
        id=JD_ID,
        workspace_id=UUID(int=2),
        job_title="原職稱",
        duties=(
            Duty.create(id=UUID(int=10), job_description_id=JD_ID, name="分類A"),
            Duty.create(id=UUID(int=11), job_description_id=JD_ID, name="分類B"),
        ),
        knowledge=(
            Knowledge.create(id=UUID(int=20), job_description_id=JD_ID, name="知識A"),
            Knowledge.create(id=UUID(int=21), job_description_id=JD_ID, name="知識B"),
        ),
        skills=(
            Skill.create(id=UUID(int=30), job_description_id=JD_ID, name="技能A"),
            Skill.create(id=UUID(int=31), job_description_id=JD_ID, name="技能B"),
        ),
        tasks=(
            JobTask.create(
                id=UUID(int=40),
                job_description_id=JD_ID,
                name="任務A",
                duty_id=UUID(int=10),
                outcomes=(TaskOutcome(id=UUID(int=50), text="成果A"),),
                requirements=(TaskRequirement(id=UUID(int=60), text="要求A"),),
                knowledge_ids=(UUID(int=21), UUID(int=20)),
                skill_ids=(UUID(int=30), UUID(int=31)),
            ),
            JobTask.create(
                id=UUID(int=41),
                job_description_id=JD_ID,
                name="任務B",
                duty_id=UUID(int=11),
                outcomes=(TaskOutcome(id=UUID(int=51), text="成果B"),),
                knowledge_ids=(UUID(int=20),),
                skill_ids=(UUID(int=31), UUID(int=30)),
            ),
            JobTask.create(id=UUID(int=42), job_description_id=JD_ID, name="未分類"),
        ),
        collaborations=(CollaborationEntry(id=UUID(int=70), collaborator_name="顧問"),),
        conditions=(
            JobCondition(
                id=UUID(int=80), kind=ConditionKind.QUALIFICATION, text="資格"
            ),
        ),
    )


@pytest.mark.parametrize("kind", ["duty", "task", "knowledge", "skill"])
def test_add_rejects_existing_identity_and_same_kind_name(
    populated: JobDescription, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = populated.model_dump()
    existing_id = UUID(int={"duty": 10, "task": 40, "knowledge": 20, "skill": 30}[kind])
    for duplicate_id in (True, False):
        with monkeypatch.context() as identity_collision:
            if duplicate_id:
                identity_collision.setattr(root_model, "uuid7", lambda: existing_id)
            with pytest.raises(
                DuplicateIdentityError if duplicate_id else DuplicateNameError
            ):
                if kind == "duty":
                    populated.add_duty(name="新名" if duplicate_id else " 分類A ")
                elif kind == "task":
                    populated.add_task(
                        name="新名" if duplicate_id else " 任務A ",
                        duty_id=UUID(int=11),
                    )
                elif kind == "knowledge":
                    populated.add_knowledge(name="新名" if duplicate_id else " 知識A ")
                else:
                    populated.add_skill(name="新名" if duplicate_id else " 技能A ")
        assert populated.model_dump() == before
    collection = {
        "duty": "duties",
        "task": "tasks",
        "knowledge": "knowledge",
        "skill": "skills",
    }[kind]
    payload = populated.model_dump()
    payload[collection] = (*payload[collection], payload[collection][0])
    with pytest.raises(DuplicateIdentityError):
        JobDescription.model_validate(payload)


def test_different_kinds_can_share_names_and_new_tasks_append_to_own_group(
    populated: JobDescription,
) -> None:
    populated.add_duty(name="共同名稱")
    populated.add_knowledge(name="共同名稱")
    populated.add_skill(name="共同名稱")
    task_id = populated.add_task(name="共同名稱", duty_id=UUID(int=10))
    assert tuple(
        item.id for item in populated.tasks if item.duty_id == UUID(int=10)
    ) == (UUID(int=40), task_id)
    assert tuple(item.id.int for item in populated.tasks if item.duty_id is None) == (
        42,
    )


@pytest.mark.parametrize("invalid_reference", ["duty", "knowledge", "skill"])
def test_late_invalid_reference_rejects_complete_task_and_all_new_definitions(
    populated: JobDescription,
    invalid_reference: str,
) -> None:
    before = populated.model_dump()
    with pytest.raises(InvalidTaskReferenceError):
        populated.add_task(
            name="新任務",
            duty_id=UUID(int=99 if invalid_reference == "duty" else 10),
            outcomes=("新成果",),
            requirements=("新要求",),
            knowledge=(
                ("新知識", None),
                UUID(int=99 if invalid_reference == "knowledge" else 20),
                UUID(int=20),
            ),
            skills=(
                ("新技能", None),
                UUID(int=99 if invalid_reference == "skill" else 30),
                UUID(int=30),
            ),
        )
    assert populated.model_dump() == before


@pytest.mark.parametrize("kind", ["knowledge", "skill"])
@pytest.mark.parametrize("collision", ["existing", "batch"])
def test_complete_task_rejects_new_definition_name_conflicts(
    populated: JobDescription,
    kind: str,
    collision: str,
) -> None:
    name = (
        (" 知識A " if kind == "knowledge" else " 技能A ")
        if collision == "existing"
        else "新定義"
    )
    new_knowledge: tuple[tuple[str, str | None], ...] = ((name, None),)
    new_skills: tuple[tuple[str, str | None], ...] = ((name, None),)
    if collision == "batch":
        new_knowledge += ((" 新定義 ", None),)
        new_skills += ((" 新定義 ", None),)
    before = populated.model_dump()
    with pytest.raises(DuplicateNameError):
        populated.add_task(
            name="新任務",
            knowledge=new_knowledge if kind == "knowledge" else (),
            skills=new_skills if kind == "skill" else (),
        )
    assert populated.model_dump() == before


@pytest.mark.parametrize("kind", ["outcome", "requirement"])
def test_owned_identity_cannot_be_reused_across_tasks(
    populated: JobDescription, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    before = populated.model_dump()
    duplicate_id = UUID(int=50 if kind == "outcome" else 60)
    monkeypatch.setattr(root_model, "uuid7", lambda: duplicate_id)
    with pytest.raises(DuplicateIdentityError):
        if kind == "outcome":
            populated.add_outcome(task_id=UUID(int=41), text="其他")
        else:
            populated.add_requirement(task_id=UUID(int=41), text="其他")
    assert populated.model_dump() == before
    with pytest.raises(DuplicateIdentityError):
        populated.add_task(
            name="新任務",
            outcomes=("其他",) if kind == "outcome" else (),
            requirements=("其他",) if kind == "requirement" else (),
        )
    assert populated.model_dump() == before
    payload = populated.model_dump()
    target = next(item for item in payload["tasks"] if item["id"] == UUID(int=41))
    target[f"{kind}s"] = (
        {"id": UUID(int=50 if kind == "outcome" else 60), "text": "重複"},
    )
    with pytest.raises(DuplicateIdentityError):
        JobDescription.model_validate(payload)


def test_remove_task_preserves_new_and_existing_shared_definitions(
    populated: JobDescription,
) -> None:
    task_id = populated.add_task(
        name="新任務",
        outcomes=("成果",),
        knowledge=(("新知識", None),),
        skills=(("新技能", None),),
    )
    task = populated.get_task(task_id=task_id)
    knowledge_id, skill_id = task.knowledge_ids[0], task.skill_ids[0]
    before = populated.model_dump()
    remove_task: Callable[..., object] = populated.remove_task
    assert remove_task(task_id=task_id) is None
    assert populated.model_dump() == before | {
        "tasks": tuple(item for item in before["tasks"] if item["id"] != task_id)
    }
    assert tuple(item.id for item in populated.knowledge) == (
        UUID(int=20),
        UUID(int=21),
        knowledge_id,
    )
    assert tuple(item.id for item in populated.skills) == (
        UUID(int=30),
        UUID(int=31),
        skill_id,
    )
    with pytest.raises(TaskNotFoundError):
        populated.get_task(task_id=task_id)


def test_shared_definition_edits_and_deletion_preserve_task_identity_and_content(
    populated: JobDescription,
) -> None:
    first, second = (
        populated.get_task(task_id=UUID(int=40)),
        populated.get_task(task_id=UUID(int=41)),
    )
    first_before, second_before = first.model_dump(), second.model_dump()
    assert (
        populated.update_knowledge(
            knowledge_id=UUID(int=20), name="新知識", description="新說明"
        )
        is True
    )
    assert first.model_dump() == first_before and second.model_dump() == second_before
    populated.remove_knowledge(knowledge_id=UUID(int=20))
    populated.remove_skill(skill_id=UUID(int=30))
    assert first.model_dump() == first_before | {
        "knowledge_ids": (UUID(int=21),),
        "skill_ids": (UUID(int=31),),
    }
    assert second.model_dump() == second_before | {
        "knowledge_ids": (),
        "skill_ids": (UUID(int=31),),
    }
    assert populated.get_task(task_id=first.id) is first
    assert populated.get_task(task_id=second.id) is second


def test_remove_duty_appends_its_tasks_after_unclassified_and_keeps_other_groups(
    populated: JobDescription,
) -> None:
    task_id = populated.add_task(name="同分類第二項", duty_id=UUID(int=10))
    other = populated.get_task(task_id=UUID(int=41))
    other_before = other.model_dump()
    populated.remove_duty(duty_id=UUID(int=10))
    assert tuple(task.id for task in populated.tasks if task.duty_id is None) == (
        UUID(int=42),
        UUID(int=40),
        task_id,
    )
    assert other.model_dump() == other_before
    assert tuple(
        task.id.int for task in populated.tasks if task.duty_id == UUID(int=11)
    ) == (41,)


@pytest.mark.parametrize(
    ("move", "identities"),
    [
        (
            lambda jd, before: jd.move_duty(duty_id=UUID(int=11), before_id=before),
            (10, 11),
        ),
        (
            lambda jd, before: jd.move_knowledge(
                knowledge_id=UUID(int=21), before_id=before
            ),
            (20, 21),
        ),
        (
            lambda jd, before: jd.move_skill(skill_id=UUID(int=31), before_id=before),
            (30, 31),
        ),
    ],
)
def test_overview_ordering_preserves_references_and_rejects_bad_anchors(
    populated: JobDescription,
    move: Callable[[JobDescription, UUID | None], bool],
    identities: tuple[int, int],
) -> None:
    tasks_before = {task.id: task.model_dump() for task in populated.tasks}
    assert move(populated, UUID(int=identities[0])) is True
    assert move(populated, UUID(int=identities[0])) is False
    assert {task.id: task.model_dump() for task in populated.tasks} == tasks_before
    before = populated.model_dump()
    for anchor in (UUID(int=identities[1]), UUID(int=999)):
        with pytest.raises(InvalidDefinitionOrderError):
            move(populated, anchor)
    with pytest.raises(ValidationError):
        move(populated, cast(UUID, "invalid"))
    assert populated.model_dump() == before
    assert move(populated, None) is True
    assert move(populated, None) is False


@pytest.mark.parametrize(
    ("move", "error"),
    [
        (
            lambda jd: jd.move_duty(duty_id=UUID(int=999), before_id=UUID(int=999)),
            DutyNotFoundError,
        ),
        (
            lambda jd: jd.move_knowledge(
                knowledge_id=UUID(int=999), before_id=UUID(int=999)
            ),
            KnowledgeNotFoundError,
        ),
        (
            lambda jd: jd.move_skill(skill_id=UUID(int=999), before_id=UUID(int=999)),
            SkillNotFoundError,
        ),
        (
            lambda jd: jd.move_collaboration(
                collaboration_id=UUID(int=999), before_id=UUID(int=999)
            ),
            CollaborationNotFoundError,
        ),
        (
            lambda jd: jd.move_condition(
                condition_id=UUID(int=999), before_id=UUID(int=999)
            ),
            JobConditionNotFoundError,
        ),
    ],
)
def test_missing_ordering_target_precedes_anchor_rejection(
    populated: JobDescription,
    move: Callable[[JobDescription], bool],
    error: type[Exception],
) -> None:
    before = populated.model_dump()
    with pytest.raises(error):
        move(populated)
    assert populated.model_dump() == before


@pytest.mark.parametrize(
    ("remove", "error"),
    [
        (lambda jd: jd.remove_duty(duty_id=UUID(int=999)), DutyNotFoundError),
        (lambda jd: jd.remove_task(task_id=UUID(int=999)), TaskNotFoundError),
        (
            lambda jd: jd.remove_knowledge(knowledge_id=UUID(int=999)),
            KnowledgeNotFoundError,
        ),
        (lambda jd: jd.remove_skill(skill_id=UUID(int=999)), SkillNotFoundError),
    ],
)
def test_missing_deletion_preserves_complete_content(
    populated: JobDescription,
    remove: Callable[[JobDescription], object],
    error: type[Exception],
) -> None:
    before = populated.model_dump()
    with pytest.raises(error):
        remove(populated)
    assert populated.model_dump() == before


@pytest.mark.parametrize(
    "reject",
    [
        lambda jd: jd.add_duty(name=cast(str, 123)),
        lambda jd: jd.add_knowledge(name=cast(str, 123)),
        lambda jd: jd.add_skill(name=cast(str, 123)),
        lambda jd: jd.add_task(
            name="新任務",
            description=cast(str, 123),
            knowledge=(("新知識", None),),
        ),
        lambda jd: jd.update_duty(
            duty_id=UUID(int=10), name="新職責", scope=cast(str, 123)
        ),
        lambda jd: jd.update_knowledge(
            knowledge_id=UUID(int=20), name="新知識", description=cast(str, 123)
        ),
        lambda jd: jd.update_skill(
            skill_id=UUID(int=30), name="新技能", description=cast(str, 123)
        ),
        lambda jd: jd.update_task(
            task_id=UUID(int=40),
            name="新任務",
            description=cast(str, 123),
            competency_level=None,
        ),
        lambda jd: jd.add_outcome(task_id=UUID(int=40), text=cast(str, 123)),
        lambda jd: jd.add_requirement(task_id=UUID(int=40), text=cast(str, 123)),
        lambda jd: jd.update_outcome(
            task_id=UUID(int=40), outcome_id=UUID(int=50), text=cast(str, 123)
        ),
        lambda jd: jd.update_requirement(
            task_id=UUID(int=40), requirement_id=UUID(int=60), text=cast(str, 123)
        ),
        lambda jd: jd.remove_duty(duty_id=cast(UUID, "10")),
        lambda jd: jd.remove_task(task_id=cast(UUID, "40")),
        lambda jd: jd.remove_knowledge(knowledge_id=cast(UUID, "20")),
        lambda jd: jd.remove_skill(skill_id=cast(UUID, "30")),
        lambda jd: jd.remove_outcome(task_id=UUID(int=40), outcome_id=cast(UUID, "50")),
        lambda jd: jd.remove_requirement(
            task_id=UUID(int=40), requirement_id=cast(UUID, "60")
        ),
        lambda jd: jd.link_knowledge(
            task_id=UUID(int=40), knowledge_id=cast(UUID, "20")
        ),
        lambda jd: jd.link_skill(task_id=UUID(int=40), skill_id=cast(UUID, "30")),
        lambda jd: jd.unlink_knowledge(
            task_id=UUID(int=40), knowledge_id=cast(UUID, "20")
        ),
        lambda jd: jd.unlink_skill(task_id=UUID(int=40), skill_id=cast(UUID, "30")),
        lambda jd: jd.move_knowledge_reference(
            task_id=UUID(int=40), knowledge_id=cast(UUID, "20"), before_id=None
        ),
        lambda jd: jd.move_skill_reference(
            task_id=UUID(int=40), skill_id=cast(UUID, "30"), before_id=None
        ),
        lambda jd: jd.move_task(
            task_id=UUID(int=40),
            destination_duty_id=UUID(int=11),
            before_id=cast(UUID, "41"),
        ),
        lambda jd: jd.add_collaboration(
            collaborator_name="新對象",
            scope=cast(str, 123),
        ),
        lambda jd: jd.add_condition(
            kind=ConditionKind.QUALIFICATION,
            text=cast(str, 123),
        ),
        lambda jd: jd.update_collaboration(
            collaboration_id=UUID(int=70),
            collaborator_name="新對象",
            scope=cast(str, 123),
        ),
        lambda jd: jd.update_condition(condition_id=UUID(int=80), text=cast(str, 123)),
        lambda jd: jd.remove_collaboration(collaboration_id=cast(UUID, "70")),
        lambda jd: jd.remove_condition(condition_id=cast(UUID, "80")),
        lambda jd: jd.move_collaboration(
            collaboration_id=UUID(int=70), before_id=cast(UUID, "80")
        ),
        lambda jd: jd.move_condition(
            condition_id=UUID(int=80), before_id=cast(UUID, "70")
        ),
        lambda jd: jd.reclassify_condition(
            condition_id=UUID(int=80), kind=cast(ConditionKind, "qualification")
        ),
    ],
)
def test_type_rejection_preserves_the_entire_populated_aggregate(
    populated: JobDescription,
    reject: Callable[[JobDescription], object],
) -> None:
    before = populated.model_dump()
    with pytest.raises(ValidationError):
        reject(populated)
    assert populated.model_dump() == before


def test_every_condition_kind_allows_multiple_entries_and_text_noop(
    populated: JobDescription,
) -> None:
    original_task = populated.get_task(task_id=UUID(int=40)).model_dump()
    for kind in ConditionKind:
        for _ in range(2):
            populated.add_condition(kind=kind, text="同文")
        group = tuple(item for item in populated.conditions if item.kind == kind)
        assert len(group) >= 2
    assert populated.update_condition(condition_id=UUID(int=80), text="資格") is False
    assert (
        populated.update_condition(condition_id=UUID(int=80), text=" 新資格 ") is True
    )
    assert populated.get_condition(condition_id=UUID(int=80)).text == " 新資格 "
    assert populated.get_task(task_id=UUID(int=40)).model_dump() == original_task
