"""Task 內容輸入拒絕不可儲存文字，UUID 與正文不隱式轉型。"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddOutcomeInput,
    AddRequirementInput,
    DeleteOutcomeInput,
    UpdateOutcomeInput,
)


@pytest.mark.parametrize("change_type", [AddOutcomeInput, AddRequirementInput])
@pytest.mark.parametrize("value", ["含\x00NUL", "孤立\ud800"])
def test_task_text_rejects_unstorable_characters(
    change_type: type[AddOutcomeInput | AddRequirementInput], value: str
) -> None:
    """字串不能落地為 PostgreSQL Text 時，在進入用例前拒絕。"""
    with pytest.raises(InvalidJobDescriptionInputError):
        change_type(text=value)


@pytest.mark.parametrize("value", [b"outcome", None])
def test_task_text_rejects_implicit_conversion(value: object) -> None:
    with pytest.raises(ValidationError):
        AddOutcomeInput.model_validate({"text": value})


@pytest.mark.parametrize("change_type", [UpdateOutcomeInput, DeleteOutcomeInput])
def test_existing_content_requires_typed_identity(
    change_type: type[UpdateOutcomeInput | DeleteOutcomeInput],
) -> None:
    """更新與刪除只能接受已解析的目標 UUID。"""
    values: dict[str, object] = {"id": str(UUID(int=3))}
    if change_type is UpdateOutcomeInput:
        values["text"] = "正文"
    with pytest.raises(ValidationError):
        change_type.model_validate(values)
