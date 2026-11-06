"""讀取宣告走正式 OpenAI 初始化器，runtime 與版本不能出現在模型參數。"""

import json

from caliburn.bundles.job_description.reading import create_read_tool
from caliburn.bundles.job_description.source_changes import create_source_changes_tool
from caliburn.modules.agent.infrastructure.openai.request_initialization import (
    OpenAIRequestInitializer,
)
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST


def test_read_tool_declarations_are_strict_provider_payloads() -> None:
    initializer = OpenAIRequestInitializer(
        MODEL_REQUEST, (create_read_tool(), create_source_changes_tool())
    )
    declarations = list(
        initializer.initialize({"turn_input": "驗讀取契約"})["model_request"]["tools"]
    )

    def inspect(value: object) -> None:
        if isinstance(value, dict):
            assert not {"oneOf", "discriminator", "$ref"}.intersection(value)
            if value.get("type") == "object":
                assert value["additionalProperties"] is False
                assert set(value["required"]) == set(value["properties"])
            for child in value.values():
                inspect(child)
        elif isinstance(value, list):
            for child in value:
                inspect(child)

    assert len(declarations) == 2
    read_tool = declarations[0]
    assert read_tool["type"] == "function"
    read_parameters = read_tool["parameters"]
    assert read_parameters is not None
    required = read_parameters["required"]
    properties = read_parameters["properties"]
    assert isinstance(required, list) and "read_ref" in required
    assert isinstance(properties, dict)
    read_ref = properties["read_ref"]
    assert {"type": "null"} in read_ref["anyOf"]
    assert "null" in read_ref["description"]
    for tool in declarations:
        assert tool["type"] == "function" and tool["strict"] is True
        inspect(tool["parameters"])
        encoded = json.dumps(tool["parameters"])
        assert not any(
            f'"{name}"' in encoded
            for name in (
                "workspace_id",
                "jd_id",
                "runtime",
                "published_version",
                "expected_version",
            )
        )
