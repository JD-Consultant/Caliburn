"""驗證 JD 根的局部修改、身分與失敗效果。"""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.domain.errors import InvalidCompetencyLevelError
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)

JD_ID = UUID(int=1)
WORKSPACE_ID = UUID(int=2)


def test_details_update_applies_one_candidate_preserving_identity() -> None:
    """五欄一起改、同值不變、全部可清空，根身分與原物件持續有效。"""
    jd = JobDescription(id=JD_ID, workspace_id=WORKSPACE_ID)
    reference = jd
    original_hash = hash(jd)
    update_details: Callable[..., bool] = jd.update_details
    candidate = {
        "job_title": "  分析師\n",
        "organization_unit": "",
        "reports_to": " ",
        "purpose": "改善工作",
        "baseline_competency_level": 4,
    }

    assert update_details(**candidate) is True
    assert reference.model_dump() == {
        "id": JD_ID,
        "workspace_id": WORKSPACE_ID,
        "job_title": "  分析師\n",
        "organization_unit": "",
        "reports_to": " ",
        "purpose": "改善工作",
        "baseline_competency_level": {"value": 4},
        "collaborations": (),
        "conditions": (),
        "duties": (),
        "tasks": (),
        "knowledge": (),
        "skills": (),
        "citations": (),
    }
    assert update_details(**candidate) is False
    assert (
        jd.update_details(
            job_title=None,
            organization_unit=None,
            reports_to=None,
            purpose=None,
            baseline_competency_level=None,
        )
        is True
    )
    assert reference.model_dump() == {
        "id": JD_ID,
        "workspace_id": WORKSPACE_ID,
        "job_title": None,
        "organization_unit": None,
        "reports_to": None,
        "purpose": None,
        "baseline_competency_level": None,
        "collaborations": (),
        "conditions": (),
        "duties": (),
        "tasks": (),
        "knowledge": (),
        "skills": (),
        "citations": (),
    }
    assert hash(jd) == original_hash


@pytest.mark.parametrize("invalid_field", ["purpose", "baseline_competency_level"])
def test_late_invalid_detail_preserves_all_existing_fields(invalid_field: str) -> None:
    """後面文字或級別型別無效，也不留下前面欄位的修改。"""
    jd = JobDescription(
        id=JD_ID,
        workspace_id=WORKSPACE_ID,
        job_title="舊職稱",
        organization_unit="舊單位",
        reports_to="舊主管",
        purpose="舊目的",
        baseline_competency_level=CompetencyLevel(value=2),
    )
    before = jd.model_dump()
    update_details: Callable[..., bool] = jd.update_details
    candidate = {
        "job_title": "新職稱",
        "organization_unit": "新單位",
        "reports_to": "新主管",
        "purpose": "新目的",
        "baseline_competency_level": 4,
    }
    candidate[invalid_field] = (
        "4" if invalid_field == "baseline_competency_level" else 123
    )

    with pytest.raises(ValidationError):
        update_details(**candidate)

    assert jd.model_dump() == before


PROFILE_SETTERS: tuple[
    tuple[str, Callable[[JobDescription, str | None], object]], ...
] = (
    ("job_title", lambda jd, value: jd.set_job_title(job_title=value)),
    (
        "organization_unit",
        lambda jd, value: jd.set_organization_unit(organization_unit=value),
    ),
    ("reports_to", lambda jd, value: jd.set_reports_to(reports_to=value)),
    ("purpose", lambda jd, value: jd.set_purpose(purpose=value)),
)


def test_empty_job_description_requires_workspace_ownership() -> None:
    """空 JD 可以尚未填寫內容，但必須明示 Workspace 歸屬。"""
    with pytest.raises(ValidationError):
        JobDescription.model_validate({"id": JD_ID})

    jd = JobDescription(id=JD_ID, workspace_id=WORKSPACE_ID)

    assert jd.id == JD_ID
    assert jd.workspace_id == WORKSPACE_ID
    assert (jd.job_title, jd.organization_unit, jd.reports_to, jd.purpose) == (
        None,
        None,
        None,
        None,
    )
    assert jd.baseline_competency_level is None


@pytest.mark.parametrize(("field", "set_profile"), PROFILE_SETTERS)
def test_profile_edit_updates_the_same_instance(
    field: str, set_profile: Callable[[JobDescription, str | None], object]
) -> None:
    """各基本欄位原地設定及清空，保留其他內容與身分。"""
    jd = JobDescription(
        id=JD_ID,
        workspace_id=WORKSPACE_ID,
        job_title="分析師",
        organization_unit="人資處",
        reports_to="主管",
        purpose="改善工作",
        baseline_competency_level=CompetencyLevel(value=3),
    )
    reference = jd
    before = jd.model_dump()
    original_hash = hash(jd)

    assert set_profile(jd, " 原文\n ") is None
    assert reference.model_dump() == before | {field: " 原文\n "}
    assert set_profile(jd, None) is None
    assert reference.model_dump() == before | {field: None}
    assert hash(jd) == original_hash


@pytest.mark.parametrize(("field", "set_profile"), PROFILE_SETTERS)
def test_invalid_profile_type_preserves_existing_content(
    field: str, set_profile: Callable[[JobDescription, str | None], object]
) -> None:
    """錯誤文字型別不會覆寫已有的基本資料或其他欄位。"""
    jd = JobDescription.model_validate(
        {"id": JD_ID, "workspace_id": WORKSPACE_ID, field: "既有內容"}
    )
    before = jd.model_dump()

    with pytest.raises(ValidationError):
        set_profile(jd, cast(str, 123))

    assert jd.model_dump() == before


def test_baseline_is_set_and_cleared_without_changing_profile() -> None:
    """基準級別原地設定及清空，不改寫基本資料。"""
    jd = JobDescription(id=JD_ID, workspace_id=WORKSPACE_ID, purpose="建立 JD")
    set_level: Callable[..., object] = jd.set_baseline_competency_level
    reference = jd

    assert set_level(competency_level=6) is None
    assert reference.baseline_competency_level == CompetencyLevel(value=6)
    assert set_level(competency_level=None) is None
    assert reference.baseline_competency_level is None
    assert reference.purpose == "建立 JD"


@pytest.mark.parametrize("value", [True, "4", 4.0])
def test_invalid_baseline_type_preserves_existing_level(value: object) -> None:
    """不轉換布林、字串或浮點數；拒絕後原領域值不變。"""
    jd = JobDescription(
        id=JD_ID,
        workspace_id=WORKSPACE_ID,
        baseline_competency_level=CompetencyLevel(value=3),
    )
    before = jd.model_dump()

    with pytest.raises(ValidationError):
        jd.set_baseline_competency_level(competency_level=cast(int, value))

    assert jd.model_dump() == before


@pytest.mark.parametrize("value", [0, 7])
def test_competency_level_rejects_values_outside_domain(value: int) -> None:
    """級別只接受 1–6，不以零表示未填。"""
    with pytest.raises(InvalidCompetencyLevelError):
        CompetencyLevel(value=value)


def test_competency_level_requires_explicit_value() -> None:
    """DP 明示 value，不把裸整數隱式轉成領域物件。"""
    with pytest.raises(ValidationError):
        CompetencyLevel.model_validate(3)


@pytest.mark.parametrize("value", [True, "3", 3.0])
def test_competency_level_rejects_coercible_values(value: object) -> None:
    """級別不把布林、數字字串或浮點數轉成整數。"""
    with pytest.raises(ValidationError):
        CompetencyLevel.model_validate({"value": value})


def test_job_description_fields_require_domain_methods() -> None:
    """外部不可重新賦值或刪除 JD 欄位以繞過領域方法。"""
    jd = JobDescription(id=JD_ID, workspace_id=WORKSPACE_ID, job_title="分析師")
    before = jd.model_dump()

    for field, value in before.items():
        with pytest.raises(ValidationError):
            setattr(jd, field, value)
        with pytest.raises(ValidationError):
            delattr(jd, field)

    assert jd.model_dump() == before


@pytest.mark.parametrize("collection", ["duties", "tasks", "knowledge", "skills"])
def test_empty_job_description_owns_all_internal_collections(
    collection: str,
) -> None:
    """明確空集合是合法完整內容；沒有子根版號。"""
    jd = JobDescription.model_validate(
        {"id": JD_ID, "workspace_id": WORKSPACE_ID, collection: ()}
    )
    assert getattr(jd, collection) == ()
