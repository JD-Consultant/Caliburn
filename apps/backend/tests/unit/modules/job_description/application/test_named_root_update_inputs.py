"""Duty／K／S 局部修改的明確欄位及輸入邊界。"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.duties import UpdateDutyInput
from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.knowledge import UpdateKnowledgeInput
from caliburn.modules.job_description.application.skills import UpdateSkillInput


def test_knowledge_requires_a_patch_and_rejects_null_name() -> None:
    with pytest.raises(ValidationError):
        UpdateKnowledgeInput(
            job_description_id=UUID(int=1), knowledge_id=UUID(int=2), expected_version=1
        )
    with pytest.raises(ValidationError):
        UpdateKnowledgeInput(
            job_description_id=UUID(int=1),
            knowledge_id=UUID(int=2),
            expected_version=1,
            name=None,
        )
    patch = UpdateKnowledgeInput(
        job_description_id=UUID(int=1),
        knowledge_id=UUID(int=2),
        expected_version=1,
        description=None,
    )
    assert "description" in patch.model_fields_set
    assert "name" not in patch.model_fields_set


@pytest.mark.parametrize(
    ("input_type", "identity", "detail", "wrong_detail"),
    [
        (UpdateKnowledgeInput, "knowledge_id", "description", "scope"),
        (UpdateSkillInput, "skill_id", "description", "scope"),
        (UpdateDutyInput, "duty_id", "scope", "description"),
    ],
)
def test_named_root_inputs_preserve_presence_and_reject_noneditable_shapes(
    input_type: type[UpdateKnowledgeInput]
    | type[UpdateSkillInput]
    | type[UpdateDutyInput],
    identity: str,
    detail: str,
    wrong_detail: str,
) -> None:
    base: dict[str, object] = {
        "job_description_id": UUID(int=1),
        identity: UUID(int=2),
        "expected_version": 1,
    }
    patch = input_type.model_validate(base | {detail: None})
    assert patch.model_fields_set == set(base) | {detail}
    for addition in (
        {},
        {"name": None},
        {"name": 17},
        {detail: 17},
        {detail: None, "position": 0},
        {detail: None, "version": 2},
        {detail: None, "name_key": "x"},
        {detail: None, wrong_detail: "x"},
        {detail: None, "unknown": True},
        {detail: None, "expected_version": True},
        {detail: None, "expected_version": 0},
        {detail: None, identity: str(UUID(int=2))},
    ):
        with pytest.raises(ValidationError):
            input_type.model_validate(base | addition)
    with pytest.raises(InvalidJobDescriptionInputError):
        input_type.model_validate(base | {"name": "含\x00NUL"})
    with pytest.raises(InvalidJobDescriptionInputError):
        input_type.model_validate(base | {detail: "孤立\ud800"})
