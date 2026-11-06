"""Plan Bundle 的模型公開工具契約。"""

import asyncio
import json

import pytest
from langchain_core.messages import ToolMessage
from pydantic import BaseModel

from caliburn.bundles.plan import create_bundle


def test_bundle_declares_only_plan_read_and_edit_tools() -> None:
    bundle = create_bundle({})

    assert [tool.name for plugin in bundle.plugins for tool in plugin.tools] == [
        "read_interview_plan",
        "edit_interview_plan",
    ]


def test_prompt_plugin_requires_tools_without_owning_turn_execution() -> None:
    prompt = next(
        plugin for plugin in create_bundle({}).plugins if plugin.name == "plan_prompt"
    )

    assert prompt.prompt_sections
    assert prompt.tools == ()
    assert prompt.required_services == ()
    assert prompt.required_plugins == ("plan_tools",)
    assert prompt.state_schema is None
    assert prompt.on_turn_start == ()
    assert prompt.on_turn_cancel is None


def test_tools_and_turn_lifecycle_are_distinct_plugins() -> None:
    plugins = {plugin.name: plugin for plugin in create_bundle({}).plugins}
    tools = plugins["plan_tools"]
    lifecycle = plugins["plan_lifecycle"]

    assert len(tools.tools) == 2
    assert tools.prompt_sections == ()
    assert tools.on_turn_start == ()
    assert tools.on_turn_cancel is None
    assert tools.required_plugins == ("plan_lifecycle",)
    assert lifecycle.tools == ()
    assert lifecycle.prompt_sections == ()
    assert lifecycle.on_turn_start
    assert lifecycle.on_turn_cancel is not None
    assert lifecycle.state_schema is not None


def test_bundle_rejects_options_that_could_be_mistaken_for_plugin_selection() -> None:
    with pytest.raises(ValueError, match="plugins"):
        create_bundle({"prompt": False})


def test_context_plugin_provides_window_contribution_without_a_separate_node() -> None:
    context = next(
        plugin for plugin in create_bundle({}).plugins if plugin.name == "plan_context"
    )

    assert context.required_plugins == ("plan_lifecycle",)
    assert [key.name for key in context.provided_services] == ["window_contributions"]
    assert context.open_services is not None
    assert context.tools == ()
    assert context.prompt_sections == ()
    assert context.on_turn_start == ()


def test_model_schema_has_only_diff_and_v4a_guidance_on_the_field() -> None:
    read, edit = create_bundle({}).plugins[0].tools

    read_schema = read.tool_call_schema
    edit_schema = edit.tool_call_schema
    assert isinstance(read_schema, type) and issubclass(read_schema, BaseModel)
    assert isinstance(edit_schema, type) and issubclass(edit_schema, BaseModel)
    assert read_schema.model_json_schema()["properties"] == {}
    schema = edit_schema.model_json_schema()
    assert set(schema["properties"]) == {"diff"}
    assert schema["required"] == ["diff"]
    assert "*** End of File" in schema["properties"]["diff"]["description"]
    assert schema["properties"]["diff"]["minLength"] == 1
    assert schema["properties"]["diff"]["maxLength"] == 16_000
    assert "候選" not in edit.description
    assert "consultant_interview_plan" in read.description


@pytest.mark.parametrize("arguments", [{}, {"diff": 12}, {"diff": None}])
def test_invalid_edit_arguments_return_safe_repair(
    arguments: dict[str, object],
) -> None:
    edit = create_bundle({}).plugins[0].tools[1]

    result = asyncio.run(
        edit.ainvoke(
            {"name": edit.name, "type": "tool_call", "id": "edit-1", "args": arguments}
        )
    )

    assert isinstance(result, ToolMessage)
    assert result.tool_call_id == "edit-1"
    assert isinstance(result.content, str)
    rejection = json.loads(result.content)
    assert rejection["status"] == "rejected"
    assert rejection["code"] == "invalid_arguments"
    assert "diff" in rejection["next_action"]
