"""記載用例在開交易前拒絕錯型別、不可儲存文字及不完整 patch。"""

from collections.abc import Callable
from typing import NoReturn
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.collaborations import (
    UpdateCollaborationInput,
    add_collaboration,
    delete_collaboration,
)
from caliburn.modules.job_description.application.conditions import (
    UpdateConditionInput,
    add_condition,
    delete_condition,
)
from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind


def _unopened() -> NoReturn:
    raise AssertionError("無效輸入不得開啟交易")


@pytest.mark.parametrize(
    "operation, arguments",
    [
        (add_collaboration, {"collaborator_name": None}),
        (add_collaboration, {"collaborator_name": b"bytes"}),
        (add_collaboration, {"collaborator_name": "顧問", "scope": 1}),
        (add_condition, {"kind": "qualification", "text": "條件"}),
        (add_condition, {"kind": ConditionKind.QUALIFICATION, "text": None}),
        (delete_condition, {"condition_id": UUID(int=2), "expected_version": 0}),
        (
            delete_collaboration,
            {"collaboration_id": UUID(int=2), "expected_version": 1.0},
        ),
    ],
)
def test_invalid_record_arguments_reject_before_transaction(
    operation: Callable[..., object], arguments: dict[str, object]
) -> None:
    arguments = {"expected_version": 1, **arguments}
    with pytest.raises(ValidationError):
        operation(
            workspace_id=UUID(int=2),
            job_description_id=UUID(int=1),
            uow_factory=_unopened,
            **arguments,
        )


@pytest.mark.parametrize("text", ["bad\x00", "bad\ud800"])
def test_unstorable_record_text_rejects_before_transaction(text: str) -> None:
    with pytest.raises(InvalidJobDescriptionInputError):
        add_condition(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=UUID(int=1),
            kind=ConditionKind.QUALIFICATION,
            text=text,
            uow_factory=_unopened,
        )
    with pytest.raises(InvalidJobDescriptionInputError):
        add_collaboration(
            workspace_id=UUID(int=2),
            expected_version=1,
            job_description_id=UUID(int=1),
            collaborator_name=text,
            uow_factory=_unopened,
        )


@pytest.mark.parametrize(
    "patch", [{}, {"collaborator_name": None}, {"scope": 12}, {"extra": "bad"}]
)
def test_collaboration_patch_requires_at_least_one_legal_explicit_field(
    patch: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        UpdateCollaborationInput.model_validate(
            {
                "job_description_id": UUID(int=1),
                "collaboration_id": UUID(int=2),
                "expected_version": 1,
                **patch,
            }
        )


@pytest.mark.parametrize(
    "patch",
    [
        {},
        {"text": None},
        {"kind": "unknown"},
        {"placement": None},
        {"placement": {"before_id": "bad"}},
        {"text": "條件", "expected_version": True},
    ],
)
def test_condition_patch_rejects_invalid_changes(patch: dict[str, object]) -> None:
    """條件複合輸入保留分類、位置與版本的型別邊界。"""
    with pytest.raises(ValidationError):
        UpdateConditionInput.model_validate(
            {
                "job_description_id": UUID(int=1),
                "condition_id": UUID(int=2),
                "expected_version": 1,
                **patch,
            }
        )
