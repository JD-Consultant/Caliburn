"""共同入口的版本與結果協調；鎖及持久性另由同場景 PG 測試驗證。"""

from uuid import uuid7

import pytest

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionNotFoundError,
)
from tests.integration.content_scenarios import (
    CASES,
    JD,
    ContentCheck,
    WriteOperation,
    complete_root,
)
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


@pytest.mark.parametrize(
    "operation", [pytest.param(operation, id=name) for name, operation, _ in CASES]
)
def test_every_existing_jd_write_rejects_the_original_stale_version(
    operation: WriteOperation,
) -> None:
    root = complete_root()
    original = root.model_dump()
    unit = RecordingUnitOfWork(root)
    with pytest.raises(JobDescriptionConcurrencyError):
        operation(unit, 3, root.workspace_id)
    assert root.model_dump() == original
    assert not unit.committed


@pytest.mark.parametrize(
    "operation, check",
    [pytest.param(operation, check, id=name) for name, operation, check in CASES],
)
def test_every_content_operation_returns_the_complete_committed_result(
    operation: WriteOperation, check: ContentCheck
) -> None:
    root = complete_root()
    unit = RecordingUnitOfWork(root)
    result = operation(unit, 4, root.workspace_id)
    assert check(result)
    assert result.job_description_id == JD
    assert result.version == unit.job_descriptions.saved
    assert unit.committed and unit.closed


@pytest.mark.parametrize(
    "operation", [pytest.param(operation, id=name) for name, operation, _ in CASES]
)
def test_every_content_operation_rejects_another_workspace_before_mutation(
    operation: WriteOperation,
) -> None:
    root = complete_root()
    original = root.model_dump()
    unit = RecordingUnitOfWork(root)
    with pytest.raises(JobDescriptionNotFoundError):
        operation(unit, 4, uuid7())
    assert root.model_dump() == original
    assert unit.job_descriptions.saved is None
    assert not unit.committed
