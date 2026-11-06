"""Workspace 的客戶端生成契約。"""

from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


def test_workspace_operations_have_stable_business_names() -> None:
    """方法名不隨 HTTP handler 的內部名稱變動，且跨模組唯一。"""
    schema = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    ).openapi()
    paths = schema["paths"]
    for path, method, operation_id in (
        ("/workspaces", "post", "create_workspace"),
        ("/workspaces", "get", "list_workspaces"),
        ("/workspaces/{workspace_id}", "get", "get_workspace"),
        ("/workspaces/{workspace_id}", "patch", "rename_workspace"),
        ("/workspaces/{workspace_id}", "delete", "delete_workspace"),
    ):
        assert paths[path][method]["operationId"] == operation_id
    operation_ids = [
        operation["operationId"]
        for operations in paths.values()
        for method, operation in operations.items()
        if method in {"get", "post", "patch", "put", "delete"}
    ]
    assert len(operation_ids) == len(set(operation_ids))


def test_workspace_creation_location_and_empty_deletion_are_documented() -> None:
    """建立回新資源位址；整份刪除沒有 JSON body。"""
    paths = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://localhost:1/unreachable",
    ).openapi()["paths"]
    created = paths["/workspaces"]["post"]["responses"]["201"]
    assert created["headers"]["Location"]["schema"]["type"] == "string"
    deleted = paths["/workspaces/{workspace_id}"]["delete"]["responses"]["204"]
    assert "content" not in deleted
