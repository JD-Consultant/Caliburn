"""建立空 JD 的 Application 協調；不代替真資料庫交易驗收。"""

from types import TracebackType
from typing import Literal
from uuid import UUID

import pytest

from caliburn.modules.job_description.application.errors import (
    CommitStatus,
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from tests.unit.modules.job_description.application.recording_uow import (
    RecordingUnitOfWork,
)


def test_creates_complete_empty_job_description_after_commit_and_exit() -> None:
    workspace_id = UUID(int=1)
    unit = RecordingUnitOfWork()

    result = create_job_description(
        workspace_id=workspace_id, correlation_id="create-1", uow_factory=lambda: unit
    )

    current = result
    assert current.job_description_id.version == 7
    assert current.workspace_id == workspace_id
    assert current.version == 1
    assert current.job_title is None
    assert current.tasks == ()
    assert current.duties == ()
    assert current.knowledge == ()
    assert current.skills == ()
    assert current.collaborations == ()
    assert current.conditions == ()
    assert unit.job_descriptions.correlation_id == "create-1"
    assert unit.committed and unit.closed


class FailingUnitOfWork(RecordingUnitOfWork):
    def __init__(
        self, failure: Exception, cause: Exception, stage: Literal["commit", "exit"]
    ) -> None:
        super().__init__()
        self.failure = failure
        self.cause = cause
        self.stage = stage

    def commit(self) -> None:
        if self.stage == "commit":
            raise self.failure from self.cause
        super().commit()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        super().__exit__(exc_type, exc_value, traceback)
        if self.stage == "exit":
            raise self.failure from self.cause


@pytest.mark.parametrize(
    ("commit_status", "stage"),
    [
        ("not_committed", "commit"),
        ("unknown", "commit"),
        ("committed", "exit"),
    ],
)
def test_transaction_completion_failure_preserves_commit_fact_and_cause(
    commit_status: CommitStatus,
    stage: Literal["commit", "exit"],
) -> None:
    cause = OSError("合成的持久邊界故障")
    failure = JobDescriptionPersistenceError(commit_status=commit_status)
    unit = FailingUnitOfWork(failure, cause, stage)

    with pytest.raises(JobDescriptionPersistenceError) as error:
        create_job_description(workspace_id=UUID(int=1), uow_factory=lambda: unit)

    assert error.value is failure
    assert error.value.commit_status == commit_status
    assert error.value.__cause__ is cause
    assert unit.closed
    assert unit.committed == (commit_status == "committed")
