"""Task 相對排列純政策及 JD 根分類行為。"""

from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import InvalidTaskOrderError
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.rules.task_placement import (
    plan_task_placement,
)


def test_same_group_move_preserves_other_members_relative_order() -> None:
    first, second, third = (UUID(int=i) for i in (1, 2, 3))
    placement = plan_task_placement(
        task_id=third,
        destination_task_ids=(first, second, third),
        before_id=second,
    )
    assert placement.task_ids == (first, third, second)
    assert placement.changed is True


@pytest.mark.parametrize("anchor", [UUID(int=1), UUID(int=999)])
def test_self_or_foreign_anchor_is_rejected(anchor: UUID) -> None:
    with pytest.raises(InvalidTaskOrderError):
        plan_task_placement(
            task_id=UUID(int=1),
            destination_task_ids=(UUID(int=2), UUID(int=3)),
            before_id=anchor,
        )


@pytest.mark.parametrize(
    ("destination", "anchor", "expected", "changed"),
    [
        ((2, 3), 3, (2, 1, 3), True),
        ((2, 3), None, (2, 3, 1), True),
        ((), None, (1,), True),
        ((1, 2, 3), 2, (1, 2, 3), False),
        ((2, 3, 1), None, (2, 3, 1), False),
        ((1, 2, 3), None, (2, 3, 1), True),
    ],
)
def test_cross_group_insertion_and_effective_noop(
    destination: tuple[int, ...],
    anchor: int | None,
    expected: tuple[int, ...],
    changed: bool,
) -> None:
    placement = plan_task_placement(
        task_id=UUID(int=1),
        destination_task_ids=tuple(UUID(int=i) for i in destination),
        before_id=UUID(int=anchor) if anchor is not None else None,
    )
    assert placement.task_ids == tuple(UUID(int=i) for i in expected)
    assert placement.changed is changed


def test_reclassifying_preserves_identity_content_and_owned_entities(
    jd: JobDescription,
) -> None:
    duty_id = jd.add_duty(name="第二職責")
    task = jd.get_task(task_id=UUID(int=1))
    original = task.model_dump()
    outcome, requirement = task.outcomes[0], task.requirements[0]
    assert jd.move_task(task_id=task.id, destination_duty_id=duty_id) is True
    assert task.model_dump() == {**original, "duty_id": duty_id}
    assert jd.move_task(task_id=task.id, destination_duty_id=duty_id) is False
    assert jd.move_task(task_id=task.id, destination_duty_id=None) is True
    assert task.model_dump() == {**original, "duty_id": None}
    assert task.outcomes[0] is outcome and task.requirements[0] is requirement
    before = jd.model_dump()
    with pytest.raises(ValidationError):
        jd.move_task(task_id=task.id, destination_duty_id=cast(UUID, "3"))
    assert jd.model_dump() == before


def test_move_across_groups_uses_destination_order_and_preserves_other_groups(
    jd: JobDescription,
) -> None:
    unclassified_id = jd.add_task(name="任務3")
    first_classified_id = jd.add_task(name="任務4", duty_id=UUID(int=2))
    last_classified_id = jd.add_task(name="任務5", duty_id=UUID(int=2))
    first = jd.get_task(task_id=UUID(int=1))
    assert (
        jd.move_task(
            task_id=first.id,
            destination_duty_id=UUID(int=2),
            before_id=last_classified_id,
        )
        is True
    )
    assert tuple(task.id for task in jd.tasks if task.duty_id is None) == (
        unclassified_id,
    )
    assert tuple(task.id for task in jd.tasks if task.duty_id == UUID(int=2)) == (
        first_classified_id,
        first.id,
        last_classified_id,
    )
    assert jd.get_task(task_id=first.id) is first
    before = jd.model_dump()
    with pytest.raises(InvalidTaskOrderError):
        jd.move_task(
            task_id=first.id, destination_duty_id=None, before_id=first_classified_id
        )
    assert jd.model_dump() == before
    assert jd.move_task(task_id=first.id, destination_duty_id=None) is True
    assert tuple(task.id for task in jd.tasks if task.duty_id is None) == (
        unclassified_id,
        first.id,
    )
