"""模型只填查找所需欄位，插件沒有員工狀態或寫入接點。"""

import pytest
from pydantic import BaseModel

from caliburn.bundles.job_reference import create_bundle


def test_declares_only_search_and_required_nullable_task_read() -> None:
    bundle = create_bundle({})
    tools = [tool for plugin in bundle.plugins for tool in plugin.tools]
    assert [tool.name for tool in tools] == [
        "search_occupation_references",
        "read_occupation_reference",
    ]
    for tool, fields in zip(
        tools, ({"query"}, {"reference_id", "task_id"}), strict=True
    ):
        schema = tool.tool_call_schema
        assert isinstance(schema, type) and issubclass(schema, BaseModel)
        declaration = schema.model_json_schema()
        assert set(declaration["properties"]) == fields
        assert set(declaration["required"]) == fields
    read_schema = tools[1].tool_call_schema
    assert isinstance(read_schema, type) and issubclass(read_schema, BaseModel)
    task = read_schema.model_json_schema()["properties"]["task_id"]
    assert {entry["type"] for entry in task["anyOf"]} == {"string", "null"}
    plugin = bundle.plugins[0]
    assert plugin.state_schema is None
    assert not plugin.on_turn_start
    assert plugin.on_turn_cancel is None


@pytest.mark.parametrize(
    "config",
    [
        {"max_result_characters": 0},
        {"max_result_characters": True},
        {"max_result_characters": "100"},
        {"unknown": 1},
    ],
)
def test_invalid_configuration_is_rejected(config: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        create_bundle(config)
