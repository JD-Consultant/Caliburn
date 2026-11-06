"""Task 引用修改使用 typed 輸入，拒絕身分與版本強制轉型。"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.tasks.inputs import (
    LinkKnowledgeInput,
    LinkSkillInput,
    UnlinkKnowledgeInput,
    UnlinkSkillInput,
    UpdateTaskInput,
)

type ReferenceChange = (
    LinkKnowledgeInput | LinkSkillInput | UnlinkKnowledgeInput | UnlinkSkillInput
)


@pytest.mark.parametrize(
    "change_type",
    [LinkKnowledgeInput, LinkSkillInput, UnlinkKnowledgeInput, UnlinkSkillInput],
)
def test_reference_changes_reject_string_identity(
    change_type: type[ReferenceChange],
) -> None:
    """Application 收已解析的 UUID，避免把字串當正式身分。"""
    with pytest.raises(ValidationError):
        change_type.model_validate({"id": str(UUID(int=3))})


@pytest.mark.parametrize("version", [0, True, "1"])
def test_reference_patch_requires_strict_positive_version(version: object) -> None:
    """引用與其他 JD 寫入共用相同版本前置條件。"""
    with pytest.raises(ValidationError):
        UpdateTaskInput.model_validate(
            {
                "job_description_id": UUID(int=1),
                "task_id": UUID(int=2),
                "expected_version": version,
                "changes": (UnlinkKnowledgeInput(id=UUID(int=3)),),
            }
        )
