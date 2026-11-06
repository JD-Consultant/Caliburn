"""同次內容意圖的核對與移動伴隨職責範圍修改。"""

import pytest

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.tasks.inputs import UpdateTaskInput
from caliburn.modules.job_description.application.tasks.lifecycle import update_task
from tests.integration.content_scenarios import D1, D2, JD, T1, complete_root
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


def test_move_can_update_both_duty_scopes_in_one_save() -> None:
    root = complete_root()
    unit = RecordingUnitOfWork(root)
    input = UpdateTaskInput.model_validate(
        {
            "job_description_id": JD,
            "task_id": T1,
            "expected_version": 4,
            "placement": {"destination_duty_id": D2},
            "duty_scopes": (
                {"duty_id": D1, "scope": "移出後範圍"},
                {"duty_id": D2, "scope": "移入後範圍"},
            ),
        }
    )
    result = update_task(
        workspace_id=root.workspace_id, input=input, uow_factory=lambda: unit
    )
    assert root.get_task(task_id=T1).duty_id == D2
    assert root.get_duty(duty_id=D1).scope == "移出後範圍"
    assert root.get_duty(duty_id=D2).scope == "移入後範圍"
    assert result.version == 5
    assert unit.committed


def test_duty_scope_companion_requires_actual_cross_duty_move() -> None:
    root = complete_root()
    unit = RecordingUnitOfWork(root)
    input = UpdateTaskInput.model_validate(
        {
            "job_description_id": JD,
            "task_id": T1,
            "expected_version": 4,
            "placement": {"destination_duty_id": D1},
            "duty_scopes": ({"duty_id": D1, "scope": "不可套用"},),
        }
    )
    with pytest.raises(InvalidJobDescriptionInputError):
        update_task(
            workspace_id=root.workspace_id, input=input, uow_factory=lambda: unit
        )
    assert not unit.committed
