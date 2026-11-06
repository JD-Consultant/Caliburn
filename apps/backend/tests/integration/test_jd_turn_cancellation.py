"""取消只恢復本輪提交；真 PostgreSQL 驗證重入、隔離、鎖與原子性。"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from threading import Barrier
from uuid import UUID, uuid7

import pytest
from sqlalchemy import Engine, text

from caliburn.modules.job_description.application.duties import add_duty
from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionHistoryDataError,
    JobDescriptionNotFoundError,
    JobDescriptionPersistenceError,
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
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_support import content_rows

TURN = "cancelled-turn"


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
    current = add_duty(
        workspace_id=jd_workspace_id,
        job_description_id=current.job_description_id,
        expected_version=current.version,
        name="既有職責",
        uow_factory=factory,
    )
    return add_task(
        workspace_id=jd_workspace_id,
        input=AddTaskInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            name="既有任務",
            duty_id=current.duties[0].id,
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
    correlation_id: str | None = TURN,
    purpose: str = "本輪改寫",
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


def _cancel(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
    *,
    workspace_id: UUID | None = None,
) -> JobDescriptionResult:
    return restore_turn_changes(
        workspace_id=workspace_id or baseline.workspace_id,
        input=RestoreTurnChangesInput(
            job_description_id=baseline.job_description_id,
            base_version=baseline.version,
            correlation_id=TURN,
        ),
        uow_factory=factory,
    )


def test_cancel_reentry_does_not_create_another_version(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    written = _edit(baseline, factory)
    restored = _cancel(baseline, factory)
    again = _cancel(baseline, factory)
    assert restored.version == written.version + 1
    assert again == restored
    assert restored.model_dump(exclude={"version"}) == baseline.model_dump(
        exclude={"version"}
    )
    entries = (
        SqlAlchemyJobDescriptionQueries(pg_engine)
        .list_history(
            workspace_id=baseline.workspace_id,
            job_description_id=baseline.job_description_id,
            reverts_correlation_id=TURN,
        )
        .items
    )
    assert len(entries) == 1
    assert entries[0].restored_from_version == baseline.version


def test_cancel_without_turn_writes_preserves_current_content_and_history(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    manual = _edit(baseline, factory, correlation_id=None, purpose="人工內容")
    before = content_rows(pg_engine)
    assert _cancel(baseline, factory) == manual
    assert content_rows(pg_engine) == before


@pytest.mark.parametrize("interleaved", [False, True])
def test_cancel_rejects_other_edits_after_base_without_losing_them(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
    interleaved: bool,
) -> None:
    written = _edit(baseline, factory)
    manual = _edit(written, factory, correlation_id=None, purpose="人工內容")
    if interleaved:
        _edit(manual, factory, purpose="本輪後續內容")
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionConcurrencyError):
        _cancel(baseline, factory)
    assert content_rows(pg_engine) == before


def test_cancel_reentry_keeps_edits_made_after_successful_restore(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    _edit(baseline, factory)
    restored = _cancel(baseline, factory)
    manual = _edit(restored, factory, correlation_id=None, purpose="取消後人工內容")
    before = content_rows(pg_engine)
    assert _cancel(baseline, factory) == manual
    assert content_rows(pg_engine) == before


def test_cancel_restores_deleted_entity_uuids_and_links(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    deleted = delete_task(
        workspace_id=baseline.workspace_id,
        job_description_id=baseline.job_description_id,
        task_id=baseline.tasks[0].id,
        expected_version=baseline.version,
        correlation_id=TURN,
        uow_factory=factory,
    )
    restored = _cancel(baseline, factory)
    assert restored.version == deleted.version + 1
    assert restored.tasks == baseline.tasks
    assert restored.knowledge == baseline.knowledge
    assert restored.skills == baseline.skills


def test_cancel_cannot_read_or_restore_a_different_workspace(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    _edit(baseline, factory)
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionNotFoundError):
        _cancel(baseline, factory, workspace_id=uuid7())
    assert content_rows(pg_engine) == before


def test_cancel_snapshot_failure_rolls_back_content_version_and_history(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    _edit(baseline, factory)
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
            CREATE FUNCTION reject_cancel_snapshot() RETURNS trigger AS $$
            BEGIN
                IF NEW.kind = 'restored' THEN
                    RAISE EXCEPTION 'synthetic cancellation snapshot failure';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
        """)
        )
        connection.execute(
            text("""
            CREATE TRIGGER reject_cancel_snapshot
            BEFORE INSERT ON job_description_snapshots
            FOR EACH ROW EXECUTE FUNCTION reject_cancel_snapshot()
        """)
        )
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionPersistenceError) as error:
        _cancel(baseline, factory)
    assert error.value.commit_status == "not_committed"
    assert content_rows(pg_engine) == before


def test_concurrent_cancellation_calls_share_one_restoration(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    written = _edit(baseline, factory)
    ready = Barrier(2)

    def cancel() -> JobDescriptionResult:
        ready.wait(timeout=5)
        return _cancel(baseline, factory)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(cancel)
        second = executor.submit(cancel)
        left = first.result(timeout=10)
        right = second.result(timeout=10)
    assert left == right
    assert left.version == written.version + 1


def test_cancel_requires_the_same_root_lock_as_content_writes(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    _edit(baseline, factory)
    impatient = partial(
        SqlAlchemyJobDescriptionUnitOfWork,
        create_session_factory(pg_engine),
        lock_timeout_ms=100,
    )
    with factory() as writer:
        writer.job_descriptions.get_for_update(
            workspace_id=baseline.workspace_id,
            job_description_id=baseline.job_description_id,
        )
        with ThreadPoolExecutor(max_workers=1) as executor:
            cancellation = executor.submit(_cancel, baseline, impatient)
            with pytest.raises(JobDescriptionConcurrencyError) as error:
                cancellation.result(timeout=5)
            assert error.value.reason == "lock_timeout"


def test_cancel_rejects_a_different_base_on_reentry(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    written = _edit(baseline, factory)
    _cancel(baseline, factory)
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionConcurrencyError):
        _cancel(written, factory)
    assert content_rows(pg_engine) == before


def test_cancel_reentry_rejects_writes_after_its_restoration_marker(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    _edit(baseline, factory)
    restored = _cancel(baseline, factory)
    _edit(restored, factory, purpose="取消後異常晚到的本輪寫入")
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionConcurrencyError):
        _cancel(baseline, factory)
    assert content_rows(pg_engine) == before


@pytest.mark.parametrize("has_manual_edit", [False, True])
def test_cancel_checks_history_beyond_one_page(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
    has_manual_edit: bool,
) -> None:
    current = baseline
    if has_manual_edit:
        current = _edit(current, factory, correlation_id=None, purpose="早期人工修改")
    for index in range(101):
        current = _edit(current, factory, purpose=f"本輪修改 {index}")
    if has_manual_edit:
        before = content_rows(pg_engine)
        with pytest.raises(JobDescriptionConcurrencyError):
            _cancel(baseline, factory)
        assert content_rows(pg_engine) == before
    else:
        restored = _cancel(baseline, factory)
        assert restored.version == current.version + 1
        assert restored.model_dump(exclude={"version"}) == baseline.model_dump(
            exclude={"version"}
        )


def test_cancel_with_net_zero_content_still_records_one_restoration(
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    written = _edit(baseline, factory)
    returned = update_job_description(
        workspace_id=baseline.workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=baseline.job_description_id,
            expected_version=written.version,
            purpose=baseline.purpose,
            correlation_id=TURN,
        ),
        uow_factory=factory,
    )
    restored = _cancel(baseline, factory)
    assert restored.version == returned.version + 1
    assert _cancel(baseline, factory) == restored


def test_cancel_refuses_incomplete_turn_history(
    pg_engine: Engine,
    baseline: JobDescriptionResult,
    factory: Callable[[], JobDescriptionUnitOfWork],
) -> None:
    first = _edit(baseline, factory)
    _edit(first, factory, purpose="後續寫入")
    with pg_engine.begin() as connection:
        connection.execute(
            text("""
                DELETE FROM job_description_snapshots
                WHERE job_description_id = :id AND version = :version
            """),
            {"id": baseline.job_description_id, "version": first.version},
        )
    before = content_rows(pg_engine)
    with pytest.raises(JobDescriptionHistoryDataError):
        _cancel(baseline, factory)
    assert content_rows(pg_engine) == before
