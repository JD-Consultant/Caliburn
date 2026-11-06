"""單項新增入口的型別與可儲存文字驗證先於開交易。"""

from collections.abc import Callable
from typing import Never
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.duties import add_duty
from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.knowledge import (
    add_knowledge,
)
from caliburn.modules.job_description.application.skills import add_skill

JOB_DESCRIPTION_ID = UUID("019286c0-0000-7000-8000-000000000001")


def unexpected_transaction() -> Never:
    raise AssertionError("無效輸入不應取得交易")


TEXT_CASES: tuple[tuple[str, Callable[[str], object]], ...] = (
    (
        "knowledge-name",
        lambda value: add_knowledge(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name=value,
            uow_factory=unexpected_transaction,
        ),
    ),
    (
        "knowledge-description",
        lambda value: add_knowledge(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="知識",
            description=value,
            uow_factory=unexpected_transaction,
        ),
    ),
    (
        "skill-name",
        lambda value: add_skill(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name=value,
            uow_factory=unexpected_transaction,
        ),
    ),
    (
        "skill-description",
        lambda value: add_skill(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="技能",
            description=value,
            uow_factory=unexpected_transaction,
        ),
    ),
    (
        "duty-name",
        lambda value: add_duty(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name=value,
            uow_factory=unexpected_transaction,
        ),
    ),
    (
        "duty-scope",
        lambda value: add_duty(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="職責",
            scope=value,
            uow_factory=unexpected_transaction,
        ),
    ),
)


@pytest.mark.parametrize("value", ["含\x00NUL", "孤立\ud800"])
@pytest.mark.parametrize(
    "create", [pytest.param(create, id=name) for name, create in TEXT_CASES]
)
def test_unrepresentable_text_is_rejected_before_opening_a_transaction(
    create: Callable[[str], object], value: str
) -> None:
    """三入口的名稱與補充文字共用可表示性檢查，不取得任何 UoW。"""
    with pytest.raises(InvalidJobDescriptionInputError):
        create(value)


def test_standalone_inputs_do_not_coerce_ids_names_or_optional_text() -> None:
    """代表錯誤型別在各公開入口被拒絕，不悄悄轉 UUID 或文字。"""
    with pytest.raises(ValidationError):
        add_knowledge(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=str(JOB_DESCRIPTION_ID),  # type: ignore[arg-type]
            name="知識",
            uow_factory=unexpected_transaction,
        )
    with pytest.raises(ValidationError):
        add_skill(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name=b"skill",  # type: ignore[arg-type]
            uow_factory=unexpected_transaction,
        )
    with pytest.raises(ValidationError):
        add_duty(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=JOB_DESCRIPTION_ID,
            name="職責",
            scope=123,  # type: ignore[arg-type]
            uow_factory=unexpected_transaction,
        )
