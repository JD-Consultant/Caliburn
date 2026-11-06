"""從正式 initializer 驗模型實收宣告，避免 Pydantic 可驗卻無法外送。"""

import json

import pytest

from caliburn.bundles.job_description.write_tools import create_write_tools
from caliburn.modules.agent.infrastructure.openai.request_initialization import (
    OpenAIRequestInitializer,
)
from tests.unit.bundles.job_description.test_write_tools import Harness, payload
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST


def test_write_tool_declarations_use_supported_strict_schema() -> None:
    initializer = OpenAIRequestInitializer(MODEL_REQUEST, create_write_tools())
    state = initializer.initialize({"turn_input": "測試宣告"})
    declarations = list(state["model_request"]["tools"])
    assert len(declarations) == 6

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

    for declaration in declarations:
        assert declaration["type"] == "function"
        assert declaration["strict"] is True
        parameters = declaration["parameters"]
        assert isinstance(parameters, dict)
        assert parameters["type"] == "object"
        assert "anyOf" not in parameters
        inspect(parameters)
        encoded = json.dumps(parameters)
        assert not any(
            f'"{field}"' in encoded
            for field in (
                "workspace_id",
                "expected_version",
                "turn_id",
                "runtime",
                "published_version",
            )
        )


@pytest.mark.parametrize("value", [True, False, "1", 1.5])
def test_non_integer_levels_are_rejected_without_coercion(value: object) -> None:
    harness = Harness()
    output = payload(
        harness.invoke(
            "revise_jd_profile",
            {"changes": [{"action": "set_baseline_competency_level", "value": value}]},
        )
    )
    assert output["code"] == "invalid_arguments"
    assert harness.store.commits == 0
