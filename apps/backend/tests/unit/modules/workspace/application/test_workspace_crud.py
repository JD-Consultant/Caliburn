"""Workspace 查詢、分頁、改名與刪除的用例契約。"""

from collections.abc import Callable
from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.workspace.application.errors import (
    InvalidWorkspacePaginationError,
    WorkspaceNotFoundError,
)
from caliburn.modules.workspace.application.results import (
    WorkspacePage,
    WorkspaceResult,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.modules.workspace.domain.workspace import Workspace

from .fakes import FakeUnitOfWork, FakeUnitOfWorkFactory

FIRST_ID = UUID("0199a000-0000-7000-8000-000000000001")
SECOND_ID = UUID("0199a000-0000-7000-8000-000000000002")
THIRD_ID = UUID("0199a000-0000-7000-8000-000000000003")


def workspace(identity: UUID = FIRST_ID, name: str = " 王 小明 ") -> Workspace:
    return Workspace(id=identity, interviewee_name=IntervieweeName(value=name))


def test_service_reuses_one_instance_with_independent_crud_units() -> None:
    """同一服務可連續完成 CRUD，各次呼叫分別取得並釋放工作單元。"""
    factory = FakeUnitOfWorkFactory()
    service = WorkspaceService(factory)

    created = service.create(interviewee_name="原名")
    found = service.get(workspace_id=created.workspace_id)
    page = service.list()
    renamed = service.rename(workspace_id=created.workspace_id, interviewee_name="新名")
    service.delete(workspace_id=created.workspace_id)

    assert found.workspace_id == created.workspace_id
    assert found.interviewee_name == "原名"
    assert tuple(item.workspace_id for item in page.items) == (created.workspace_id,)
    assert page.items[0].interviewee_name == "原名"
    assert renamed.workspace_id == created.workspace_id
    assert renamed.interviewee_name == "新名"
    assert factory.saved == {}
    assert len(factory.units) == 5
    assert len({id(unit) for unit in factory.units}) == 5
    assert [unit.commit_attempts for unit in factory.units] == [1, 0, 0, 1, 1]
    assert all(unit.closed for unit in factory.units)


def test_service_recovers_with_a_new_unit_after_failed_commit() -> None:
    """改名提交失敗後，同一服務仍能讀回原名並在新工作單元成功改名。"""
    factory = FakeUnitOfWorkFactory({FIRST_ID: workspace(name="原名")})
    failure = OSError("commit failed")

    def unit_of_work() -> FakeUnitOfWork:
        unit = factory()
        if len(factory.units) == 1:
            unit.commit_error = failure
        return unit

    service = WorkspaceService(unit_of_work)

    with pytest.raises(OSError) as error:
        service.rename(workspace_id=FIRST_ID, interviewee_name="未提交姓名")

    assert error.value is failure
    assert len(factory.units) == 1
    assert factory.units[0].closed
    assert service.get(workspace_id=FIRST_ID).interviewee_name == "原名"

    renamed = service.rename(workspace_id=FIRST_ID, interviewee_name="新名")

    assert renamed.workspace_id == FIRST_ID
    assert renamed.interviewee_name == "新名"
    assert factory.saved[FIRST_ID].interviewee_name.value == "新名"
    assert len(factory.units) == 3
    assert len({id(unit) for unit in factory.units}) == 3
    assert [unit.commit_attempts for unit in factory.units] == [1, 0, 1]
    assert all(unit.closed for unit in factory.units)


def test_get_returns_plain_values_without_committing() -> None:
    """查詢回傳不可變結果與原姓名，並在未提交下釋放工作單元。"""
    factory = FakeUnitOfWorkFactory({FIRST_ID: workspace()})

    result = WorkspaceService(factory).get(workspace_id=FIRST_ID)

    assert isinstance(result, WorkspaceResult)
    assert result.workspace_id == FIRST_ID
    assert result.interviewee_name == " 王 小明 "
    assert factory.units[0].commit_attempts == 0
    assert factory.units[0].closed


def test_missing_workspace_is_distinct_from_storage_failure() -> None:
    """查無資料回具名應用錯誤與請求 ID，不提交交易。"""
    factory = FakeUnitOfWorkFactory()

    with pytest.raises(WorkspaceNotFoundError) as error:
        WorkspaceService(factory).get(workspace_id=FIRST_ID)

    assert error.value.workspace_id == FIRST_ID
    assert factory.units[0].commit_attempts == 0
    assert factory.units[0].closed


def test_listing_requests_one_extra_row_and_returns_last_visible_cursor() -> None:
    """分頁只取上限加一，游標取本頁末筆而非探測下一筆。"""
    factory = FakeUnitOfWorkFactory(
        {identity: workspace(identity) for identity in (FIRST_ID, SECOND_ID, THIRD_ID)}
    )

    page = WorkspaceService(factory).list(limit=2)

    assert tuple(item.workspace_id for item in page.items) == (THIRD_ID, SECOND_ID)
    assert page.next_cursor == SECOND_ID
    assert page.items[0].interviewee_name == " 王 小明 "
    assert factory.units[0].workspaces.page_requests == [(3, None)]
    assert factory.units[0].commit_attempts == 0
    assert factory.units[0].closed


@pytest.mark.parametrize("count", [0, 1, 2])
def test_listing_without_an_extra_row_has_no_next_cursor(count: int) -> None:
    """空頁、未滿頁與恰好滿頁都不虛構下一頁游標。"""
    identities = (FIRST_ID, SECOND_ID)[:count]
    factory = FakeUnitOfWorkFactory(
        {identity: workspace(identity) for identity in identities}
    )

    page = WorkspaceService(factory).list(limit=2)

    assert len(page.items) == count
    assert page.next_cursor is None


def test_listing_passes_cursor_and_probe_limit_to_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """游標原樣交給 Repository，取上限加一並轉成分頁結果。"""
    unit = FakeUnitOfWork({})
    requests: list[tuple[int, UUID | None]] = []

    def list_page(*, limit: int, after: UUID | None) -> list[Workspace]:
        requests.append((limit, after))
        return [workspace()]

    monkeypatch.setattr(unit.workspaces, "list_page", list_page)

    page = WorkspaceService(lambda: unit).list(limit=1, after=SECOND_ID)

    assert requests == [(2, SECOND_ID)]
    assert tuple(item.workspace_id for item in page.items) == (FIRST_ID,)
    assert page.items[0].interviewee_name == " 王 小明 "
    assert page.next_cursor is None


def test_default_page_limit_is_bounded_to_twenty_items() -> None:
    """省略上限時每頁最多二十筆，額外一筆只用於判定下一頁。"""
    factory = FakeUnitOfWorkFactory(
        {UUID(int=index): workspace(UUID(int=index)) for index in range(1, 23)}
    )

    page = WorkspaceService(factory).list()

    assert len(page.items) == 20
    assert page.items[0].workspace_id == UUID(int=22)
    assert page.next_cursor == UUID(int=3)
    assert factory.units[0].workspaces.page_requests == [(21, None)]


def test_largest_supported_page_limit_is_accepted() -> None:
    """允許上限一百筆，Repository 僅收到一百零一筆的有界查詢。"""
    factory = FakeUnitOfWorkFactory()

    assert WorkspaceService(factory).list(limit=100).items == ()
    assert factory.units[0].workspaces.page_requests == [(101, None)]


@pytest.mark.parametrize("limit", [0, -1, 101, True, "20", 1.5, None])
def test_invalid_page_limit_is_rejected_before_opening_a_unit(limit: object) -> None:
    """無效頁數上限在開交易前拒絕，避免隱式轉型或無界讀取。"""
    factory = FakeUnitOfWorkFactory()

    with pytest.raises(InvalidWorkspacePaginationError):
        WorkspaceService(factory).list(limit=cast(int, limit))

    assert factory.units == []


@pytest.mark.parametrize("after", [str(FIRST_ID), 1, False])
def test_invalid_cursor_is_rejected_before_opening_a_unit(after: object) -> None:
    """Application 要求 UUID 游標，不把外部字串解析責任帶入用例。"""
    factory = FakeUnitOfWorkFactory()

    with pytest.raises(InvalidWorkspacePaginationError):
        WorkspaceService(factory).list(after=cast(UUID, after))

    assert factory.units == []


def test_result_page_and_items_are_immutable() -> None:
    """頁面以 tuple 保存不可變 DTO，不能直接更換游標或項目姓名。"""
    factory = FakeUnitOfWorkFactory({FIRST_ID: workspace()})
    page = WorkspaceService(factory).list()

    assert isinstance(page, WorkspacePage)
    assert isinstance(page.items, tuple)
    with pytest.raises(ValidationError):
        page.__setattr__("next_cursor", SECOND_ID)
    with pytest.raises(ValidationError):
        page.items[0].__setattr__("interviewee_name", "另一個姓名")


def test_rename_commits_new_snapshot_and_preserves_other_workspaces() -> None:
    """改名提交同 ID 新姓名，原快照與其他 Workspace 不受影響。"""
    original = workspace()
    factory = FakeUnitOfWorkFactory(
        {FIRST_ID: original, SECOND_ID: workspace(SECOND_ID, "另一人")}
    )

    result = WorkspaceService(factory).rename(
        workspace_id=FIRST_ID, interviewee_name=" 新 姓名 "
    )

    assert result.workspace_id == FIRST_ID
    assert result.interviewee_name == " 新 姓名 "
    assert factory.saved[FIRST_ID].interviewee_name.value == " 新 姓名 "
    assert factory.saved[FIRST_ID] is not original
    assert original.interviewee_name.value == " 王 小明 "
    assert factory.saved[SECOND_ID].interviewee_name.value == "另一人"
    assert factory.units[0].workspaces.add_attempts == 0
    assert factory.units[0].commit_attempts == 1
    assert factory.units[0].closed


@pytest.mark.parametrize("name", ["", "\t\n", "\u3000", "\x1c\u00a0"])
def test_rename_validates_before_reading_workspace(name: str) -> None:
    """改名與建立共用姓名規則，無效姓名不開啟工作單元。"""
    factory = FakeUnitOfWorkFactory()

    with pytest.raises(ValidationError):
        WorkspaceService(factory).rename(workspace_id=FIRST_ID, interviewee_name=name)

    assert factory.units == []


def test_rename_missing_workspace_does_not_create_or_commit() -> None:
    """改名缺少目標時回不存在，不改用新增或提交。"""
    factory = FakeUnitOfWorkFactory()

    with pytest.raises(WorkspaceNotFoundError) as error:
        WorkspaceService(factory).rename(
            workspace_id=FIRST_ID, interviewee_name="新姓名"
        )

    assert error.value.workspace_id == FIRST_ID
    assert factory.saved == {}
    assert factory.units[0].workspaces.add_attempts == 0
    assert factory.units[0].workspaces.save_attempts == 0
    assert factory.units[0].commit_attempts == 0
    assert factory.units[0].closed


def test_deleted_workspace_is_not_recreated_by_an_earlier_rename(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """讀取後更新前已刪除的目標仍回不存在，不能被舊快照復活。"""
    unit = FakeUnitOfWork({FIRST_ID: workspace()})

    def remove_before_save(updated: Workspace) -> bool:
        unit.saved.pop(updated.id)
        return False

    monkeypatch.setattr(unit.workspaces, "save", remove_before_save)

    with pytest.raises(WorkspaceNotFoundError):
        WorkspaceService(lambda: unit).rename(
            workspace_id=FIRST_ID, interviewee_name="新姓名"
        )

    assert unit.saved == {}
    assert unit.workspaces.add_attempts == 0
    assert unit.commit_attempts == 0
    assert unit.closed


def test_delete_commits_absence_and_preserves_other_workspaces() -> None:
    """刪除只影響目標，確認提交並退出後回傳 None。"""
    factory = FakeUnitOfWorkFactory(
        {FIRST_ID: workspace(), SECOND_ID: workspace(SECOND_ID, "另一人")}
    )

    WorkspaceService(factory).delete(workspace_id=FIRST_ID)

    assert FIRST_ID not in factory.saved
    assert factory.saved[SECOND_ID].interviewee_name.value == "另一人"
    assert factory.units[0].commit_attempts == 1
    assert factory.units[0].closed


def test_repeated_deletion_commits_each_request_and_uses_a_new_unit() -> None:
    """重複刪除仍成功，每次都有獨立工作單元與明確提交。"""
    factory = FakeUnitOfWorkFactory({FIRST_ID: workspace()})
    service = WorkspaceService(factory)

    service.delete(workspace_id=FIRST_ID)
    service.delete(workspace_id=FIRST_ID)

    assert factory.saved == {}
    assert len(factory.units) == 2
    assert factory.units[0] is not factory.units[1]
    assert all(unit.commit_attempts == 1 and unit.closed for unit in factory.units)


def query_get(unit: FakeUnitOfWork) -> object:
    return WorkspaceService(lambda: unit).get(workspace_id=FIRST_ID)


def query_list(unit: FakeUnitOfWork) -> object:
    return WorkspaceService(lambda: unit).list()


@pytest.mark.parametrize("query", [query_get, query_list])
def test_queries_propagate_storage_failure_without_commit(
    query: Callable[[FakeUnitOfWork], object],
) -> None:
    """讀取故障傳出原例外，不誤報不存在或空清單，也不提交。"""
    unit = FakeUnitOfWork({FIRST_ID: workspace()})
    failure = OSError("storage read failed")
    unit.workspaces.read_error = failure

    with pytest.raises(OSError) as error:
        query(unit)

    assert error.value is failure
    assert unit.commit_attempts == 0
    assert unit.closed


def rename(unit: FakeUnitOfWork) -> object:
    return WorkspaceService(lambda: unit).rename(
        workspace_id=FIRST_ID, interviewee_name="新姓名"
    )


def delete(unit: FakeUnitOfWork) -> object:
    WorkspaceService(lambda: unit).delete(workspace_id=FIRST_ID)
    return None


@pytest.mark.parametrize("command", [rename, delete])
def test_mutations_propagate_storage_failure_without_commit(
    command: Callable[[FakeUnitOfWork], object],
) -> None:
    """更新與刪除故障傳出原例外，不提交或自動重送。"""
    original = workspace()
    unit = FakeUnitOfWork({FIRST_ID: original})
    failure = OSError("storage write failed")
    unit.workspaces.write_error = failure

    with pytest.raises(OSError) as error:
        command(unit)

    assert error.value is failure
    assert unit.saved[FIRST_ID] is original
    assert unit.workspaces.save_attempts + unit.workspaces.delete_attempts == 1
    assert unit.commit_attempts == 0
    assert unit.closed


@pytest.mark.parametrize("command", [rename, delete])
def test_commit_failure_does_not_return_success_or_retry(
    command: Callable[[FakeUnitOfWork], object],
) -> None:
    """提交前故障不回成功、不重試，未提交資料保持原狀。"""
    original = workspace()
    failure = OSError("commit failed")
    unit = FakeUnitOfWork({FIRST_ID: original}, commit_error=failure)

    with pytest.raises(OSError) as error:
        command(unit)

    assert error.value is failure
    assert unit.saved[FIRST_ID] is original
    assert unit.commit_attempts == 1
    assert unit.closed


@pytest.mark.parametrize("command", [rename, delete])
@pytest.mark.parametrize("failed_stage", ["commit_reply", "exit"])
def test_confirmed_write_is_not_undone_or_reported_as_success_after_failure(
    command: Callable[[FakeUnitOfWork], object], failed_stage: str
) -> None:
    """提交回覆或退出故障仍可能已保存，不回成功、不補償或重送。"""
    original = workspace()
    failure = OSError("acknowledgement or cleanup failed")
    unit = FakeUnitOfWork(
        {FIRST_ID: original},
        commit_error=failure if failed_stage == "commit_reply" else None,
        exit_error=failure if failed_stage == "exit" else None,
        commit_before_error=True,
    )

    with pytest.raises(OSError) as error:
        command(unit)

    assert error.value is failure
    if command is rename:
        assert unit.saved[FIRST_ID].interviewee_name.value == "新姓名"
    else:
        assert FIRST_ID not in unit.saved
    assert unit.commit_attempts == 1
    assert unit.committed
    assert unit.closed
