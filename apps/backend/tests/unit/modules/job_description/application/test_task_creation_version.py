"""新增 Task 亦須具備原 JD 版本，不能以追加繞過並行保護。"""

from uuid import uuid7

import pytest
from pydantic import ValidationError

from caliburn.modules.job_description.application.tasks.inputs import AddTaskInput


def test_task_creation_requires_the_original_jd_version() -> None:
    with pytest.raises(ValidationError):
        AddTaskInput.model_validate({"job_description_id": uuid7(), "name": "任務"})
