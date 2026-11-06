"""Task 公開輸入在 Application 邊界拒絕不可儲存的文字。"""

from collections.abc import Callable
from uuid import UUID

import pytest

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    NewDefinitionInput,
)

JOB_DESCRIPTION_ID = UUID("019286c0-0000-7000-8000-000000000001")


INPUT_CASES: tuple[tuple[str, Callable[[str], AddTaskInput]], ...] = (
    (
        "task-name",
        lambda bad_text: AddTaskInput(
            expected_version=1, job_description_id=JOB_DESCRIPTION_ID, name=bad_text
        ),
    ),
    (
        "task-description",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            description=bad_text,
        ),
    ),
    (
        "outcome",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            outcomes=("合法O", bad_text),
        ),
    ),
    (
        "requirement",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            requirements=("合法P", bad_text),
        ),
    ),
    (
        "knowledge-name",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            knowledge=(NewDefinitionInput(name=bad_text),),
        ),
    ),
    (
        "knowledge-description",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            knowledge=(NewDefinitionInput(name="知識", description=bad_text),),
        ),
    ),
    (
        "skill-name",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            skills=(NewDefinitionInput(name=bad_text),),
        ),
    ),
    (
        "skill-description",
        lambda bad_text: AddTaskInput(
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="任務",
            skills=(NewDefinitionInput(name="技能", description=bad_text),),
        ),
    ),
)


@pytest.mark.parametrize(
    "bad_text",
    [
        pytest.param("含\x00NUL", id="nul"),
        pytest.param("孤立\ud800", id="surrogate"),
    ],
)
@pytest.mark.parametrize(
    "make_input",
    [pytest.param(make_input, id=case_name) for case_name, make_input in INPUT_CASES],
)
def test_unrepresentable_text_is_rejected_by_public_input(
    make_input: Callable[[str], AddTaskInput], bad_text: str
) -> None:
    """Task 與新 K/S 的八個文字位置都拒絕 NUL 與孤立 surrogate。"""
    with pytest.raises(InvalidJobDescriptionInputError):
        make_input(bad_text)
