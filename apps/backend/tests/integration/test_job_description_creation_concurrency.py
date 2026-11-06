"""兩條真 PostgreSQL 連線驗證建立 JD 的競爭與有界拒絕。"""

from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Event
from time import monotonic
from uuid import UUID

import pytest
from sqlalchemy import Engine, event, text
from sqlalchemy.orm import ORMExecuteState, Session

from caliburn.modules.job_description.application.errors import (
    JobDescriptionAlreadyExistsError,
    JobDescriptionConcurrencyError,
    JobDescriptionWorkspaceNotFoundError,
)
from caliburn.modules.job_description.application.job_descriptions import (
    create_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_workspace_lock_timeout_rejects_the_whole_creation(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """Workspace 被未提交刪除鎖住時，JD 依設定期限拒絕且不留新根。"""
    with pg_engine.connect() as deleting:
        deleting.execute(
            text("DELETE FROM workspaces WHERE id=:id"), {"id": jd_workspace_id}
        )
        with pytest.raises(JobDescriptionConcurrencyError) as error:
            create_job_description(
                workspace_id=jd_workspace_id,
                uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(
                    create_session_factory(pg_engine), lock_timeout_ms=100
                ),
            )
        assert error.value.__cause__ is not None
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0
        assert observer.scalar(text("SELECT count(*) FROM workspaces")) == 1


def wait_for_block(engine: Engine, *, waiting_pid: int, blocking_pid: int) -> None:
    """等到資料庫證實指定連線受阻；不以固定延遲推定時序。"""
    deadline = monotonic() + 5
    while monotonic() < deadline:
        with engine.connect() as observer:
            blockers = observer.scalar(
                text("SELECT pg_blocking_pids(:pid)"), {"pid": waiting_pid}
            )
        if blocking_pid in blockers:
            return
    raise AssertionError("競爭連線未在期限內進入預期鎖等待")


def report_backend_pid(session: Session, queue: Queue[int]) -> None:
    """將目前真連線身分交給有界的鎖觀察者。"""
    pid = session.scalar(text("SELECT pg_backend_pid()"))
    assert isinstance(pid, int)
    queue.put(pid)


def test_competing_creations_save_exactly_one_root(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """兩個公開建立用例確實競爭 UNIQUE，只有一份成功且未重播。"""
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release_first = Event()
    sessions = create_session_factory(pg_engine)

    def hold_first_flush(session: Session, flush_context: object) -> None:
        report_backend_pid(session, first_pid)
        assert release_first.wait(8), "第一筆建立未收到釋放訊號"

    def report_second_flush(session: Session, *args: object) -> None:
        report_backend_pid(session, second_pid)

    def create_first() -> UUID:
        session = sessions()
        event.listen(session, "after_flush", hold_first_flush)
        return create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        ).job_description_id

    def create_second() -> None:
        def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
            session = sessions()
            event.listen(session, "before_flush", report_second_flush)
            return SqlAlchemyJobDescriptionUnitOfWork(lambda: session)

        with pytest.raises(JobDescriptionAlreadyExistsError):
            create_job_description(
                workspace_id=jd_workspace_id,
                uow_factory=factory,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(create_first)
        try:
            blocker = first_pid.get(timeout=5)
            second = executor.submit(create_second)
            wait_for_block(
                pg_engine, waiting_pid=second_pid.get(timeout=5), blocking_pid=blocker
            )
        finally:
            release_first.set()
        saved_id = first.result(timeout=5)
        second.result(timeout=5)
    with pg_engine.connect() as observer:
        assert observer.execute(
            text("SELECT id, workspace_id, version FROM job_descriptions")
        ).one() == (saved_id, jd_workspace_id, 1)


def test_workspace_delete_waits_for_jd_then_removes_root_and_history(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """先建立 JD 鎖住 Workspace 關係，並行刪除等待後清除根與初始歷史。"""
    first_pid: Queue[int] = Queue()
    delete_pid: Queue[int] = Queue()
    release_create = Event()
    sessions = create_session_factory(pg_engine)

    def hold_flush(session: Session, flush_context: object) -> None:
        report_backend_pid(session, first_pid)
        assert release_create.wait(8), "建立 JD 未收到釋放訊號"

    def create_root() -> UUID:
        session = sessions()
        event.listen(session, "after_flush", hold_flush)
        return create_job_description(
            workspace_id=jd_workspace_id,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        ).job_description_id

    def delete_workspace() -> None:
        session = sessions()

        def report_delete(state: ORMExecuteState) -> None:
            if state.is_delete:
                report_backend_pid(session, delete_pid)

        event.listen(session, "do_orm_execute", report_delete)
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(lambda: session)).delete(
            workspace_id=jd_workspace_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        created = executor.submit(create_root)
        try:
            blocker = first_pid.get(timeout=5)
            deleted = executor.submit(delete_workspace)
            wait_for_block(
                pg_engine, waiting_pid=delete_pid.get(timeout=5), blocking_pid=blocker
            )
        finally:
            release_create.set()
        created.result(timeout=5)
        deleted.result(timeout=5)
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM workspaces")) == 0
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0
        assert (
            observer.scalar(text("SELECT count(*) FROM job_description_snapshots")) == 0
        )


def test_jd_waiting_for_workspace_deletion_is_rejected_without_orphans(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """Workspace 刪除先取得鎖且提交，等待的 JD 整筆拒絕且不留下孤兒。"""
    create_pid: Queue[int] = Queue()
    sessions = create_session_factory(pg_engine)

    def report_flush(session: Session, *args: object) -> None:
        report_backend_pid(session, create_pid)

    def create_root() -> None:
        def factory() -> SqlAlchemyJobDescriptionUnitOfWork:
            session = sessions()
            event.listen(session, "before_flush", report_flush)
            return SqlAlchemyJobDescriptionUnitOfWork(lambda: session)

        with pytest.raises(JobDescriptionWorkspaceNotFoundError):
            create_job_description(
                workspace_id=jd_workspace_id,
                uow_factory=factory,
            )

    with ThreadPoolExecutor(max_workers=1) as executor:
        session = sessions()
        with SqlAlchemyWorkspaceUnitOfWork(lambda: session) as deleting:
            assert deleting.workspaces.delete(jd_workspace_id)
            blocker = session.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(blocker, int)
            pending = executor.submit(create_root)
            wait_for_block(
                pg_engine, waiting_pid=create_pid.get(timeout=5), blocking_pid=blocker
            )
            deleting.commit()
        pending.result(timeout=5)
    with pg_engine.connect() as observer:
        assert observer.scalar(text("SELECT count(*) FROM job_descriptions")) == 0
        assert observer.scalar(text("SELECT count(*) FROM workspaces")) == 0
