"""單根前置版本限制；真正鎖與持久性另以 PostgreSQL 驗證。"""

from uuid import uuid7

import pytest

from caliburn.modules.job_description.application.duties import add_duty
from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


def test_append_rejects_stale_jd_version_before_applying_content() -> None:
    root = JobDescription(id=uuid7(), workspace_id=uuid7())
    unit = RecordingUnitOfWork(root, version=2)

    with pytest.raises(JobDescriptionConcurrencyError):
        add_duty(
            workspace_id=root.workspace_id,
            job_description_id=root.id,
            expected_version=1,
            name="過期新增",
            uow_factory=lambda: unit,
        )

    assert root.duties == ()
    assert not unit.committed
