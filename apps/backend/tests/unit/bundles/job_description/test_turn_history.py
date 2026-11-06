"""完成輪 JD 兩端只認已保存字段，不猜目前或上輪版本。"""

from uuid import UUID, uuid4

import pytest

from caliburn.bundles.job_description.turn_history import project_completed_turn
from caliburn.modules.job_description.application.turn_history import (
    JobDescriptionTurnDataError,
    JobDescriptionTurnNotFoundError,
)


def saved_values(turn_id: UUID, jd_id: UUID) -> dict[str, object]:
    return {
        "jd_turn_id": turn_id,
        "jd_id": jd_id,
        "jd_turn_start_version": 3,
        "jd_completed_version": 7,
        "jd_version": 99,
        "jd_manual_before_version": 1,
    }


def test_projects_fixed_versions_without_using_other_baselines() -> None:
    workspace_id, turn_id, jd_id = uuid4(), uuid4(), uuid4()
    result = project_completed_turn(
        workspace_id=workspace_id, turn_id=turn_id, values=saved_values(turn_id, jd_id)
    )
    assert result.workspace_id == workspace_id
    assert result.turn_id == turn_id
    assert result.job_description_id == jd_id
    assert (result.before_version, result.after_version) == (3, 7)


def test_turn_without_writes_keeps_equal_fixed_versions() -> None:
    workspace_id, turn_id, jd_id = uuid4(), uuid4(), uuid4()
    values = saved_values(turn_id, jd_id)
    values["jd_completed_version"] = 3
    result = project_completed_turn(
        workspace_id=workspace_id, turn_id=turn_id, values=values
    )
    assert (result.before_version, result.after_version) == (3, 3)


def test_completed_seen_version_may_precede_start_after_manual_net_zero() -> None:
    turn_id = uuid4()
    values = saved_values(turn_id, uuid4())
    values["jd_completed_version"] = 1
    result = project_completed_turn(
        workspace_id=uuid4(), turn_id=turn_id, values=values
    )
    assert (result.before_version, result.after_version) == (3, 1)


@pytest.mark.parametrize(
    "field",
    ["jd_id", "jd_turn_start_version", "jd_completed_version"],
)
def test_missing_saved_field_is_data_error(field: str) -> None:
    turn_id = uuid4()
    values = saved_values(turn_id, uuid4())
    del values[field]
    with pytest.raises(JobDescriptionTurnDataError):
        project_completed_turn(workspace_id=uuid4(), turn_id=turn_id, values=values)


@pytest.mark.parametrize("marker", [None, uuid4(), "not-a-uuid"])
def test_turn_without_current_jd_participation_is_not_found(marker: object) -> None:
    turn_id = uuid4()
    values = saved_values(turn_id, uuid4())
    if marker is None:
        del values["jd_turn_id"]
    else:
        values["jd_turn_id"] = marker
    with pytest.raises(JobDescriptionTurnNotFoundError):
        project_completed_turn(workspace_id=uuid4(), turn_id=turn_id, values=values)


@pytest.mark.parametrize(
    ("field", "invalid"),
    [
        ("jd_id", None),
        ("jd_id", str(uuid4())),
        ("jd_turn_start_version", True),
        ("jd_turn_start_version", 0),
        ("jd_turn_start_version", "3"),
        ("jd_completed_version", None),
        ("jd_completed_version", 0),
        ("jd_completed_version", 7.0),
        ("jd_completed_version", False),
    ],
)
def test_unprovable_saved_fields_are_not_repaired(field: str, invalid: object) -> None:
    turn_id = uuid4()
    values = saved_values(turn_id, uuid4())
    values[field] = invalid
    with pytest.raises(JobDescriptionTurnDataError):
        project_completed_turn(workspace_id=uuid4(), turn_id=turn_id, values=values)
