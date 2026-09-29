"""Shared wire mechanics only; role permissions and domain rules remain with each tool."""

from importlib.resources import files

from openai.types.responses import FunctionToolParam
from pydantic import TypeAdapter

from caliburn.contracts.generated.tools.tool_rejection import ToolRejection


def function_definition(name: str, description: str, parameters_schema: str) -> FunctionToolParam:
    schema = TypeAdapter(dict[str, object]).validate_json(
        files("caliburn.contracts.generated.tools")
        .joinpath(f"{parameters_schema}.schema.json")
        .read_text(encoding="utf-8")
    )
    schema.pop("$schema", None)
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": schema,
        "strict": True,
    }


def reject_tool_call(code: str, message: str, next_action: str) -> str:
    return ToolRejection(
        status="rejected", code=code, message=message, next_action=next_action
    ).model_dump_json()
