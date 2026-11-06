"""真 PostgreSQL 鎖等待驗證同根競爭、獨立 Workspace 與刪除次序。"""

from concurrent.futures import ThreadPoolExecutor
from functools import partial
from queue import Queue
from threading import Event
from time import monotonic
from uuid import UUID

import pytest
from sqlalchemy import Connection, Engine, event, text
from sqlalchemy.orm import Session

from caliburn.modules.plan.application.errors import (
    PlanConcurrencyError,
    WorkspaceNotFoundError,
)
from caliburn.modules.plan.application.plans import initialize_plan, patch_plan
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def _wait_for_block(engine: Engine, *, waiting: int, blocking: int) -> None:
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with engine.connect() as connection:
            blockers = connection.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting}
            )
        if blocking in blockers:
            return
    raise AssertionError("未觀察到預期的 PostgreSQL 鎖等待")


def _report_on_begin(session: Session, reported: Queue[int]) -> None:
    def report(session: Session, transaction: object, connection: Connection) -> None:
        pid = connection.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        reported.put(pid)

    event.listen(session, "after_begin", report)


@pytest.mark.parametrize("operation", ["initialize", "patch"])
def test_same_plan_writers_wait_and_keep_one_effect(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: str,
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    if operation == "patch":
        initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release = Event()

    def hold(session: Session) -> None:
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        first_pid.put(pid)
        assert release.wait(8), "第一筆寫入未獲釋放"

    def write(*, first: bool) -> PlanView:
        session = sessions()
        if first:
            event.listen(session, "before_commit", hold)
        else:
            _report_on_begin(session, second_pid)
        one = partial(SqlAlchemyPlanUnitOfWork, lambda: session)
        if operation == "initialize":
            return initialize_plan(workspace_id=jd_workspace_id, uow_factory=one)
        return patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            diff=f"@@\n+{'first' if first else 'second'}\n*** End of File",
            uow_factory=one,
        ).plan

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(write, first=True)
        try:
            blocking = first_pid.get(timeout=5)
            second = executor.submit(write, first=False)
            _wait_for_block(
                pg_engine, waiting=second_pid.get(timeout=5), blocking=blocking
            )
            other = WorkspaceService(
                lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
            ).create(interviewee_name="不受另一個 Plan 鎖影響")
            assert (
                initialize_plan(
                    workspace_id=other.workspace_id, uow_factory=factory
                ).version
                == 1
            )
        finally:
            release.set()
        first_result = first.result(timeout=5)
        if operation == "initialize":
            assert (
                second.result(timeout=5)
                == first_result
                == PlanView(jd_workspace_id, 1, None)
            )
        else:
            with pytest.raises(PlanConcurrencyError):
                second.result(timeout=5)
            assert first_result == PlanView(jd_workspace_id, 2, "first")
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
        == first_result
    )


@pytest.mark.parametrize("operation", ["initialize", "patch"])
def test_workspace_deletion_wins_without_plan_recreation(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: str,
) -> None:
    sessions = create_session_factory(pg_engine)
    if operation == "patch":
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
        )
    waiting_pid: Queue[int] = Queue()

    def write() -> None:
        session = sessions()
        _report_on_begin(session, waiting_pid)
        factory = partial(SqlAlchemyPlanUnitOfWork, lambda: session)
        with pytest.raises(WorkspaceNotFoundError):
            if operation == "initialize":
                initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
            else:
                patch_plan(
                    workspace_id=jd_workspace_id,
                    expected_version=1,
                    diff="@@\n+不可重生\n*** End of File",
                    uow_factory=factory,
                )

    with ThreadPoolExecutor(max_workers=1) as executor:
        deleting_session = sessions()
        with SqlAlchemyWorkspaceUnitOfWork(lambda: deleting_session) as deleting:
            deleting.workspaces.delete(jd_workspace_id)
            blocking = deleting_session.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(blocking, int)
            pending = executor.submit(write)
            _wait_for_block(
                pg_engine, waiting=waiting_pid.get(timeout=5), blocking=blocking
            )
            deleting.commit()
        pending.result(timeout=5)
    with pytest.raises(WorkspaceNotFoundError):
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)


def test_plan_lock_wait_is_bounded_and_does_not_modify_content(
    pg_engine: Engine,
    jd_workspace_id: UUID,
) -> None:
    sessions = create_session_factory(pg_engine)
    initial = initialize_plan(
        workspace_id=jd_workspace_id,
        uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
    )
    with pg_engine.connect() as locking:
        locking.execute(
            text("SELECT workspace_id FROM plans WHERE workspace_id=:id FOR UPDATE"),
            {"id": jd_workspace_id},
        )
        with pytest.raises(PlanConcurrencyError) as error:
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=1,
                diff="@@\n+鎖等待拒絕\n*** End of File",
                uow_factory=lambda: SqlAlchemyPlanUnitOfWork(
                    sessions, lock_timeout_ms=50
                ),
            )
        assert error.value.reason == "lock_timeout"
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
        == initial
    )


@pytest.mark.parametrize("operation", ["initialize", "patch"])
def test_workspace_deletion_waits_for_plan_write_then_removes_it(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    operation: str,
) -> None:
    sessions = create_session_factory(pg_engine)
    if operation == "patch":
        initialize_plan(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
        )
    writer_pid: Queue[int] = Queue()
    deleting_pid: Queue[int] = Queue()
    release = Event()

    def hold(session: Session) -> None:
        pid = session.scalar(text("SELECT pg_backend_pid()"))
        assert isinstance(pid, int)
        writer_pid.put(pid)
        assert release.wait(8), "Plan 寫入未獲釋放"

    def write() -> None:
        session = sessions()
        event.listen(session, "before_commit", hold)
        factory = partial(SqlAlchemyPlanUnitOfWork, lambda: session)
        if operation == "initialize":
            initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
        else:
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=1,
                diff="@@\n+寫完即刪\n*** End of File",
                uow_factory=factory,
            )

    def delete() -> None:
        session = sessions()
        _report_on_begin(session, deleting_pid)
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(lambda: session)).delete(
            workspace_id=jd_workspace_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        writing = executor.submit(write)
        try:
            blocking = writer_pid.get(timeout=5)
            deleting = executor.submit(delete)
            _wait_for_block(
                pg_engine, waiting=deleting_pid.get(timeout=5), blocking=blocking
            )
        finally:
            release.set()
        writing.result(timeout=5)
        deleting.result(timeout=5)
    with pytest.raises(WorkspaceNotFoundError):
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
