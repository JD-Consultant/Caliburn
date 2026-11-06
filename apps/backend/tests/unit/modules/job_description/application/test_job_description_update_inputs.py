"""JD 基本資料修改的欄位出現、型別與可儲存文字契約。"""

from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
)


def test_empty_patch_is_rejected() -> None:
    """只有身分與版本不構成合法修改要求。"""
    with pytest.raises(ValidationError):
        UpdateJobDescriptionInput(job_description_id=UUID(int=1), expected_version=1)


@pytest.mark.parametrize(
    "field",
    [
        "job_title",
        "organization_unit",
        "reports_to",
        "purpose",
        "baseline_competency_level",
    ],
)
def test_every_detail_can_be_cleared_without_supplying_other_fields(field: str) -> None:
    """五欄皆可明確清空，且保留它與省略欄位的區別。"""
    patch = UpdateJobDescriptionInput.model_validate(
        {"job_description_id": UUID(int=1), "expected_version": 1, field: None}
    )
    assert patch.model_fields_set == {"job_description_id", "expected_version", field}
    assert getattr(patch, field) is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("job_description_id", str(UUID(int=1))),
        ("expected_version", True),
        ("expected_version", 0),
        ("expected_version", -1),
        ("expected_version", "1"),
        ("baseline_competency_level", True),
        ("baseline_competency_level", 3.0),
        ("baseline_competency_level", "3"),
        ("job_title", 17),
        ("organization_unit", 17),
        ("reports_to", 17),
        ("purpose", 17),
        ("id", UUID(int=2)),
        ("workspace_id", UUID(int=2)),
        ("version", 1),
        ("collaborations", ()),
        ("conditions", ()),
        ("unknown", "值"),
    ],
)
def test_wrong_types_readonly_and_unknown_fields_are_rejected(
    field: str, value: object
) -> None:
    """外部不能用型別轉換或額外欄位繞過修改範圍。"""
    raw: dict[str, object] = {
        "job_description_id": UUID(int=1),
        "expected_version": 1,
        "purpose": "補充",
    }
    raw[field] = value
    with pytest.raises(ValidationError):
        UpdateJobDescriptionInput.model_validate(raw)


@pytest.mark.parametrize(
    "field", ["job_title", "organization_unit", "reports_to", "purpose"]
)
@pytest.mark.parametrize("value", ["含\x00NUL", "孤立\ud800"])
def test_unstorable_text_is_rejected_before_persistence(field: str, value: str) -> None:
    """四個文字入口拒絕 PostgreSQL 不可儲存的原始文字。"""
    with pytest.raises(InvalidJobDescriptionInputError):
        UpdateJobDescriptionInput.model_validate(
            {"job_description_id": UUID(int=1), "expected_version": 1, field: value}
        )
