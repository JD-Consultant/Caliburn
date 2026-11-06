"""公開短碼服務的真 PostgreSQL 競爭與 Workspace 刪除次序。"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic
from typing import Any
from uuid import UUID, uuid4

import pytest
from psycopg.errors import ForeignKeyViolation
from sqlalchemy import Connection, Engine, event, text
from sqlalchemy.engine import Result
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import ORMExecuteState, Session

from caliburn.modules.model_references import (
    ModelReferenceAllocationError,
    ReferenceTarget,
    UnknownModelReferenceError,
)
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.workspace.application.errors import WorkspaceNotFoundError
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def _bounded_session(sessions: Callable[[], Session]) -> Session:
    session = sessions()

    def begin(session: Session, transaction: object, connection: Connection) -> None:
        # 測試失敗也不讓 worker 無限卡在資料庫；不改受測的 conflict handling。
        connection.execute(text("SET LOCAL statement_timeout = '10s'"))

    event.listen(session, "after_begin", begin)
    return session


def _observed_session(
    sessions: Callable[[], Session],
    reported: Queue[int],
    *,
    hold_commit: Event | None = None,
) -> Session:
    """以原生交易事件觀察 PID；持有者到提交前才回報已取得資料庫鎖。"""
    session = _bounded_session(sessions)

    def begin(session: Session, transaction: object, connection: Connection) -> None:
        if hold_commit is None:
            pid = connection.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(pid, int)
            reported.put(pid)

    def before_commit(session: Session) -> None:
        assert hold_commit is not None
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        reported.put(pid)
        assert hold_commit.wait(12), "未釋放受測交易"

    event.listen(session, "after_begin", begin)
    if hold_commit is not None:
        event.listen(session, "before_commit", before_commit)
    return session


def _wait_for_block(engine: Engine, *, waiting: int, blocking: int) -> None:
    # 只觀察 PG 的實際鎖等待，不比對 INSERT SQL 或以 sleep 猜 worker 次序。
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with engine.connect() as connection:
            blockers = connection.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting}
            )
        if blocking in blockers:
            return
    raise AssertionError("未觀察到預期的 PostgreSQL 鎖等待")


@pytest.mark.parametrize(
    ("first_indexes", "second_indexes"),
    [
        pytest.param((0,), (0,), id="same-target"),
        pytest.param((0, 1, 2), (3, 2, 1), id="reversed-overlapping-batches"),
    ],
)
def test_competing_allocations_wait_and_return_stable_references(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    first_indexes: tuple[int, ...],
    second_indexes: tuple[int, ...],
) -> None:
    sessions = create_session_factory(pg_engine)
    targets = [ReferenceTarget("task", uuid4()) for _ in range(4)]
    first_targets = [targets[index] for index in first_indexes]
    second_targets = [targets[index] for index in second_indexes]
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release = Event()
    first_references = SqlAlchemyModelReferences(
        lambda: _observed_session(sessions, first_pid, hold_commit=release)
    )
    second_references = SqlAlchemyModelReferences(
        lambda: _observed_session(sessions, second_pid)
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            first_references.get_or_create_refs, jd_workspace_id, first_targets
        )
        try:
            blocking = first_pid.get(timeout=5)
            second = executor.submit(
                second_references.get_or_create_refs, jd_workspace_id, second_targets
            )
            _wait_for_block(
                pg_engine, waiting=second_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        first_result = first.result(timeout=5)
        second_result = second.result(timeout=5)

    assert set(first_result) == set(first_targets)
    assert set(second_result) == set(second_targets)
    for target in set(first_targets) & set(second_targets):
        assert first_result[target] == second_result[target]
    combined = first_result | second_result
    assert len(set(combined.values())) == len(combined)
    persisted = SqlAlchemyModelReferences(sessions)
    assert persisted.get_or_create_refs(jd_workspace_id, list(combined)) == combined
    assert persisted.resolve_refs(jd_workspace_id, list(combined.values())) == {
        reference: target for target, reference in combined.items()
    }


def test_workspace_deletion_wins_and_waiting_allocation_cannot_recreate_mapping(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    references = SqlAlchemyModelReferences(sessions)
    original = ReferenceTarget("task", uuid4())
    original_ref = references.get_or_create_refs(jd_workspace_id, [original])[original]
    pending_target = ReferenceTarget("message", uuid4())
    deleting_pid: Queue[int] = Queue()
    allocating_pid: Queue[int] = Queue()
    release = Event()
    workspaces = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(
            lambda: _observed_session(sessions, deleting_pid, hold_commit=release)
        )
    )
    allocating = SqlAlchemyModelReferences(
        lambda: _observed_session(sessions, allocating_pid)
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        deleting = executor.submit(workspaces.delete, workspace_id=jd_workspace_id)
        try:
            blocking = deleting_pid.get(timeout=5)
            allocation = executor.submit(
                allocating.get_or_create_refs, jd_workspace_id, [pending_target]
            )
            _wait_for_block(
                pg_engine, waiting=allocating_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        deleting.result(timeout=5)
        # 映射沒有額外的 Workspace 錯誤翻譯；儲存失敗沿公開契約向外傳遞。
        with pytest.raises(IntegrityError) as error:
            allocation.result(timeout=5)
        assert isinstance(error.value.orig, ForeignKeyViolation)

    with pytest.raises(UnknownModelReferenceError):
        references.resolve_refs(jd_workspace_id, [original_ref])
    with pytest.raises(WorkspaceNotFoundError):
        workspaces.get(workspace_id=jd_workspace_id)


def test_workspace_deletion_waits_for_allocation_then_removes_its_mapping(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    target = ReferenceTarget("task", uuid4())
    allocating_pid: Queue[int] = Queue()
    deleting_pid: Queue[int] = Queue()
    release = Event()
    allocating = SqlAlchemyModelReferences(
        lambda: _observed_session(sessions, allocating_pid, hold_commit=release)
    )
    workspaces = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(
            lambda: _observed_session(sessions, deleting_pid)
        )
    )

    with ThreadPoolExecutor(max_workers=2) as executor:
        allocation = executor.submit(
            allocating.get_or_create_refs, jd_workspace_id, [target]
        )
        try:
            blocking = allocating_pid.get(timeout=5)
            deleting = executor.submit(workspaces.delete, workspace_id=jd_workspace_id)
            _wait_for_block(
                pg_engine, waiting=deleting_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        assigned = allocation.result(timeout=5)
        deleting.result(timeout=5)

    assert set(assigned) == {target}
    with pytest.raises(UnknownModelReferenceError):
        SqlAlchemyModelReferences(sessions).resolve_refs(
            jd_workspace_id, [assigned[target]]
        )
    with pytest.raises(WorkspaceNotFoundError):
        workspaces.get(workspace_id=jd_workspace_id)


def test_existing_mapping_deleted_before_readback_rejects_incomplete_allocation(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    references = SqlAlchemyModelReferences(sessions)
    target = ReferenceTarget("task", uuid4())
    original_ref = references.get_or_create_refs(jd_workspace_id, [target])[target]
    workspaces = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(lambda: _bounded_session(sessions))
    )
    insert_completed = Event()
    release = Event()

    def paused_session() -> Session:
        session = _bounded_session(sessions)

        def pause_after_insert(execution: ORMExecuteState) -> Result[Any]:
            result = execution.invoke_statement()
            if execution.is_insert:
                # 既有目標的 conflict path 不持有新插入才取得的 FK 鎖。
                # 在正式 DB 寫入與讀回間安排刪除，斷言公開整批拒絕效果。
                insert_completed.set()
                assert release.wait(12), "既有映射配置未獲釋放"
            return result

        event.listen(session, "do_orm_execute", pause_after_insert, retval=True)
        return session

    with ThreadPoolExecutor(max_workers=1) as executor:
        allocation = executor.submit(
            SqlAlchemyModelReferences(paused_session).get_or_create_refs,
            jd_workspace_id,
            [target],
        )
        try:
            assert insert_completed.wait(5), "配置未完成 INSERT"
            workspaces.delete(workspace_id=jd_workspace_id)
        finally:
            release.set()
        with pytest.raises(ModelReferenceAllocationError):
            allocation.result(timeout=5)

    with pytest.raises(UnknownModelReferenceError):
        references.resolve_refs(jd_workspace_id, [original_ref])
    with pytest.raises(WorkspaceNotFoundError):
        workspaces.get(workspace_id=jd_workspace_id)
