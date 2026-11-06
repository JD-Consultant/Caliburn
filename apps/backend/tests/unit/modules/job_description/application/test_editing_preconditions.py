"""編修前置由持有版本與修改意圖的物件驗證。"""

from uuid import UUID

import pytest

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
    JobDescriptionConcurrencyError,
)
from caliburn.modules.job_description.application.persistence import (
    LoadedJobDescription,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    DeleteOutcomeInput,
    UpdateOutcomeInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


def test_loaded_version_accepts_current_and_rejects_stale_before_editing() -> None:
    """核版只判保存前置，不改動聚合內容。"""
    job_description = JobDescription(id=UUID(int=1), workspace_id=UUID(int=2))
    loaded = LoadedJobDescription(job_description, version=4)
    loaded.require_version(expected_version=4)
    with pytest.raises(JobDescriptionConcurrencyError):
        loaded.require_version(expected_version=3)
    assert job_description.tasks == ()


def test_task_input_rejects_contradictory_changes() -> None:
    """同一成果不能在同次修改內同時更新與刪除。"""
    task_input = UpdateTaskInput(
        job_description_id=UUID(int=1),
        task_id=UUID(int=2),
        expected_version=4,
        changes=(
            UpdateOutcomeInput(id=UUID(int=3), text="修改成果"),
            DeleteOutcomeInput(id=UUID(int=3)),
        ),
    )
    with pytest.raises(InvalidJobDescriptionInputError):
        task_input.validate_changes()
