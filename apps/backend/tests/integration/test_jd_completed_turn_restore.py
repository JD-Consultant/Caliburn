"""完成輪固定上界只限制待撤寫入；不改取消、無寫入或重入契約。"""

from collections.abc import Callable
from functools import partial
from uuid import UUID

import pytest
from sqlalchemy import Engine

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
)
from caliburn.modules.job_description.application.history.turn_changes import (
    RestoreTurnChangesInput,
    restore_turn_changes,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    create_job_description,
    update_job_description,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    NewDefinitionInput,
)
from caliburn.modules.job_description.application.tasks.lifecycle import (
    add_task,
    delete_task,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_support import content_rows

TURN = "completed-turn"


@pytest.fixture
def factory(pg_engine: Engine) -> Callable[[], JobDescriptionUnitOfWork]:
    return partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )


@pytest.fixture
def baseline(
    jd_workspace_id: UUID, factory: Callable[[], JobDescriptionUnitOfWork]
) -> JobDescriptionResult:
    current = create_job_description(workspace_id=jd_workspace_id, uow_factory=factory)
    return add_task(
        workspace_id=jd_workspace_id,
        input=AddTaskInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            name="既有任務",
            outcomes=("原成果",),
            requirements=("原要求",),
            knowledge=(NewDefinitionInput(name="原知識"),),
            skills=(NewDefinitionInput(name="原技能"),),
        ),
        uow_factory=factory,
    )


def _edit(
    current: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
    *,
    purpose: str,
    correlation_id: str | None = TURN,
) -> JobDescriptionResult:
    return update_job_description(
        workspace_id=current.workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            purpose=purpose,
            correlation_id=correlation_id,
        ),
        uow_factory=factory,
    )


def _restore(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
    *,
    completed_version: int | None,
) -> JobDescriptionResult:
    return restore_turn_changes(
        workspace_id=baseline.workspace_id,
        input=RestoreTurnChangesInput(
            job_description_id=baseline.job_description_id,
            base_version=baseline.version,
            correlation_id=TURN,
            completed_version=completed_version,
        ),
        uow_factory=factory,
    )


def test_completed_restore_rejects_same_turn_write_beyond_fixed_completion(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    completed = _edit(baseline, factory, purpose="已完成內容")
    _edit(completed, factory, purpose="完成後同來源新寫入")
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionConcurrencyError):
        _restore(baseline, factory, completed_version=completed.version)
    assert content_rows(pg_engine) == before


def test_completed_restore_keeps_original_entity_uuids_and_references(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    completed = delete_task(
        workspace_id=baseline.workspace_id,
        job_description_id=baseline.job_description_id,
        task_id=baseline.tasks[0].id,
        expected_version=baseline.version,
        correlation_id=TURN,
        uow_factory=factory,
    )
    restored = _restore(baseline, factory, completed_version=completed.version)
    assert restored.version == completed.version + 1
    assert restored.tasks == baseline.tasks
    assert restored.knowledge == baseline.knowledge
    assert restored.skills == baseline.skills


@pytest.mark.parametrize("completed_version", [1, 2])
def test_completed_restore_without_turn_writes_is_noop_even_with_reverse_versions(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
    completed_version: int,
) -> None:
    assert baseline.version == 2
    manual = _edit(baseline, factory, purpose="人工後續內容", correlation_id=None)
    before = content_rows(pg_engine)
    restored = _restore(baseline, factory, completed_version=completed_version)
    assert restored == manual
    assert content_rows(pg_engine) == before


def test_completed_restore_rejects_later_manual_edit(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    completed = _edit(baseline, factory, purpose="本輪內容")
    _edit(completed, factory, purpose="人工後續內容", correlation_id=None)
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionConcurrencyError):
        _restore(baseline, factory, completed_version=completed.version)
    assert content_rows(pg_engine) == before


def test_completed_restore_reentry_preserves_later_manual_edit(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    completed = _edit(baseline, factory, purpose="本輪內容")
    restored = _restore(baseline, factory, completed_version=completed.version)
    manual = _edit(restored, factory, purpose="撤銷後人工內容", correlation_id=None)
    before = content_rows(pg_engine)
    assert _restore(baseline, factory, completed_version=completed.version) == manual
    assert content_rows(pg_engine) == before


def test_completed_restore_reentry_rejects_later_same_turn_write(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    completed = _edit(baseline, factory, purpose="本輪內容")
    restored = _restore(baseline, factory, completed_version=completed.version)
    _edit(restored, factory, purpose="撤銷後同輪新內容")
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionConcurrencyError):
        _restore(baseline, factory, completed_version=completed.version)
    assert content_rows(pg_engine) == before


def test_cancellation_without_completion_bound_includes_unreported_committed_write(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    reported = _edit(baseline, factory, purpose="工具已回覆內容")
    committed = _edit(reported, factory, purpose="已提交尚未保存工具回覆內容")
    restored = restore_turn_changes(
        workspace_id=baseline.workspace_id,
        input=RestoreTurnChangesInput(
            job_description_id=baseline.job_description_id,
            base_version=baseline.version,
            correlation_id=TURN,
        ),
        uow_factory=factory,
    )
    assert restored.version == committed.version + 1
    assert restored.model_dump(exclude={"version"}) == baseline.model_dump(
        exclude={"version"}
    )
