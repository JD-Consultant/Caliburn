"""建立用例的提交邊界、失敗傳遞與輸入規則測試。"""

import pytest
from pydantic import ValidationError

from caliburn.modules.workspace.application.results import (
    CreateWorkspaceResult,
    WorkspaceResult,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.domain.interviewee_name import (
    IntervieweeName,
)
from caliburn.shared.application.base_dto import BaseDTO

from .fakes import FakeUnitOfWork, FakeUnitOfWorkFactory


def test_creates_workspace_and_returns_committed_values() -> None:
    """成功結果與提交的 UUIDv7、姓名一致，並已退出 UoW。"""
    factory = FakeUnitOfWorkFactory()

    result = WorkspaceService(factory).create(interviewee_name=" 王 小明 ")

    assert isinstance(result, BaseDTO)
    assert isinstance(result, CreateWorkspaceResult)
    assert isinstance(result, WorkspaceResult)
    assert result.workspace_id.version == 7
    assert result.interviewee_name == " 王 小明 "
    saved = factory.saved[result.workspace_id]
    assert saved.id == result.workspace_id
    assert isinstance(saved.interviewee_name, IntervieweeName)
    assert saved.interviewee_name.value == " 王 小明 "
    assert len(factory.saved) == 1
    assert factory.units[0].commit_attempts == 1
    assert factory.units[0].closed


def test_same_name_creates_separate_workspaces_and_units_of_work() -> None:
    """同一服務重複建立各用獨立 UoW，不因同名合併 Workspace。"""
    factory = FakeUnitOfWorkFactory()
    service = WorkspaceService(factory)

    first = service.create(interviewee_name="王小明")
    second = service.create(interviewee_name="王小明")

    assert first.workspace_id != second.workspace_id
    assert first.workspace_id.version == second.workspace_id.version == 7
    assert len(factory.saved) == 2
    assert len(factory.units) == 2
    assert factory.units[0] is not factory.units[1]
    assert all(unit.closed and unit.committed for unit in factory.units)


@pytest.mark.parametrize("name", ["", " \t\u3000"])
def test_invalid_name_is_rejected_before_opening_a_unit_of_work(name: str) -> None:
    """Domain 拒絕空白姓名時，不開啟交易或保存資料。"""
    factory = FakeUnitOfWorkFactory()

    with pytest.raises(ValidationError) as error:
        WorkspaceService(factory).create(interviewee_name=name)

    assert error.value.errors()[0]["type"] == "value_error"
    assert factory.units == []
    assert factory.saved == {}


def test_add_failure_does_not_commit_or_return_success() -> None:
    """新增失敗原樣傳出，不重試或提交，並退出未完成工作單元。"""
    failure = RuntimeError("add failed")
    unit = FakeUnitOfWork({}, add_error=failure)

    with pytest.raises(RuntimeError) as error:
        WorkspaceService(lambda: unit).create(interviewee_name="王小明")

    assert error.value is failure
    assert unit.workspaces.add_attempts == 1
    assert unit.commit_attempts == 0
    assert unit.saved == {}
    assert unit.closed


def test_commit_failure_is_not_retried_or_returned_as_success() -> None:
    """提交失敗傳出原錯誤，不自動重試，也不回成功結果。"""
    failure = RuntimeError("commit failed")
    unit = FakeUnitOfWork({}, commit_error=failure)

    with pytest.raises(RuntimeError) as error:
        WorkspaceService(lambda: unit).create(interviewee_name="王小明")

    assert error.value is failure
    assert unit.commit_attempts == 1
    assert unit.saved == {}
    assert unit.closed


def test_lost_commit_reply_does_not_repeat_or_erase_the_write() -> None:
    """提交回覆遺失仍可能已保存；用例傳出錯誤，不重建或刪除資料。"""
    failure = OSError("commit acknowledgement lost")
    unit = FakeUnitOfWork({}, commit_error=failure, commit_before_error=True)

    with pytest.raises(OSError) as error:
        WorkspaceService(lambda: unit).create(interviewee_name="王小明")

    assert error.value is failure
    assert unit.commit_attempts == 1
    assert len(unit.saved) == 1
    assert next(iter(unit.saved.values())).interviewee_name.value == "王小明"
    assert unit.closed


def test_enter_failure_is_propagated_without_commit() -> None:
    """進入工作單元失敗時原樣傳出，不嘗試保存或提交。"""
    failure = OSError("connection unavailable")
    unit = FakeUnitOfWork({}, enter_error=failure)

    with pytest.raises(OSError) as error:
        WorkspaceService(lambda: unit).create(interviewee_name="王小明")

    assert error.value is failure
    assert unit.commit_attempts == 0
    assert unit.saved == {}


def test_exit_failure_does_not_return_success_or_undo_confirmed_commit() -> None:
    """退出失敗不回成功，但不把已確認的提交誤當作未保存。"""
    failure = OSError("cleanup failed")
    unit = FakeUnitOfWork({}, exit_error=failure)

    with pytest.raises(OSError) as error:
        WorkspaceService(lambda: unit).create(interviewee_name="王小明")

    assert error.value is failure
    assert unit.commit_attempts == 1
    assert len(unit.saved) == 1
    assert unit.committed
