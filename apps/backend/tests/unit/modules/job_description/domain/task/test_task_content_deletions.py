"""JD 根移除指定 Task 內部記載，不影響其餘內容。"""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import (
    TaskOutcomeNotFoundError,
    TaskRequirementNotFoundError,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

TASK_ID = UUID(int=1)


@pytest.mark.parametrize("kind", ["outcome", "requirement"])
def test_remove_middle_content_preserves_other_entities_and_order(
    jd: JobDescription, kind: str
) -> None:
    task = jd.get_task(task_id=TASK_ID)
    middle_outcome_id = jd.add_outcome(task_id=TASK_ID, text="第二成果")
    jd.add_outcome(task_id=TASK_ID, text="第三成果")
    middle_requirement_id = jd.add_requirement(task_id=TASK_ID, text="第二要求")
    jd.add_requirement(task_id=TASK_ID, text="第三要求")
    before = jd.model_dump()
    first_outcome, last_outcome = task.outcomes[0], task.outcomes[-1]
    first_requirement, last_requirement = task.requirements[0], task.requirements[-1]
    expected = task.model_dump()
    if kind == "outcome":
        remove_outcome: Callable[..., object] = jd.remove_outcome
        assert remove_outcome(task_id=TASK_ID, outcome_id=middle_outcome_id) is None
        expected["outcomes"] = (expected["outcomes"][0], expected["outcomes"][2])
    else:
        remove_requirement: Callable[..., object] = jd.remove_requirement
        assert (
            remove_requirement(task_id=TASK_ID, requirement_id=middle_requirement_id)
            is None
        )
        expected["requirements"] = (
            expected["requirements"][0],
            expected["requirements"][2],
        )
    assert task.model_dump() == expected
    assert jd.model_dump() == before | {"tasks": (expected,)}
    assert task.outcomes[0] is first_outcome and task.outcomes[-1] is last_outcome
    assert (
        task.requirements[0] is first_requirement
        and task.requirements[-1] is last_requirement
    )


def test_remove_last_requirement_keeps_other_content(jd: JobDescription) -> None:
    task = jd.get_task(task_id=TASK_ID)
    before = task.model_dump()
    remove_requirement: Callable[..., object] = jd.remove_requirement
    assert remove_requirement(task_id=TASK_ID, requirement_id=UUID(int=11)) is None
    assert task.model_dump() == before | {"requirements": ()}


def test_missing_and_invalid_removal_preserve_entire_jd(jd: JobDescription) -> None:
    before = jd.model_dump()
    with pytest.raises(TaskOutcomeNotFoundError):
        jd.remove_outcome(task_id=TASK_ID, outcome_id=UUID(int=11))
    with pytest.raises(TaskRequirementNotFoundError):
        jd.remove_requirement(task_id=TASK_ID, requirement_id=UUID(int=10))
    with pytest.raises(ValidationError):
        jd.remove_outcome(task_id=TASK_ID, outcome_id=cast(UUID, "10"))
    assert jd.model_dump() == before
