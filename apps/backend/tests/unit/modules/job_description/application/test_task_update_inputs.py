"""Task 局部修改的省略、清空與入口形狀契約。"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.tasks.inputs import UpdateTaskInput


def test_empty_patch_is_rejected() -> None:
    with pytest.raises(ValidationError):
        UpdateTaskInput(
            job_description_id=UUID(int=1), task_id=UUID(int=2), expected_version=1
        )


def test_omitted_and_explicit_null_fields_remain_distinguishable() -> None:
    patch = UpdateTaskInput(
        job_description_id=UUID(int=1),
        task_id=UUID(int=2),
        expected_version=1,
        description=None,
    )
    assert patch.model_fields_set == {
        "job_description_id",
        "task_id",
        "expected_version",
        "description",
    }
    assert patch.description is None
    with pytest.raises(ValidationError):
        UpdateTaskInput(
            job_description_id=UUID(int=1),
            task_id=UUID(int=2),
            expected_version=1,
            name=None,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_description_id", str(UUID(int=1))),
        ("task_id", str(UUID(int=2))),
        ("expected_version", True),
        ("expected_version", 0),
        ("expected_version", -1),
        ("expected_version", "1"),
        ("competency_level", True),
        ("competency_level", 1.5),
        ("competency_level", "3"),
        ("name", 17),
        ("description", 17),
        ("duty_id", UUID(int=3)),
        ("position", 0),
        ("version", 1),
        ("outcomes", ()),
        ("name_key", "任務"),
        ("unknown", "值"),
    ],
)
def test_update_input_rejects_wrong_types_and_readonly_or_unknown_fields(
    field: str, value: object
) -> None:
    raw: dict[str, object] = {
        "job_description_id": UUID(int=1),
        "task_id": UUID(int=2),
        "expected_version": 1,
        "description": "補充",
    }
    raw[field] = value
    with pytest.raises(ValidationError):
        UpdateTaskInput.model_validate(raw)


def test_unstorable_text_is_rejected_at_the_input_boundary() -> None:
    with pytest.raises(InvalidJobDescriptionInputError):
        UpdateTaskInput(
            job_description_id=UUID(int=1),
            task_id=UUID(int=2),
            expected_version=1,
            name="含\x00NUL",
        )
    with pytest.raises(InvalidJobDescriptionInputError):
        UpdateTaskInput(
            job_description_id=UUID(int=1),
            task_id=UUID(int=2),
            expected_version=1,
            description="孤立\ud800",
        )
