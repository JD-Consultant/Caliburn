"""真 PostgreSQL 鎖競爭與 migration 可重建性。"""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from time import monotonic, sleep
from uuid import uuid7

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, inspect, text
from sqlalchemy.orm import Session

from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.modules.workspace.infrastructure.persistence.repository import (
    SqlAlchemyWorkspaceRepository,
)


def test_competing_renames_wait_on_row_lock_and_last_writer_wins(
    pg_engine: Engine,
) -> None:
    """兩個連線競爭相同列，後寫入者等待鎖後保存，不新增第二筆。"""
    original = Workspace(id=uuid7(), interviewee_name=IntervieweeName(value="原姓名"))
    with Session(pg_engine) as initial:
        SqlAlchemyWorkspaceRepository(initial).add(original)
        initial.commit()
    pid_queue: Queue[int] = Queue()

    def competing_rename() -> bool:
        with Session(pg_engine) as session:
            # 明示有限等待，失敗時測試不能永久掛住。
            session.execute(text("SET LOCAL lock_timeout = '5s'"))
            pid = session.scalar(text("SELECT pg_backend_pid()"))
            assert isinstance(pid, int)
            pid_queue.put(pid)
            saved = SqlAlchemyWorkspaceRepository(session).save(
                original.rename(interviewee_name=IntervieweeName(value="後寫入"))
            )
            session.commit()
            return saved

    with ThreadPoolExecutor(max_workers=1) as executor:
        with Session(pg_engine) as first:
            assert SqlAlchemyWorkspaceRepository(first).save(
                original.rename(interviewee_name=IntervieweeName(value="先寫入"))
            )
            pending = executor.submit(competing_rename)
            pid = pid_queue.get(timeout=5)
            deadline = monotonic() + 3
            while True:
                with pg_engine.connect() as lock_observer:
                    waiting = lock_observer.scalar(
                        text(
                            "SELECT wait_event_type FROM pg_stat_activity "
                            "WHERE pid=:pid"
                        ),
                        {"pid": pid},
                    )
                if waiting == "Lock":
                    break
                assert monotonic() < deadline, "Second writer did not wait on row lock"
                sleep(0.01)
            assert not pending.done()
            first.commit()
        assert pending.result(timeout=5)

    with Session(pg_engine) as observer:
        saved = SqlAlchemyWorkspaceRepository(observer).get(original.id)
        assert saved is not None and saved.interviewee_name.value == "後寫入"
        assert (
            len(SqlAlchemyWorkspaceRepository(observer).list_page(limit=2, after=None))
            == 1
        )


def test_migration_downgrade_and_upgrade_recreate_schema(pg_engine: Engine) -> None:
    """在專用空 schema 降版再升版，資料表與 metadata 保持一致。"""
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        command.downgrade(config, "base")
        assert "workspaces" not in inspect(connection).get_table_names()
        command.upgrade(config, "head")
        assert "workspaces" in inspect(connection).get_table_names()
        command.check(config)
