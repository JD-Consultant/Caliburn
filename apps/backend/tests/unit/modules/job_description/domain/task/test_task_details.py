"""JD 根更新 Task 基本欄位，保留其他內容及身分。"""

from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import InvalidCompetencyLevelError
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

TASK_ID = UUID(int=1)


def test_updates_all_details_without_replacing_children(jd: JobDescription) -> None:
    task = jd.get_task(task_id=TASK_ID)
    outcome, requirement = task.outcomes[0], task.requirements[0]
    jd.move_task(task_id=TASK_ID, destination_duty_id=UUID(int=2))
    assert (
        jd.update_task(
            task_id=TASK_ID,
            name="  分析需求  ",
            description=" 補充說明 ",
            competency_level=4,
        )
        is True
    )
    assert (task.name.value, task.description, task.competency_level) == (
        "分析需求",
        " 補充說明 ",
        CompetencyLevel(value=4),
    )
    assert task.id == TASK_ID and task.job_description_id == jd.id
    assert task.duty_id == UUID(int=2)
    assert task.outcomes[0] is outcome and task.requirements[0] is requirement
    assert task.knowledge_ids == (UUID(int=20),) and task.skill_ids == (UUID(int=30),)
    assert jd.get_task(task_id=TASK_ID) is task


@pytest.mark.parametrize("invalid_field", ["description", "competency_level"])
def test_late_invalid_detail_preserves_the_populated_jd(
    jd: JobDescription, invalid_field: str
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    before = jd.model_dump()
    outcome = task.outcomes[0]
    with pytest.raises(ValidationError):
        jd.update_task(
            task_id=TASK_ID,
            name="新名稱",
            description=cast(str, 17) if invalid_field == "description" else "新說明",
            competency_level=cast(int, "4")
            if invalid_field == "competency_level"
            else 4,
        )
    assert jd.model_dump() == before
    assert task.outcomes[0] is outcome


def test_identical_details_are_noop_and_optional_details_can_be_cleared(
    jd: JobDescription,
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    assert (
        jd.update_task(
            task_id=TASK_ID,
            name=task.name.value,
            description=None,
            competency_level=None,
        )
        is False
    )
    jd.update_task(
        task_id=TASK_ID,
        name=task.name.value,
        description="原說明",
        competency_level=2,
    )
    jd.update_task(
        task_id=TASK_ID,
        name="新名稱",
        description=None,
        competency_level=2,
    )
    assert task.description is None and task.competency_level == CompetencyLevel(
        value=2
    )


@pytest.mark.parametrize("level", [0, 7, True, "4", 4.0])
def test_invalid_level_preserves_all_task_details(
    jd: JobDescription, level: object
) -> None:
    """級別範圍或型別錯誤時，名稱與說明也不留下部分修改。"""
    before = jd.model_dump()
    error = InvalidCompetencyLevelError if type(level) is int else ValidationError

    with pytest.raises(error):
        jd.update_task(
            task_id=TASK_ID,
            name="新名稱",
            description="新說明",
            competency_level=cast(int, level),
        )

    assert jd.model_dump() == before
