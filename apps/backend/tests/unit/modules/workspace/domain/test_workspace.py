"""Workspace 聚合根的有效姓名與身分契約測試。"""

from typing import cast
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.modules.workspace.domain.interviewee_name import IntervieweeName
from caliburn.modules.workspace.domain.workspace import Workspace

WORKSPACE_ID = UUID("0199a000-0000-7000-8000-000000000001")
OTHER_WORKSPACE_ID = UUID("0199a000-0000-7000-8000-000000000002")


@pytest.mark.parametrize(
    "identity",
    [WORKSPACE_ID, UUID("12345678-1234-4234-8234-123456789abc")],
    ids=["uuid7", "uuid4"],
)
def test_preserves_supplied_identity_and_name(identity: UUID) -> None:
    """聚合根保留傳入 UUID 與完整姓名，不另行限制 UUID 版本。"""
    name = IntervieweeName(value=" 王 小明 ")

    workspace = Workspace(id=identity, interviewee_name=name)

    assert workspace.id == identity
    assert workspace.interviewee_name == name
    assert workspace.interviewee_name.value == " 王 小明 "


def test_rejects_invalid_nested_name() -> None:
    """從資料重建聚合時，巢狀姓名仍必須通過領域驗證。"""
    with pytest.raises(ValidationError) as error:
        Workspace.model_validate(
            {"id": WORKSPACE_ID, "interviewee_name": {"value": " \t\u3000"}}
        )

    detail = error.value.errors()[0]
    assert detail["loc"] == ("interviewee_name", "value")
    assert detail["type"] == "value_error"


def test_allows_separate_workspaces_with_the_same_name() -> None:
    """同名 Workspace 仍由 ID 區分，姓名不能用來合併身分。"""
    name = IntervieweeName(value="王小明")
    first = Workspace(id=WORKSPACE_ID, interviewee_name=name)
    second = Workspace(id=OTHER_WORKSPACE_ID, interviewee_name=name)

    assert first.interviewee_name == second.interviewee_name
    assert first != second


@pytest.mark.parametrize("identity", [None, str(WORKSPACE_ID), 42])
def test_rejects_non_uuid_identity(identity: object) -> None:
    """Workspace 限定 UUID 身分，拒絕字串或其他型別。"""
    with pytest.raises(ValidationError) as error:
        Workspace.model_validate(
            {"id": identity, "interviewee_name": IntervieweeName(value="王小明")}
        )

    detail = error.value.errors()[0]
    assert detail["loc"] == ("id",)
    assert detail["type"] == "is_instance_of"


@pytest.mark.parametrize("name", [None, 123, b"name", "王小明"])
def test_rejects_unstructured_name(name: object) -> None:
    """聚合根要求姓名值物件，不把裸字串當成已建模的姓名。"""
    with pytest.raises(ValidationError) as error:
        Workspace.model_validate({"id": WORKSPACE_ID, "interviewee_name": name})

    assert error.value.errors()[0]["loc"] == ("interviewee_name",)


def test_rejects_unknown_constructor_fields() -> None:
    """聚合根拒絕未定義的建構欄位。"""
    with pytest.raises(ValidationError) as error:
        Workspace.model_validate(
            {
                "id": WORKSPACE_ID,
                "interviewee_name": IntervieweeName(value="王小明"),
                "display_name": "不屬於此模型",
            }
        )

    detail = error.value.errors()[0]
    assert detail["loc"] == ("display_name",)
    assert detail["type"] == "extra_forbidden"


@pytest.mark.parametrize(
    ("field", "replacement"),
    [("id", OTHER_WORKSPACE_ID), ("interviewee_name", IntervieweeName(value="王大明"))],
)
def test_fields_cannot_be_reassigned(field: str, replacement: object) -> None:
    """ID 與姓名均不可直接替換，即使新值合法也拒絕。"""
    workspace = Workspace(
        id=WORKSPACE_ID, interviewee_name=IntervieweeName(value="王小明")
    )

    with pytest.raises(ValidationError) as error:
        setattr(workspace, field, replacement)

    assert error.value.errors()[0]["type"] == "frozen_field"
    assert workspace.id == WORKSPACE_ID
    assert workspace.interviewee_name.value == "王小明"


@pytest.mark.parametrize("field", ["id", "interviewee_name"])
def test_required_fields_cannot_be_deleted(field: str) -> None:
    """刪除 ID 或姓名被拒絕，聚合根必填狀態保持完整。"""
    workspace = Workspace(
        id=WORKSPACE_ID, interviewee_name=IntervieweeName(value="王小明")
    )

    with pytest.raises(ValidationError) as error:
        delattr(workspace, field)

    assert error.value.errors()[0]["type"] == "frozen_field"
    assert workspace.id == WORKSPACE_ID
    assert workspace.interviewee_name.value == "王小明"


def test_rename_returns_a_new_snapshot_with_the_same_identity() -> None:
    """改名保留 ID 與相等性，但原姓名快照不被更改。"""
    original = Workspace(
        id=WORKSPACE_ID, interviewee_name=IntervieweeName(value="王小明")
    )

    renamed = original.rename(interviewee_name=IntervieweeName(value=" 王 大明 "))

    assert renamed is not original
    assert renamed.id == WORKSPACE_ID
    assert renamed.interviewee_name.value == " 王 大明 "
    assert original.interviewee_name.value == "王小明"
    assert renamed == original
    assert hash(renamed) == hash(original)
    assert len({original, renamed}) == 1


@pytest.mark.parametrize("invalid_name", ["王大明", {"value": " \t\u3000"}])
def test_rename_validates_input_without_bypassing_construction(
    invalid_name: object,
) -> None:
    """改名仍經正常建構驗證，錯誤型別及空白資料不能繞過規則。"""
    original = Workspace(
        id=WORKSPACE_ID, interviewee_name=IntervieweeName(value="王小明")
    )

    with pytest.raises(ValidationError):
        original.rename(interviewee_name=cast(IntervieweeName, invalid_name))

    assert original.interviewee_name.value == "王小明"
