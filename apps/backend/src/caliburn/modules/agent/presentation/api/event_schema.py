"""將具名 Agent 事件投影為 OpenAPI SSE itemSchema，保留原生 wire 格式。"""

from typing import Any

from fastapi import FastAPI
from pydantic import TypeAdapter

from caliburn.modules.agent.application.events import TurnEvent

AGENT_EVENTS_OPERATION_ID = "stream_agent_turn"


def install_agent_event_schema(app: FastAPI) -> None:
    """在 Host routes 組裝完成後，補上原生 ServerSentEvent 未推導的 payload。"""
    original_openapi = app.openapi
    app.openapi_schema = None

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is not None:
            return app.openapi_schema
        document = original_openapi()
        # 原生成器先快取；只在 Agent 契約完整補齊後才交付快取。
        app.openapi_schema = None
        event_schema = TypeAdapter(TurnEvent).json_schema(
            mode="serialization", ref_template="#/components/schemas/{model}"
        )
        definitions = event_schema.pop("$defs")
        definitions["TurnEvent"] = event_schema
        components = document["components"]["schemas"]
        for name, definition in definitions.items():
            if name in components and components[name] != definition:
                raise ValueError(f"Agent event schema conflicts with {name}")
            components[name] = definition

        # JSON envelope 給前端驗證；SSE data 本身仍為含 JSON 的字串。
        variants = []
        for variant in event_schema["oneOf"]:
            name = variant["$ref"].removeprefix("#/components/schemas/")
            envelope = definitions[name]
            variants.append(
                {
                    "type": "object",
                    "required": envelope["required"],
                    "properties": {
                        "event": envelope["properties"]["event"],
                        "data": {
                            "type": "string",
                            "contentMediaType": "application/json",
                            "contentSchema": envelope["properties"]["data"],
                        },
                    },
                }
            )
        for path in document["paths"].values():
            operation = path.get("get", {})
            if operation.get("operationId") == AGENT_EVENTS_OPERATION_ID:
                operation["responses"]["200"]["content"]["text/event-stream"][
                    "itemSchema"
                ] = {"oneOf": variants}
                app.openapi_schema = document
                return document
        raise ValueError("Agent event route must be installed before its schema")

    # FastAPI 官方 OpenAPI 擴充接點；只替換此 app 的生成方法。
    app.openapi = openapi  # type: ignore[method-assign]
