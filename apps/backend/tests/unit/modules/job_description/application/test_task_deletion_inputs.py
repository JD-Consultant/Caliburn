"""根刪除輸入不可強制轉型，無效版本及身分不得取得交易。"""

from collections.abc import Callable
from typing import Never
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.tasks.lifecycle import delete_task


def unexpected_transaction() -> Never:
    raise AssertionError("無效輸入不應取得交易")


@pytest.mark.parametrize(
    "field,value",
    [
        ("job_description_id", str(UUID(int=1))),
        ("task_id", str(UUID(int=2))),
        ("expected_version", True),
        ("expected_version", 0),
        ("expected_version", -1),
        ("expected_version", "1"),
        ("expected_version", 1.0),
        ("expected_version", None),
    ],
)
def test_delete_task_requires_strict_ids_and_positive_version(
    field: str, value: object
) -> None:
    arguments: dict[str, object] = {
        "workspace_id": UUID(int=4),
        "job_description_id": UUID(int=1),
        "task_id": UUID(int=2),
        "expected_version": 1,
        "uow_factory": unexpected_transaction,
    }
    arguments[field] = value
    remove: Callable[..., object] = delete_task
    with pytest.raises(ValidationError):
        remove(**arguments)
