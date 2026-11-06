"""Workspace 結果的領域映射與繼承契約。"""

from uuid import UUID

import pytest

from caliburn.modules.workspace.application.results import (
    CreateWorkspaceResult,
    WorkspaceResult,
)
from caliburn.modules.workspace.domain.interviewee_name import IntervieweeName
from caliburn.modules.workspace.domain.workspace import Workspace


@pytest.mark.parametrize("result_type", [WorkspaceResult, CreateWorkspaceResult])
def test_mapping_preserves_identity_name_and_result_type(
    result_type: type[WorkspaceResult],
) -> None:
    """映射保留 ID、原姓名，並建立呼叫端指定的結果型別。"""
    workspace_id = UUID("0199a000-0000-7000-8000-000000000001")
    workspace = Workspace(
        id=workspace_id,
        interviewee_name=IntervieweeName(value=" 王 小明 "),
    )

    result = result_type.from_workspace(workspace)

    assert type(result) is result_type
    assert result.model_dump() == {
        "workspace_id": workspace_id,
        "interviewee_name": " 王 小明 ",
    }
