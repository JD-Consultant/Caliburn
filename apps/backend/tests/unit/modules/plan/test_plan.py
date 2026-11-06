"""透過 Plan 根驗證目前內容、原子變更與同根恢復。"""

from uuid import uuid4

import pytest

from caliburn.modules.plan.domain.errors import (
    BodyEditError,
    InvalidPlanSnapshotError,
    PlanVersionExhaustedError,
)
from caliburn.modules.plan.domain.plan import Plan
from caliburn.modules.plan.domain.snapshot import PlanSnapshot


def test_first_effective_patch_creates_body_and_advances_initial_version() -> None:
    workspace_id = uuid4()
    plan = Plan.create(workspace_id=workspace_id)
    assert (plan.id, plan.workspace_id, plan.version, plan.body) == (
        workspace_id,
        workspace_id,
        1,
        None,
    )

    assert plan.apply_patch("@@\n+## 計畫\n*** End of File") is True
    assert (plan.body, plan.version) == ("## 計畫", 2)


def test_restore_old_content_advances_current_version_and_remains_editable() -> None:
    workspace_id = uuid4()
    plan = Plan(id=workspace_id, version=9, body="本輪最新內容")
    snapshot = PlanSnapshot(workspace_id, 7, "輪前內容")

    assert plan.restore(snapshot) is True
    assert (plan.body, plan.version) == ("輪前內容", 10)
    assert plan.apply_patch("@@\n-輪前內容\n+下輪內容") is True
    assert (plan.body, plan.version) == ("下輪內容", 11)


def test_other_workspace_snapshot_is_rejected_even_for_identical_body() -> None:
    plan = Plan(id=uuid4(), version=3, body="保留")
    snapshot = PlanSnapshot(uuid4(), 2, "保留")

    with pytest.raises(InvalidPlanSnapshotError):
        plan.restore(snapshot)

    assert (plan.body, plan.version) == ("保留", 3)


def test_version_exhaustion_rejects_patch_without_mutating_body() -> None:
    plan = Plan(id=uuid4(), version=9_007_199_254_740_991, body="舊")

    with pytest.raises(PlanVersionExhaustedError):
        plan.apply_patch("@@\n-舊\n+新")

    assert (plan.body, plan.version) == ("舊", 9_007_199_254_740_991)


@pytest.mark.parametrize(
    "body", ["\x00", "\ud800", "x" * 16_001], ids=["nul", "surrogate", "oversized"]
)
def test_rehydration_rejects_unsavable_or_oversized_current_body(body: str) -> None:
    with pytest.raises(ValueError):
        Plan(id=uuid4(), version=1, body=body)


@pytest.mark.parametrize(
    "body", ["\x00", "\ud800", "x" * 16_001], ids=["nul", "surrogate", "oversized"]
)
def test_snapshot_rejects_unsavable_or_oversized_body(body: str) -> None:
    with pytest.raises(ValueError):
        PlanSnapshot(uuid4(), 1, body)


@pytest.mark.parametrize("version", [0, -1, 9_007_199_254_740_992, True])
def test_snapshot_rejects_invalid_content_version(version: int) -> None:
    with pytest.raises(InvalidPlanSnapshotError):
        PlanSnapshot(uuid4(), version, "保存原件")


def test_ineffective_first_patch_preserves_absent_body_and_initial_version() -> None:
    plan = Plan.create(workspace_id=uuid4())

    assert plan.apply_patch("@@\n+\n*** End of File") is False
    assert (plan.body, plan.version) == (None, 1)


def test_clearing_existing_content_keeps_explicit_empty_body() -> None:
    plan = Plan(id=uuid4(), version=4, body="## 計畫\r\n原文\n")

    assert plan.apply_patch("@@\n-## 計畫\n-原文\n*** End of File") is True
    assert (plan.body, plan.version) == ("", 5)
    assert plan.apply_patch("@@\n+\n*** End of File") is False
    assert (plan.body, plan.version) == ("", 5)


def test_whitespace_body_is_kept_exactly_when_appending() -> None:
    plan = Plan(id=uuid4(), version=2, body=" \r\n")

    assert plan.apply_patch("@@\n+保留\n*** End of File") is True
    assert (plan.body, plan.version) == (" \r\n保留\r\n", 3)


def test_failed_second_hunk_does_not_apply_first_hunk_or_advance_version() -> None:
    plan = Plan(id=uuid4(), version=5, body="# 頻率\n每月\n# 其他\n保留\n")

    with pytest.raises(BodyEditError) as caught:
        plan.apply_patch("@@\n # 頻率\n-每月\n+每週\n@@\n-不存在\n+增加")

    assert (caught.value.code, caught.value.hunk_number) == (
        "patch_context_not_found",
        2,
    )
    assert (plan.body, plan.version) == ("# 頻率\n每月\n# 其他\n保留\n", 5)


@pytest.mark.parametrize(
    ("before", "restored"), [("", None), (None, ""), ("內容", None)]
)
def test_restore_preserves_difference_between_absent_and_empty_body(
    before: str | None, restored: str | None
) -> None:
    workspace_id = uuid4()
    plan = Plan(id=workspace_id, version=5, body=before)

    assert plan.restore(PlanSnapshot(workspace_id, 1, restored)) is True
    assert (plan.body, plan.version) == (restored, 6)


@pytest.mark.parametrize("body", [None, "", " \t\r\n", "目前內容"])
def test_restore_same_body_is_noop_at_version_limit(body: str | None) -> None:
    plan = Plan(id=uuid4(), version=9_007_199_254_740_991, body=body)

    assert plan.restore(PlanSnapshot(plan.workspace_id, 1, body)) is False
    assert (plan.body, plan.version) == (body, 9_007_199_254_740_991)


def test_restore_at_version_limit_cannot_change_current_body() -> None:
    plan = Plan(id=uuid4(), version=9_007_199_254_740_991, body="目前內容")

    with pytest.raises(PlanVersionExhaustedError):
        plan.restore(PlanSnapshot(plan.workspace_id, 1, None))

    assert (plan.body, plan.version) == ("目前內容", 9_007_199_254_740_991)


def test_noop_patch_is_allowed_at_version_limit() -> None:
    plan = Plan(id=uuid4(), version=9_007_199_254_740_991, body="a\r\nb\nc")

    assert plan.apply_patch("@@\n-a\n-b\n-c\n+a\n+b\n+c") is False
    assert (plan.body, plan.version) == ("a\r\nb\nc", 9_007_199_254_740_991)


@pytest.mark.parametrize("version", [0, -1, 9_007_199_254_740_992, True])
def test_rehydration_rejects_invalid_content_version(version: int) -> None:
    with pytest.raises(ValueError):
        Plan(id=uuid4(), version=version, body=None)
