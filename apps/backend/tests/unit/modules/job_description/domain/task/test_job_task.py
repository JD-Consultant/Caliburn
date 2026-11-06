"""由 JD 根驗 Task 內容、引用、封裝及失敗契約。"""

from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import (
    DuplicateIdentityError,
    InvalidCompetencyLevelError,
    InvalidTaskReferenceError,
    InvalidTextError,
    KnowledgeNotFoundError,
    SkillNotFoundError,
    TaskOutcomeNotFoundError,
    TaskRequirementNotFoundError,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.entry_name import EntryName
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

TASK_ID = UUID(int=1)


@pytest.mark.parametrize("level", [1, 6, None])
def test_creation_builds_optional_competency_level_in_domain(level: int | None) -> None:
    """建立任務接整數或未填，由 Domain 建立職能級別。"""
    jd = JobDescription(id=UUID(int=100), workspace_id=UUID(int=200))
    task_id = jd.add_task(name="分析任務", competency_level=level)

    assert jd.get_task(task_id=task_id).competency_level == (
        CompetencyLevel(value=level) if level is not None else None
    )


@pytest.mark.parametrize("level", [0, 7, True, "4", 4.0])
def test_creation_rejects_invalid_competency_level(level: object) -> None:
    """根新增不接受超出值域的級別，也不隱式轉換輸入型別。"""
    error = InvalidCompetencyLevelError if type(level) is int else ValidationError

    jd = JobDescription(id=UUID(int=100), workspace_id=UUID(int=200))
    before = jd.model_dump()
    with pytest.raises(error):
        jd.add_task(
            name="分析任務",
            competency_level=cast(int, level),
        )
    assert jd.model_dump() == before


def test_task_level_changes_independently_of_text_and_baseline(
    jd: JobDescription,
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    before = task.model_dump()
    jd.set_baseline_competency_level(competency_level=2)
    assert (
        jd.update_task(
            task_id=TASK_ID,
            name=task.name.value,
            description=None,
            competency_level=4,
        )
        is True
    )
    assert task.model_dump() == before | {"competency_level": {"value": 4}}
    assert jd.baseline_competency_level == CompetencyLevel(value=2)
    assert (
        jd.update_task(
            task_id=TASK_ID,
            name=task.name.value,
            description=None,
            competency_level=None,
        )
        is True
    )
    assert task.model_dump() == before


def test_complete_task_preserves_text_and_first_reference_positions(
    jd: JobDescription,
) -> None:
    task_id = jd.add_task(
        name=" 其他任務 ",
        duty_id=UUID(int=2),
        outcomes=("同文", "同文"),
        requirements=("要求",),
        knowledge=(UUID(int=21), UUID(int=20), UUID(int=21)),
        skills=(UUID(int=31), UUID(int=30), UUID(int=31)),
    )
    task = jd.get_task(task_id=task_id)
    assert task.name.value == "其他任務" and task.duty_id == UUID(int=2)
    assert task.knowledge_ids == (UUID(int=21), UUID(int=20))
    assert task.skill_ids == (UUID(int=31), UUID(int=30))
    assert [item.text for item in task.outcomes] == ["同文", "同文"]
    assert [item.text for item in task.requirements] == ["要求"]


def test_later_additions_match_complete_construction(jd: JobDescription) -> None:
    complete = jd.get_task(task_id=TASK_ID)
    incremental = JobDescription.model_validate(jd.model_dump() | {"tasks": ()})
    task_id = incremental.add_task(name=complete.name.value)
    outcome_id = incremental.add_outcome(
        task_id=task_id,
        text=complete.outcomes[0].text,
    )
    requirement_id = incremental.add_requirement(
        task_id=task_id,
        text=complete.requirements[0].text,
    )
    incremental.link_knowledge(task_id=task_id, knowledge_id=UUID(int=20))
    incremental.link_skill(task_id=task_id, skill_id=UUID(int=30))
    assert incremental.get_task(
        task_id=task_id
    ).model_dump() == complete.model_dump() | {
        "id": task_id,
        "outcomes": (complete.outcomes[0].model_dump() | {"id": outcome_id},),
        "requirements": (
            complete.requirements[0].model_dump() | {"id": requirement_id},
        ),
    }


def test_reference_changes_preserve_first_position_and_relink_at_end(
    jd: JobDescription,
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    assert jd.link_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=21)) is True
    assert jd.link_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=22)) is True
    assert jd.link_skill(task_id=TASK_ID, skill_id=UUID(int=31)) is True
    before = jd.model_dump()
    assert jd.link_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=20)) is False
    assert jd.link_skill(task_id=TASK_ID, skill_id=UUID(int=30)) is False
    assert jd.model_dump() == before
    assert jd.unlink_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=21)) is True
    assert list(task.knowledge_ids) == [UUID(int=20), UUID(int=22)]
    before = jd.model_dump()
    assert jd.unlink_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=21)) is False
    assert jd.model_dump() == before
    assert jd.link_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=21)) is True
    assert task.knowledge_ids == (UUID(int=20), UUID(int=22), UUID(int=21))
    assert jd.unlink_skill(task_id=TASK_ID, skill_id=UUID(int=30)) is True
    assert jd.unlink_skill(task_id=TASK_ID, skill_id=UUID(int=30)) is False
    assert jd.link_skill(task_id=TASK_ID, skill_id=UUID(int=30)) is True
    assert task.skill_ids == (UUID(int=31), UUID(int=30))


def test_reference_targets_must_exist_even_when_unlinking(jd: JobDescription) -> None:
    before = jd.model_dump()
    with pytest.raises(InvalidTaskReferenceError):
        jd.link_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=30))
    with pytest.raises(InvalidTaskReferenceError):
        jd.unlink_skill(task_id=TASK_ID, skill_id=UUID(int=20))
    with pytest.raises(KnowledgeNotFoundError):
        jd.get_knowledge(knowledge_id=UUID(int=30))
    with pytest.raises(SkillNotFoundError):
        jd.get_skill(skill_id=UUID(int=20))
    assert jd.model_dump() == before


def test_local_text_edit_keeps_entities_other_content_and_order(
    jd: JobDescription,
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    outcome, requirement = task.outcomes[0], task.requirements[0]
    jd.update_task(
        task_id=TASK_ID,
        name=task.name.value,
        description=None,
        competency_level=4,
    )
    before = task.model_dump()
    assert (
        jd.update_outcome(task_id=TASK_ID, outcome_id=outcome.id, text=" 新成果\n ")
        is True
    )
    assert (
        jd.update_requirement(
            task_id=TASK_ID, requirement_id=requirement.id, text=" 新要求\n "
        )
        is True
    )
    assert (
        jd.update_outcome(task_id=TASK_ID, outcome_id=outcome.id, text=" 新成果\n ")
        is False
    )
    assert (
        jd.update_requirement(
            task_id=TASK_ID, requirement_id=requirement.id, text=" 新要求\n "
        )
        is False
    )
    assert jd.get_task(task_id=TASK_ID) is task
    assert task.outcomes[0] is outcome and task.requirements[0] is requirement
    assert task.model_dump() == before | {
        "outcomes": ({"id": outcome.id, "text": " 新成果\n "},),
        "requirements": ({"id": requirement.id, "text": " 新要求\n "},),
    }


@pytest.mark.parametrize("kind", ["outcome", "requirement"])
def test_duplicate_owned_identity_cannot_partially_append(
    jd: JobDescription, kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing_id = UUID(int=10) if kind == "outcome" else UUID(int=11)
    monkeypatch.setattr(
        "caliburn.modules.job_description.domain.models.job_description.uuid7",
        lambda: existing_id,
    )
    before = jd.model_dump()
    with pytest.raises(DuplicateIdentityError):
        if kind == "outcome":
            jd.add_outcome(task_id=TASK_ID, text="其他")
        else:
            jd.add_requirement(task_id=TASK_ID, text="其他")
    assert jd.model_dump() == before


def test_same_text_with_distinct_ids_can_be_added(jd: JobDescription) -> None:
    outcome_id = jd.add_outcome(task_id=TASK_ID, text="查詢清單")
    requirement_id = jd.add_requirement(task_id=TASK_ID, text="確認資料權限")
    task = jd.get_task(task_id=TASK_ID)
    assert outcome_id != UUID(int=10) and requirement_id != UUID(int=11)
    assert tuple(item.id for item in task.outcomes) == (UUID(int=10), outcome_id)
    assert tuple(item.id for item in task.requirements) == (
        UUID(int=11),
        requirement_id,
    )


@pytest.mark.parametrize("kind", ["outcome", "requirement"])
def test_complete_construction_rejects_duplicate_owned_ids(kind: str) -> None:
    entry = {"id": UUID(int=10), "text": "正文"}
    with pytest.raises(DuplicateIdentityError):
        JobDescription.model_validate(
            {
                "id": UUID(int=100),
                "workspace_id": UUID(int=200),
                "tasks": (
                    {
                        "id": TASK_ID,
                        "job_description_id": UUID(int=100),
                        "name": EntryName(value="任務"),
                        f"{kind}s": (entry, entry),
                    },
                ),
            }
        )


@pytest.mark.parametrize("text", ["", "\t\n"])
def test_invalid_owned_text_preserves_the_populated_jd(
    jd: JobDescription, text: str
) -> None:
    before = jd.model_dump()
    with pytest.raises(InvalidTextError):
        jd.update_outcome(task_id=TASK_ID, outcome_id=UUID(int=10), text=text)
    with pytest.raises(InvalidTextError):
        jd.update_requirement(task_id=TASK_ID, requirement_id=UUID(int=11), text=text)
    with pytest.raises(ValidationError):
        jd.update_requirement(
            task_id=TASK_ID, requirement_id=UUID(int=11), text=cast(str, 123)
        )
    assert jd.model_dump() == before


def test_missing_or_wrong_kind_owned_entry_preserves_the_jd(jd: JobDescription) -> None:
    before = jd.model_dump()
    with pytest.raises(TaskOutcomeNotFoundError):
        jd.update_outcome(task_id=TASK_ID, outcome_id=UUID(int=11), text="新文")
    with pytest.raises(TaskRequirementNotFoundError):
        jd.update_requirement(task_id=TASK_ID, requirement_id=UUID(int=10), text="新文")
    task = jd.get_task(task_id=TASK_ID)
    with pytest.raises(ValidationError):
        task.get_outcome(outcome_id=cast(UUID, "10"))
    assert jd.model_dump() == before


def test_reading_task_and_owned_entries_does_not_grant_field_write_access(
    jd: JobDescription,
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    before = jd.model_dump()
    for entry in (task, task.outcomes[0], task.requirements[0]):
        for field, value in entry.model_dump().items():
            with pytest.raises(ValidationError):
                setattr(entry, field, value)
            with pytest.raises(ValidationError):
                delattr(entry, field)
    assert jd.model_dump() == before


def test_edit_selects_requested_entry_and_preserves_position(
    jd: JobDescription,
) -> None:
    outcome_id = jd.add_outcome(task_id=TASK_ID, text="第二成果")
    requirement_id = jd.add_requirement(task_id=TASK_ID, text="第二要求")
    task = jd.get_task(task_id=TASK_ID)
    first_outcome, first_requirement = task.outcomes[0], task.requirements[0]
    jd.update_outcome(task_id=TASK_ID, outcome_id=outcome_id, text="修改第二成果")
    jd.update_requirement(
        task_id=TASK_ID, requirement_id=requirement_id, text="修改第二要求"
    )
    assert task.outcomes[0] is first_outcome and first_outcome.text == "查詢清單"
    assert (
        task.requirements[0] is first_requirement
        and first_requirement.text == "確認資料權限"
    )
    assert tuple(item.text for item in task.outcomes) == ("查詢清單", "修改第二成果")
    assert tuple(item.text for item in task.requirements) == (
        "確認資料權限",
        "修改第二要求",
    )
