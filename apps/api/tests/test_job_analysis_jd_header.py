"""JdHeader 值物件（ADR 0052 決定 8–12、ADR 0053 決定 2）。"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.job_analysis.domain import JdHeader


def test_an_empty_header_is_valid_because_every_field_is_optional() -> None:
    header = JdHeader()

    assert header.competency_name is None
    assert header.occupation_category_name is None
    assert header.occupation_name is None
    assert header.occupation_code is None
    assert header.industry_name is None
    assert header.industry_code is None
    assert header.work_description is None
    assert header.competency_level is None
    assert header.notes is None
    assert header.is_empty is True


def test_a_filled_header_keeps_every_official_field() -> None:
    header = JdHeader(
        competency_name="資訊安全維運人員",
        occupation_category_name="資訊技術",
        occupation_name="資訊安全分析師",
        occupation_code="2529",
        industry_name="電腦程式設計、諮詢及相關服務業",
        industry_code="6201",
        work_description="維運企業資訊安全設備並處理資安事件。",
        competency_level=4,
        notes="本文件為客製職務說明書。",
    )

    assert header.competency_name == "資訊安全維運人員"
    assert header.competency_level == 4
    assert header.is_empty is False


def test_the_header_carries_no_icap_assigned_code_field() -> None:
    """ADR 0052 決定 8：代碼由 iCAP 配發，不開欄位、不生成。"""

    fields = set(JdHeader.model_fields)

    assert "competency_code" not in fields
    assert "occupation_category_code" not in fields
    assert not {name for name in fields if name.endswith("_code")} - {
        "occupation_code",
        "industry_code",
    }


@pytest.mark.parametrize("level", [1, 6])
def test_competency_level_accepts_the_official_range(level: int) -> None:
    assert JdHeader(competency_level=level).competency_level == level


@pytest.mark.parametrize("level", [0, 7, -1])
def test_competency_level_rejects_values_outside_one_to_six(level: int) -> None:
    with pytest.raises(ValidationError):
        JdHeader(competency_level=level)


@pytest.mark.parametrize(
    "field",
    [
        "competency_name",
        "occupation_category_name",
        "occupation_name",
        "occupation_code",
        "industry_name",
        "industry_code",
        "work_description",
        "notes",
    ],
)
def test_blank_text_is_rejected_so_callers_must_send_null(field: str) -> None:
    """空字串不是「填了」；mapper 要先 trim 成 null，半成品不進 domain。"""

    with pytest.raises(ValidationError):
        JdHeader(**{field: "   "})
    with pytest.raises(ValidationError):
        JdHeader(**{field: ""})


def test_the_header_is_frozen_and_closed() -> None:
    header = JdHeader(competency_name="資訊安全維運人員")

    with pytest.raises(ValidationError):
        header.competency_name = "改掉"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        JdHeader(competency_code="ITE-001")  # type: ignore[call-arg]
