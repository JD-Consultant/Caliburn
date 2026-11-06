"""JD 根排序 Task 局部集合；不同集合的次序相互獨立。"""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import (
    InvalidTaskOrderError,
    InvalidTaskReferenceError,
    TaskOutcomeNotFoundError,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

TASK_ID = UUID(int=1)


def test_move_outcome_preserves_entities_other_groups_and_reports_noop(
    jd: JobDescription,
) -> None:
    jd.add_outcome(task_id=TASK_ID, text="第二")
    jd.add_outcome(task_id=TASK_ID, text="第三")
    task = jd.get_task(task_id=TASK_ID)
    first, second, third = task.outcomes
    before = jd.model_dump()
    assert (
        jd.move_outcome(task_id=TASK_ID, outcome_id=third.id, before_id=second.id)
        is True
    )
    assert (
        task.outcomes[0] is first
        and task.outcomes[1] is third
        and task.outcomes[2] is second
    )
    assert task.model_dump() == before["tasks"][0] | {
        "outcomes": (first.model_dump(), third.model_dump(), second.model_dump())
    }
    assert (
        jd.move_outcome(task_id=TASK_ID, outcome_id=third.id, before_id=second.id)
        is False
    )
    assert jd.move_outcome(task_id=TASK_ID, outcome_id=third.id, before_id=None) is True
    assert jd.model_dump() == before


def test_requirement_and_reference_orders_are_independent(jd: JobDescription) -> None:
    task = jd.get_task(task_id=TASK_ID)
    second_requirement_id = jd.add_requirement(task_id=TASK_ID, text="第二")
    jd.link_knowledge(task_id=TASK_ID, knowledge_id=UUID(int=21))
    jd.link_skill(task_id=TASK_ID, skill_id=UUID(int=31))
    before = jd.model_dump()
    assert (
        jd.move_requirement(
            task_id=TASK_ID,
            requirement_id=second_requirement_id,
            before_id=UUID(int=11),
        )
        is True
    )
    assert (
        jd.move_knowledge_reference(
            task_id=TASK_ID, knowledge_id=UUID(int=21), before_id=UUID(int=20)
        )
        is True
    )
    assert (
        jd.move_skill_reference(
            task_id=TASK_ID, skill_id=UUID(int=31), before_id=UUID(int=30)
        )
        is True
    )
    assert tuple(x.id for x in task.requirements) == (
        second_requirement_id,
        UUID(int=11),
    )
    assert task.knowledge_ids == (UUID(int=21), UUID(int=20))
    assert task.skill_ids == (UUID(int=31), UUID(int=30))
    assert task.outcomes[0].model_dump() == before["tasks"][0]["outcomes"][0]
    assert jd.model_dump()["knowledge"] == before["knowledge"]
    assert jd.model_dump()["skills"] == before["skills"]
    assert (
        jd.move_requirement(
            task_id=TASK_ID, requirement_id=UUID(int=11), before_id=None
        )
        is False
    )
    assert (
        jd.move_knowledge_reference(
            task_id=TASK_ID, knowledge_id=UUID(int=20), before_id=None
        )
        is False
    )
    assert (
        jd.move_skill_reference(task_id=TASK_ID, skill_id=UUID(int=30), before_id=None)
        is False
    )


@pytest.mark.parametrize(
    ("move", "identity"),
    [
        (
            lambda jd, anchor: jd.move_outcome(
                task_id=TASK_ID, outcome_id=UUID(int=10), before_id=anchor
            ),
            UUID(int=10),
        ),
        (
            lambda jd, anchor: jd.move_requirement(
                task_id=TASK_ID, requirement_id=UUID(int=11), before_id=anchor
            ),
            UUID(int=11),
        ),
        (
            lambda jd, anchor: jd.move_knowledge_reference(
                task_id=TASK_ID, knowledge_id=UUID(int=20), before_id=anchor
            ),
            UUID(int=20),
        ),
        (
            lambda jd, anchor: jd.move_skill_reference(
                task_id=TASK_ID, skill_id=UUID(int=30), before_id=anchor
            ),
            UUID(int=30),
        ),
    ],
)
def test_invalid_order_preserves_whole_jd(
    jd: JobDescription,
    move: Callable[[JobDescription, UUID | None], bool],
    identity: UUID,
) -> None:
    before = jd.model_dump()
    for anchor in (identity, UUID(int=999)):
        with pytest.raises(InvalidTaskOrderError):
            move(jd, anchor)
    with pytest.raises(ValidationError):
        move(jd, cast(UUID, "invalid"))
    assert jd.model_dump() == before


def test_missing_outcome_or_unlinked_definition_cannot_be_sorted(
    jd: JobDescription,
) -> None:
    before = jd.model_dump()
    with pytest.raises(TaskOutcomeNotFoundError):
        jd.move_outcome(task_id=TASK_ID, outcome_id=UUID(int=999), before_id=None)
    with pytest.raises(InvalidTaskReferenceError):
        jd.move_knowledge_reference(
            task_id=TASK_ID, knowledge_id=UUID(int=21), before_id=None
        )
    with pytest.raises(InvalidTaskReferenceError):
        jd.move_skill_reference(task_id=TASK_ID, skill_id=UUID(int=31), before_id=None)
    assert jd.model_dump() == before
