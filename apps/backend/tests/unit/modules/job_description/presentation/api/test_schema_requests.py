"""PATCH 的省略、清空與公開 schema 必須一致。"""

import pytest
from pydantic import BaseModel, ValidationError

from caliburn.modules.job_description.presentation.api.schemas.content import (
    AddCollaborationRequest,
    UpdateCollaborationRequest,
    UpdateDutyRequest,
    UpdateJobDescriptionRequest,
    UpdateKnowledgeRequest,
    UpdateSkillRequest,
)
from caliburn.modules.job_description.presentation.api.schemas.tasks import (
    UpdateTaskRequest,
)


@pytest.mark.parametrize(
    "model",
    [
        UpdateJobDescriptionRequest,
        UpdateDutyRequest,
        UpdateKnowledgeRequest,
        UpdateSkillRequest,
        UpdateCollaborationRequest,
        UpdateTaskRequest,
    ],
)
def test_patch_requires_content_change_field(model: type[BaseModel]) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"expected_version": 1, "correlation_id": "edit"})
    assert model.model_json_schema()["anyOf"]


@pytest.mark.parametrize(
    "model, field",
    [
        (UpdateDutyRequest, "name"),
        (UpdateKnowledgeRequest, "name"),
        (UpdateSkillRequest, "name"),
        (UpdateCollaborationRequest, "collaborator_name"),
        (UpdateTaskRequest, "name"),
    ],
)
def test_required_name_can_be_omitted_but_not_cleared(
    model: type[BaseModel], field: str
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"expected_version": 1, field: None})
    schema = model.model_json_schema()["properties"][field]
    assert schema["type"] == "string"
    assert "default" not in schema


@pytest.mark.parametrize(
    "model, field",
    [
        (UpdateJobDescriptionRequest, "purpose"),
        (UpdateDutyRequest, "scope"),
        (UpdateKnowledgeRequest, "description"),
        (UpdateSkillRequest, "description"),
        (UpdateCollaborationRequest, "scope"),
        (UpdateTaskRequest, "description"),
    ],
)
def test_nullable_patch_keeps_only_explicit_fields(
    model: type[BaseModel], field: str
) -> None:
    parsed = model.model_validate({"expected_version": 1, field: None})
    assert parsed.model_dump(exclude_unset=True) == {"expected_version": 1, field: None}


@pytest.mark.parametrize(
    "model, field",
    [
        (UpdateJobDescriptionRequest, "baseline_competency_level"),
        (UpdateTaskRequest, "competency_level"),
    ],
)
@pytest.mark.parametrize("value", [True, 0, 7, "1"])
def test_competency_level_has_json_integer_range(
    model: type[BaseModel], field: str, value: object
) -> None:
    with pytest.raises(ValidationError):
        model.model_validate({"expected_version": 1, field: value})


def test_collaborator_name_keeps_domain_unbounded_text_contract() -> None:
    parsed = AddCollaborationRequest.model_validate(
        {"expected_version": 1, "collaborator_name": "協作對象" * 100}
    )
    assert parsed.collaborator_name == "協作對象" * 100
