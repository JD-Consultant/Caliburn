"""完成輪撤銷上層接線；核心交易與並行規則由其 PG 測試驗證。"""

import asyncio
from collections.abc import Callable
from dataclasses import replace
from threading import get_ident
from uuid import UUID, uuid7

import pytest

from caliburn.modules.job_description.application.history import turn_changes
from caliburn.modules.job_description.application.history.turn_changes import (
    RestoreTurnChangesInput,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.turn_history import (
    JobDescriptionTurnNotFoundError,
    restore_completed_turn_changes,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from tests.unit.modules.job_description.application.test_turn_history import (
    CompletedReader,
    SavedHistory,
)


def no_direct_uow() -> JobDescriptionUnitOfWork:
    raise AssertionError("上層不能繞過既有撤銷用例自行開交易")


class CoreRestoreRecorder:
    """只觀察公開核心入口，不模擬根鎖、資料庫或並行。"""

    def __init__(self, history: SavedHistory) -> None:
        self.result = JobDescriptionResult.from_job_description(
            JobDescription.model_validate_json(history.snapshots[0].content_json),
            version=6,
        )
        self.calls: list[tuple[UUID, RestoreTurnChangesInput, int]] = []
        self.error: Exception | None = None

    def __call__(
        self,
        *,
        workspace_id: UUID,
        input: RestoreTurnChangesInput,
        uow_factory: Callable[[], JobDescriptionUnitOfWork],
    ) -> JobDescriptionResult:
        assert uow_factory is no_direct_uow
        self.calls.append((workspace_id, input, get_ident()))
        if self.error is not None:
            raise self.error
        return self.result


@pytest.mark.parametrize("reverse", [False, True])
def test_completed_restore_passes_fixed_versions_to_core_in_worker(
    monkeypatch: pytest.MonkeyPatch, reverse: bool
) -> None:
    history = SavedHistory()
    if reverse:
        history.versions = replace(history.versions, before_version=5, after_version=2)
    versions = history.versions
    reader = CompletedReader(versions)
    core = CoreRestoreRecorder(history)
    monkeypatch.setattr(turn_changes, "restore_turn_changes", core)
    caller_thread = get_ident()
    result = asyncio.run(
        restore_completed_turn_changes(
            workspace_id=versions.workspace_id,
            job_description_id=versions.job_description_id,
            turn_id=versions.turn_id,
            completed_turn_reader=reader,
            uow_factory=no_direct_uow,
        )
    )
    assert result is core.result
    assert reader.calls == [(versions.workspace_id, versions.turn_id)]
    assert len(core.calls) == 1
    workspace, received, thread = core.calls[0]
    assert workspace == versions.workspace_id
    assert received.job_description_id == versions.job_description_id
    assert received.base_version == versions.before_version
    assert received.completed_version == versions.after_version
    assert received.correlation_id == str(versions.turn_id)
    assert thread != caller_thread
    assert history.reads == []


@pytest.mark.parametrize("scope", [None, "workspace", "jd", "turn"])
def test_missing_or_wrong_completion_rejects_before_core(
    monkeypatch: pytest.MonkeyPatch, scope: str | None
) -> None:
    history = SavedHistory()
    versions = history.versions
    if scope is None:
        returned = None
    elif scope == "workspace":
        returned = replace(versions, workspace_id=uuid7())
    elif scope == "jd":
        returned = replace(versions, job_description_id=uuid7())
    else:
        returned = replace(versions, turn_id=uuid7())
    core = CoreRestoreRecorder(history)
    monkeypatch.setattr(turn_changes, "restore_turn_changes", core)
    with pytest.raises(JobDescriptionTurnNotFoundError):
        asyncio.run(
            restore_completed_turn_changes(
                workspace_id=versions.workspace_id,
                job_description_id=versions.job_description_id,
                turn_id=versions.turn_id,
                completed_turn_reader=CompletedReader(returned),
                uow_factory=no_direct_uow,
            )
        )
    assert core.calls == []
