"""Pure task rules apply without relying on an HTTP validator or live database."""

from uuid import uuid4

import pytest

from caliburn.features.job_description.task_changes import apply_task_edit, order_tasks
from caliburn.features.job_description.tasks import (
    CreateTask,
    DetailKind,
    InvalidTaskChangeError,
    MoveTask,
    ReviseTask,
    SetTaskField,
    TaskDetail,
    TaskField,
    TaskTargetNotFoundError,
    WorkTask,
)


@pytest.mark.parametrize("text", ["", "\n\t", "\u3000", "bad\x00"])
def test_creation_rejects_invalid_text_without_http(text: str) -> None:
    with pytest.raises(InvalidTaskChangeError):
        CreateTask(None, text, None, (), ())
    with pytest.raises(InvalidTaskChangeError):
        CreateTask(None, "task", None, (text,), ())


def test_invalid_final_content_does_not_mutate_the_input() -> None:
    task = WorkTask(uuid4(), uuid4(), None, "盤點", None, ())
    with pytest.raises(InvalidTaskChangeError):
        apply_task_edit(
            (task,), (), ReviseTask(task.task_id, (SetTaskField(TaskField.TITLE, None),))
        )
    assert task.title == "盤點"
    with pytest.raises(InvalidTaskChangeError):
        ReviseTask(
            task.task_id, (SetTaskField(TaskField.TITLE, "甲"), SetTaskField(TaskField.TITLE, "乙"))
        )


def test_move_noop_preserves_content_and_cross_group_self_is_rejected() -> None:
    area_id = uuid4()
    task = WorkTask(
        uuid4(), uuid4(), None, "盤點", None, (TaskDetail(uuid4(), DetailKind.OUTCOME, "清單"),)
    )
    for before in (None, task.task_id):
        changed, content = apply_task_edit(
            (task,), (area_id,), MoveTask(task.task_id, None, before)
        )
        assert changed == (task,)
        assert content is None
    with pytest.raises(InvalidTaskChangeError):
        apply_task_edit((task,), (area_id,), MoveTask(task.task_id, area_id, task.task_id))
    # A missing group must not silently remove a task when normalizing order.
    with pytest.raises(TaskTargetNotFoundError):
        order_tasks(
            (WorkTask(task.task_id, task.content_revision_id, area_id, "盤點", None, ()),), ()
        )
