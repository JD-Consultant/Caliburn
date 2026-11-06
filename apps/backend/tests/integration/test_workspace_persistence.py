"""以隔離 PostgreSQL 驗證 Workspace 保存與交易邊界。"""

import sys
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, insert, select
from sqlalchemy.exc import IntegrityError, InvalidRequestError
from sqlalchemy.orm import Session, sessionmaker

from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace
from caliburn.modules.workspace.infrastructure.persistence.orm_models import (
    WorkspaceRow,
)
from caliburn.modules.workspace.infrastructure.persistence.repository import (
    SqlAlchemyWorkspaceRepository,
)
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)


def workspace(name: str = "王小明", *, identifier: UUID | None = None) -> Workspace:
    """以合成姓名建立測例需要的有效聚合。"""
    return Workspace(
        id=identifier or uuid4(), interviewee_name=IntervieweeName(value=name)
    )


def test_database_factory_does_not_connect_or_create_schema() -> None:
    """建立連線池不應連線或偷偷建表。"""
    engine = create_database_engine("postgresql+psycopg://localhost:1/unreachable")
    try:
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        with create_session_factory(engine)() as session:
            assert not session.in_transaction()
    finally:
        engine.dispose()


@pytest.mark.parametrize("url", ["sqlite://", "postgresql+psycopg2://localhost/test"])
def test_database_factory_rejects_unsupported_drivers(url: str) -> None:
    """錯誤 driver 應在建立資源前拒絕，不暗中選用另一套儲存。"""
    with pytest.raises(ValueError, match="postgresql\\+psycopg"):
        create_database_engine(url)


def test_unit_of_work_opens_lazily_and_closes_its_session() -> None:
    """工作單元取得 Session 不立即連線，退出後不可再使用同一 Session。"""
    engine = create_database_engine("postgresql+psycopg://localhost:1/unreachable")
    session = create_session_factory(engine)()
    try:
        with SqlAlchemyWorkspaceUnitOfWork(lambda: session) as uow:
            assert isinstance(uow.workspaces, SqlAlchemyWorkspaceRepository)
            assert not session.in_transaction()
        with pytest.raises(InvalidRequestError):
            session.scalar(select(WorkspaceRow.id))
    finally:
        engine.dispose()


def test_unit_of_work_rejects_operations_outside_context() -> None:
    """取得 Repository 與提交都必須在有效工作單元範圍內。"""
    engine = create_database_engine("postgresql+psycopg://localhost:1/unreachable")
    uow = SqlAlchemyWorkspaceUnitOfWork(create_session_factory(engine))
    try:
        with pytest.raises(RuntimeError, match="目前未啟用"):
            uow.commit()
        with pytest.raises(RuntimeError, match="目前未啟用"):
            _ = uow.workspaces
        with uow:
            pass
        with pytest.raises(RuntimeError, match="目前未啟用"):
            _ = uow.workspaces
    finally:
        engine.dispose()


def test_repository_preserves_id_and_name_across_sessions(pg_engine: Engine) -> None:
    """提交後由獨立 Session 取得相同內容且不合併同名聚合。"""
    first = workspace("  林 小明\t")
    second = workspace("  林 小明\t")
    session_factory = create_session_factory(pg_engine)

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(first)
        uow.workspaces.add(second)
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        saved = uow.workspaces.get(first.id)
        assert saved is not None
        assert saved.id == first.id
        assert saved.interviewee_name.value == "  林 小明\t"
        assert saved is not first
        assert uow.workspaces.get(second.id) is not None
        assert uow.workspaces.get(uuid4()) is None

    assert saved.interviewee_name.value == "  林 小明\t"


def test_repository_does_not_commit_on_add_or_save(pg_engine: Engine) -> None:
    """Repository 的寫入不應在呼叫者提交前向其他交易可見。"""
    original = workspace("原姓名")
    with Session(pg_engine) as writer, Session(pg_engine) as observer:
        repository = SqlAlchemyWorkspaceRepository(writer)
        repository.add(original)
        writer.flush()
        assert observer.get(WorkspaceRow, original.id) is None
        writer.commit()

        renamed = workspace("新姓名", identifier=original.id)
        assert repository.save(renamed)
        observed = observer.get(WorkspaceRow, original.id)
        assert observed is not None
        assert observed.interviewee_name == "原姓名"


def test_uncommitted_exit_rolls_back_flushed_changes(pg_engine: Engine) -> None:
    """正常退出仍須回滾已送入資料庫但尚未提交的新增。"""
    original = workspace()
    session_factory = create_session_factory(pg_engine)

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(original)
        assert uow.workspaces.get(original.id) is not None

    with Session(pg_engine) as observer:
        assert observer.get(WorkspaceRow, original.id) is None


def test_exception_exit_rolls_back_and_propagates(pg_engine: Engine) -> None:
    """業務例外不可吞掉，也不可殘留已送出的更新。"""
    original = workspace()
    session_factory = create_session_factory(pg_engine)

    with pytest.raises(RuntimeError, match="operation failed"):
        with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
            uow.workspaces.add(original)
            assert uow.workspaces.get(original.id) is not None
            raise RuntimeError("operation failed")

    with Session(pg_engine) as observer:
        assert observer.get(WorkspaceRow, original.id) is None


def test_duplicate_id_fails_without_overwriting_original(pg_engine: Engine) -> None:
    """相同 ID 新增應受主鍵拒絕，不能變成覆寫。"""
    original = workspace("原姓名")
    session_factory = create_session_factory(pg_engine)
    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(original)
        uow.commit()

    with pytest.raises(IntegrityError):
        with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
            uow.workspaces.add(workspace("覆寫姓名", identifier=original.id))
            uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        saved = uow.workspaces.get(original.id)
        assert saved is not None
        assert saved.interviewee_name.value == "原姓名"


def test_list_page_uses_descending_uuid_and_deleted_cursor(pg_engine: Engine) -> None:
    """分頁限量按 ID 降冪，游標列被刪除仍可接續。"""
    session_factory = create_session_factory(pg_engine)
    identifiers = [UUID(int=value) for value in (1, 2, 3, 4)]
    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        for identifier in identifiers:
            uow.workspaces.add(workspace(identifier=identifier))
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        page = uow.workspaces.list_page(limit=2, after=None)
        assert [item.id for item in page] == [UUID(int=4), UUID(int=3)]
        assert uow.workspaces.delete(UUID(int=3))
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        page = uow.workspaces.list_page(limit=2, after=UUID(int=3))
        assert [item.id for item in page] == [UUID(int=2), UUID(int=1)]
        assert uow.workspaces.list_page(limit=2, after=UUID(int=1)) == []


def test_save_updates_only_existing_workspace(pg_engine: Engine) -> None:
    """改名保留身分且不影響另一筆，不存在的更新不能插入。"""
    original, other = workspace("原姓名"), workspace("另一人")
    missing = workspace("不存在")
    session_factory = create_session_factory(pg_engine)
    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(original)
        uow.workspaces.add(other)
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        assert uow.workspaces.save(workspace(" 新姓名 ", identifier=original.id))
        assert not uow.workspaces.save(missing)
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        saved = uow.workspaces.get(original.id)
        unaffected = uow.workspaces.get(other.id)
        assert saved is not None and saved.interviewee_name.value == " 新姓名 "
        assert unaffected is not None and unaffected.interviewee_name.value == "另一人"
        assert uow.workspaces.get(missing.id) is None


def test_delete_isolated_and_repeatable_without_implicit_commit(
    pg_engine: Engine,
) -> None:
    """刪除只作用於指定 ID，未提交不生效且重複刪除回報不存在。"""
    original, other = workspace(), workspace()
    session_factory = create_session_factory(pg_engine)
    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(original)
        uow.workspaces.add(other)
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        assert uow.workspaces.delete(original.id)
        with Session(pg_engine) as observer:
            assert observer.get(WorkspaceRow, original.id) is not None

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        assert uow.workspaces.get(original.id) is not None
        assert uow.workspaces.delete(original.id)
        assert not uow.workspaces.delete(original.id)
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        assert uow.workspaces.get(original.id) is None
        assert uow.workspaces.get(other.id) is not None


def test_stale_snapshot_cannot_resurrect_deleted_workspace(pg_engine: Engine) -> None:
    """獨立交易刪除後，較早讀取的快照不能由 save 復活。"""
    original = workspace()
    session_factory = create_session_factory(pg_engine)
    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(original)
        uow.commit()

    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as stale_uow:
        stale = stale_uow.workspaces.get(original.id)
        assert stale is not None
        with SqlAlchemyWorkspaceUnitOfWork(session_factory) as deleting_uow:
            assert deleting_uow.workspaces.delete(original.id)
            deleting_uow.commit()
        assert not stale_uow.workspaces.save(workspace("過時改名", identifier=stale.id))
        stale_uow.commit()

    with Session(pg_engine) as observer:
        assert observer.get(WorkspaceRow, original.id) is None


def test_database_rejects_every_python_whitespace_name(pg_engine: Engine) -> None:
    """資料庫須拒絕 Python 判定的所有全空白值與空字串。"""
    whitespace = [
        chr(codepoint)
        for codepoint in range(sys.maxunicode + 1)
        if chr(codepoint).isspace()
    ]
    for value in ["", *whitespace, "".join(whitespace)]:
        with Session(pg_engine) as session:
            with pytest.raises(IntegrityError):
                session.execute(
                    insert(WorkspaceRow).values(id=uuid4(), interviewee_name=value)
                )
                session.commit()


def test_database_rejects_null_name(pg_engine: Engine) -> None:
    """直接寫資料庫也不能繞過姓名必填約束。"""
    with Session(pg_engine) as session:
        with pytest.raises(IntegrityError):
            session.execute(
                insert(WorkspaceRow).values(id=uuid4(), interviewee_name=None)
            )
            session.commit()


@pytest.mark.parametrize(
    "name",
    ["\u200b", "\ufeff", " \u200b\t", "甲" * 10000],
    ids=["zero_width_space", "byte_order_mark", "mixed_whitespace", "long_name"],
)
def test_database_preserves_valid_names_without_extra_policy(
    pg_engine: Engine, name: str
) -> None:
    """非 Python 空白與長姓名不可被資料庫自行修整或拒絕。"""
    original = workspace(name)
    session_factory = create_session_factory(pg_engine)
    with SqlAlchemyWorkspaceUnitOfWork(session_factory) as uow:
        uow.workspaces.add(original)
        uow.commit()
    with Session(pg_engine) as observer:
        assert observer.scalar(select(WorkspaceRow.interviewee_name)) == name


@pytest.mark.parametrize("exit_mode", ["commit", "rollback", "error"])
def test_unit_of_work_closes_session_on_every_exit(
    pg_engine: Engine, exit_mode: str
) -> None:
    """正常、未提交與異常退出都釋放並關閉其 Session。"""
    opened_sessions: list[Session] = []
    factory = sessionmaker(pg_engine, close_resets_only=False)

    def open_session() -> Session:
        session = factory()
        opened_sessions.append(session)
        return session

    try:
        with SqlAlchemyWorkspaceUnitOfWork(open_session) as uow:
            uow.workspaces.add(workspace())
            if exit_mode == "commit":
                uow.commit()
            elif exit_mode == "error":
                raise RuntimeError("operation failed")
    except RuntimeError:
        if exit_mode != "error":
            raise

    assert len(opened_sessions) == 1
    with pytest.raises(InvalidRequestError):
        opened_sessions[0].scalar(select(WorkspaceRow.id))
