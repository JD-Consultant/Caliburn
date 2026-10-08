"""A's capability and native plan data item; saved bodies never become instructions."""

import json

from pydantic import JsonValue

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.features.executions.models import ExecutionStateError

PLAN_DATA_KIND = "consultant_interview_plan"
PLAN_TOOL_NAMES = frozenset({"read_interview_plan", "edit_interview_plan"})


def has_interview_plan_tools(request: ResponseRequest) -> bool:
    """Use the captured bundle, and reject partial or incompatible declarations."""
    declared = [
        tool for tool in request.create_payload()["tools"] if tool.get("name") in PLAN_TOOL_NAMES
    ]
    if not declared:
        return False
    if len(declared) != 2 or {tool["name"] for tool in declared} != PLAN_TOOL_NAMES:
        raise ExecutionStateError("The saved Turn has an incomplete interview plan toolkit")
    for tool in declared:
        parameters = tool.get("parameters")
        if (
            tool.get("type") != "function"
            or tool.get("strict") is not True
            or not isinstance(parameters, dict)
            or parameters.get("type") != "object"
            or parameters.get("additionalProperties") is not False
        ):
            raise ExecutionStateError("The saved Turn has an invalid interview plan schema")
        if tool["name"] == "read_interview_plan":
            valid = parameters.get("properties") == {} and parameters.get("required") == []
        else:
            properties = parameters.get("properties")
            diff = properties.get("diff") if isinstance(properties, dict) else None
            valid = (
                isinstance(properties, dict)
                and set(properties) == {"diff"}
                and parameters.get("required") == ["diff"]
                and isinstance(diff, dict)
                and diff.get("type") == "string"
                and diff.get("minLength") == 1
                and diff.get("maxLength") == 16_000
            )
        if not valid:
            raise ExecutionStateError("The saved Turn has an incompatible interview plan schema")
    return True


def interview_plan_item(plan: str | None) -> dict[str, JsonValue]:
    """Render only initial/captured data; recovery uses the exact saved item instead."""
    return {
        "role": "user",
        "content": json.dumps({"data_kind": PLAN_DATA_KIND, "plan": plan}, ensure_ascii=False),
    }
