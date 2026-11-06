"""Workspace 整份刪除與 JD 寫入的真 PostgreSQL 競爭。"""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from queue import Queue
from threading import Event
from typing import Literal
from uuid import UUID

import pytest
from psycopg.errors import DeadlockDetected
from sqlalchemy import Engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import ORMExecuteState, Session

from caliburn.modules.job_description.application.errors import (
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history.operations import (
    RestoreJobDescriptionInput,
    get_history,
    list_history,
    restore,
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
from caliburn.modules.job_description.application.tasks.inputs import AddTaskInput
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
from caliburn.modules.workspace.application.errors import (
    WorkspaceConcurrencyError,
    WorkspaceNotFoundError,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.test_job_description_creation_concurrency import (
    report_backend_pid,
    wait_for_block,
)


def _create_jd_with_task(engine: Engine, workspace_id: UUID) -> JobDescriptionResult:
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(engine)
    )
    root = create_job_description(workspace_id=workspace_id, uow_factory=factory)
    return add_task(
        workspace_id=workspace_id,
        input=AddTaskInput(
            job_description_id=root.job_description_id,
            expected_version=root.version,
            name="可恢復的任務",
            outcomes=("成果",),
            requirements=("品質要求",),
        ),
        uow_factory=factory,
    )


@pytest.fixture
def restorable_jd(
    pg_engine: Engine, jd_workspace_id: UUID
) -> tuple[JobDescriptionResult, JobDescriptionResult]:
    target = _create_jd_with_task(pg_engine, jd_workspace_id)
    current = delete_task(
        workspace_id=jd_workspace_id,
        job_description_id=target.job_description_id,
        task_id=target.tasks[0].id,
        expected_version=target.version,
        uow_factory=partial(
            SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    return current, target


def _write_jd(
    operation: Literal["edit", "restore"],
    *,
    current: JobDescriptionResult,
    target: JobDescriptionResult,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
) -> JobDescriptionResult:
    if operation == "restore":
        return restore(
            workspace_id=current.workspace_id,
            input=RestoreJobDescriptionInput(
                job_description_id=current.job_description_id,
                expected_version=current.version,
                target_version=target.version,
            ),
            uow_factory=uow_factory,
        )
    return update_job_description(
        workspace_id=current.workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            purpose="刪除前完成的編修",
        ),
        uow_factory=uow_factory,
    )


def _assert_deleted(engine: Engine, original: JobDescriptionResult) -> None:
    service = WorkspaceService(
        partial(SqlAlchemyWorkspaceUnitOfWork, create_session_factory(engine))
    )
    with pytest.raises(WorkspaceNotFoundError):
        service.get(workspace_id=original.workspace_id)
    queries = SqlAlchemyJobDescriptionQueries(engine)
    assert (
        queries.get_job_description(
            workspace_id=original.workspace_id,
            job_description_id=original.job_description_id,
        )
        is None
    )
    with pytest.raises(JobDescriptionNotFoundError):
        list_history(
            workspace_id=original.workspace_id,
            job_description_id=original.job_description_id,
            queries=queries,
        )
    # 查讀拒絕之外，核對此 fixture 曾建立的資料沒有留下不可見孤兒。
    with engine.connect() as observer:
        for table in (
            "workspaces",
            "job_descriptions",
            "job_tasks",
            "task_outcomes",
            "task_requirements",
            "job_description_snapshots",
        ):
            assert observer.scalar(text(f"SELECT count(*) FROM {table}")) == 0


@pytest.mark.parametrize("operation", ["edit", "restore"])
def test_workspace_deletion_waits_for_jd_write_then_removes_new_history(
    pg_engine: Engine,
    restorable_jd: tuple[JobDescriptionResult, JobDescriptionResult],
    operation: Literal["edit", "restore"],
) -> None:
    """JD 寫入先完成但未提交；刪除真等待，隨後包含新內容及歷史一併清除。"""
    current, target = restorable_jd
    sessions = create_session_factory(pg_engine)
    writer_pid: Queue[int] = Queue()
    delete_pid: Queue[int] = Queue()
    release_writer = Event()

    def hold_writer(session: Session) -> None:
        report_backend_pid(session, writer_pid)
        assert release_writer.wait(8), "JD 寫入未收到提交訊號"

    def write() -> JobDescriptionResult:
        session = sessions()
        event.listen(session, "before_commit", hold_writer, once=True)
        return _write_jd(
            operation,
            current=current,
            target=target,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        )

    def delete_workspace() -> None:
        session = sessions()

        def report_delete(state: ORMExecuteState) -> None:
            if state.is_delete:
                report_backend_pid(session, delete_pid)

        event.listen(session, "do_orm_execute", report_delete)
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(lambda: session)).delete(
            workspace_id=current.workspace_id
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        written = executor.submit(write)
        try:
            blocker = writer_pid.get(timeout=5)
            deleted = executor.submit(delete_workspace)
            wait_for_block(
                pg_engine, waiting_pid=delete_pid.get(timeout=5), blocking_pid=blocker
            )
        finally:
            release_writer.set()
        result = written.result(timeout=5)
        deleted.result(timeout=5)
    assert result.version == current.version + 1
    if operation == "restore":
        assert result.tasks == target.tasks
    else:
        assert result.purpose == "刪除前完成的編修"
    _assert_deleted(pg_engine, current)


@pytest.mark.parametrize("operation", ["edit", "restore"])
def test_jd_write_waits_for_workspace_deletion_then_cannot_revive_data(
    pg_engine: Engine,
    restorable_jd: tuple[JobDescriptionResult, JobDescriptionResult],
    operation: Literal["edit", "restore"],
) -> None:
    """刪除已執行但未提交；編修及可重建 Task 的恢復等到提交後皆找不到 JD。"""
    current, target = restorable_jd
    sessions = create_session_factory(pg_engine)
    delete_pid: Queue[int] = Queue()
    writer_pid: Queue[int] = Queue()
    release_delete = Event()

    def hold_delete(session: Session) -> None:
        report_backend_pid(session, delete_pid)
        assert release_delete.wait(8), "Workspace 刪除未收到提交訊號"

    def delete_workspace() -> None:
        session = sessions()
        event.listen(session, "before_commit", hold_delete, once=True)
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(lambda: session)).delete(
            workspace_id=current.workspace_id
        )

    def write() -> JobDescriptionResult:
        session = sessions()

        def report_select(state: ORMExecuteState) -> None:
            if state.is_select:
                report_backend_pid(session, writer_pid)

        event.listen(session, "do_orm_execute", report_select)
        return _write_jd(
            operation,
            current=current,
            target=target,
            uow_factory=lambda: SqlAlchemyJobDescriptionUnitOfWork(lambda: session),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        deleted = executor.submit(delete_workspace)
        try:
            blocker = delete_pid.get(timeout=5)
            written = executor.submit(write)
            wait_for_block(
                pg_engine, waiting_pid=writer_pid.get(timeout=5), blocking_pid=blocker
            )
        finally:
            release_delete.set()
        deleted.result(timeout=5)
        with pytest.raises(JobDescriptionNotFoundError):
            written.result(timeout=5)
    _assert_deleted(pg_engine, current)


def test_native_deadlock_rolls_back_all_workspace_content_and_history(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """反序鎖定形成真死鎖；受害交易完整回滾，不依賴 PostgreSQL 選哪一方。"""
    sessions = create_session_factory(pg_engine)
    service = WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, sessions))
    other_workspace_id = service.create(interviewee_name="另一份完整檔案").workspace_id
    originals = tuple(
        _create_jd_with_task(pg_engine, workspace_id)
        for workspace_id in (jd_workspace_id, other_workspace_id)
    )
    workspaces = tuple(
        service.get(workspace_id=item.workspace_id) for item in originals
    )
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    history_before = tuple(
        tuple(
            get_history(
                workspace_id=item.workspace_id,
                job_description_id=item.job_description_id,
                version=entry.version,
                queries=queries,
            )
            for entry in list_history(
                workspace_id=item.workspace_id,
                job_description_id=item.job_description_id,
                queries=queries,
            ).items
        )
        for item in originals
    )
    first_pid: Queue[int] = Queue()
    second_pid: Queue[int] = Queue()
    release_first = Event()
    release_second = Event()

    class RollBackSurvivor(Exception):
        """存活交易也退出且回滾，才能檢查死鎖受害交易的全部原資料。"""

    def delete_in_order(
        first_id: UUID,
        second_id: UUID,
        pid_queue: Queue[int],
        proceed: Event,
    ) -> str:
        session = sessions()
        try:
            with SqlAlchemyWorkspaceUnitOfWork(lambda: session) as uow:
                assert uow.workspaces.delete(first_id)
                report_backend_pid(session, pid_queue)
                assert proceed.wait(8), "反序刪除未收到繼續訊號"
                assert uow.workspaces.delete(second_id)
                raise RollBackSurvivor
        except WorkspaceConcurrencyError as error:
            assert error.reason == "deadlock"
            assert isinstance(error.__cause__, DBAPIError)
            assert isinstance(error.__cause__.orig, DeadlockDetected)
            return "deadlock"
        except RollBackSurvivor:
            return "rolled_back"

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(
            delete_in_order,
            jd_workspace_id,
            other_workspace_id,
            first_pid,
            release_first,
        )
        second = executor.submit(
            delete_in_order,
            other_workspace_id,
            jd_workspace_id,
            second_pid,
            release_second,
        )
        try:
            first_backend = first_pid.get(timeout=5)
            second_backend = second_pid.get(timeout=5)
            release_first.set()
            wait_for_block(
                pg_engine, waiting_pid=first_backend, blocking_pid=second_backend
            )
            release_second.set()
        finally:
            release_first.set()
            release_second.set()
        assert sorted((first.result(timeout=5), second.result(timeout=5))) == [
            "deadlock",
            "rolled_back",
        ]

    for original, workspace, history in zip(
        originals, workspaces, history_before, strict=True
    ):
        assert service.get(workspace_id=original.workspace_id) == workspace
        assert (
            queries.get_job_description(
                workspace_id=original.workspace_id,
                job_description_id=original.job_description_id,
            )
            == original
        )
        assert (
            tuple(
                get_history(
                    workspace_id=original.workspace_id,
                    job_description_id=original.job_description_id,
                    version=entry.version,
                    queries=queries,
                )
                for entry in list_history(
                    workspace_id=original.workspace_id,
                    job_description_id=original.job_description_id,
                    queries=queries,
                ).items
            )
            == history
        )
