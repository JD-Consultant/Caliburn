"""Plan 唯讀 HTTP 的正式 OpenAPI 契約。"""

from caliburn.host.app import build_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


def test_plan_exposes_only_current_read_without_agent_configuration() -> None:
    app = build_app(
        reference_configuration=HOST_REFERENCE_CONFIGURATION,
        database_url="postgresql+psycopg://unused:unused@127.0.0.1/unused_test",
    )
    schema = app.openapi()
    path = "/workspaces/{workspace_id}/plan"
    assert path in schema["paths"]
    assert set(schema["paths"][path]) == {"get"}
    assert [route for route in schema["paths"] if "/plan" in route] == [path]
    operation = schema["paths"][path]["get"]
    assert operation["operationId"] == "get_current_plan"
    assert {"200", "404", "422", "503"} <= operation["responses"].keys()
    assert operation["responses"]["503"]["headers"]["X-Request-ID"]["schema"] == {
        "type": "string"
    }
    response = schema["components"]["schemas"]["PlanResponse"]
    assert set(response["properties"]) == {"workspace_id", "version", "body"}
    assert set(response["required"]) == {"workspace_id", "version", "body"}
    assert response["properties"]["version"]["anyOf"] == [
        {"type": "integer", "minimum": 1, "maximum": 9007199254740991},
        {"type": "null"},
    ]
    assert {"type": "null"} in response["properties"]["body"]["anyOf"]
