"""啟動固定 SDK 政策與工具；每輪只初始化一次工作請求。"""

from copy import deepcopy
from typing import cast

from langchain_core.tools import StructuredTool
from langchain_core.utils.function_calling import convert_to_openai_function
from openai.types.responses.function_tool_param import FunctionToolParam
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.responses.response_function_tool_call import ResponseFunctionToolCall
from openai.types.responses.response_function_tool_call_output_item import (
    ResponseFunctionToolCallOutputItem,
)
from openai.types.responses.response_includable import ResponseIncludable

from caliburn.modules.agent.state import AgentState, OpenAIItems, request_items

_FORBIDDEN_FIELDS = {
    "tools",
    "conversation",
    "previous_response_id",
    "context_management",
    "prompt",
    "stream",
    "response_id",
    "starting_after",
    "extra_body",
    "extra_headers",
    "extra_query",
}


class OpenAIRequestInitializer:
    def __init__(
        self,
        model_request: ResponseCreateParamsBase,
        tools: tuple[StructuredTool, ...],
        prompt_sections: tuple[str, ...] = (),
    ):
        self._request = _configure_request(model_request)
        sections = [
            part
            for part in (self._request.get("instructions"), *prompt_sections)
            if part
        ]
        if sections:
            self._request["instructions"] = "\n\n".join(sections)
        self.tools = tuple(tool.model_copy() for tool in tools)
        self._declarations: dict[str, FunctionToolParam] = {}
        for tool in self.tools:
            if tool.name in self._declarations:
                raise ValueError(f"Duplicate tool name: {tool.name}")
            if isinstance(tool.args_schema, dict):
                tool.args_schema = deepcopy(tool.args_schema)
            declaration = convert_to_openai_function(tool, strict=True)
            self._declarations[tool.name] = {
                "type": "function",
                "name": declaration["name"],
                "description": declaration["description"],
                "parameters": declaration["parameters"],
                "strict": declaration["strict"],
            }

    def initialize(self, state: AgentState) -> AgentState:
        supplied = state["turn_input"]
        if not isinstance(supplied, (str, list)):
            raise ValueError("New turn input requires text or SDK input items")
        request = deepcopy(self._request)
        request["input"] = (
            [{"role": "user", "content": supplied}]
            if isinstance(supplied, str)
            else deepcopy(supplied)
        )
        request["tools"] = deepcopy(list(self._declarations.values()))
        return {"model_request": request}

    def validate_request_policy(self, state: AgentState) -> AgentState:
        request = state["model_request"]
        if not isinstance(request.get("input"), list):
            raise ValueError("Working model_request.input requires an items list")
        _validate_tool_call_pairs(request_items(request))
        selected: set[str] = set()
        for declaration in request.get("tools", ()):
            if declaration["type"] != "function":
                raise ValueError("Agent requires declared function tools")
            name = declaration["name"]
            if name in selected or self._declarations.get(name) != declaration:
                raise ValueError(f"Unknown or modified tool declaration: {name}")
            selected.add(name)
        # Hook 能改 prompt/input/tool 選用，不能繞過固定的出站政策。
        mutable_fields = {"input", "instructions", "tools"}
        fixed_request = {
            key: value for key, value in request.items() if key not in mutable_fields
        }
        fixed_configuration = {
            key: value
            for key, value in self._request.items()
            if key not in mutable_fields
        }
        if fixed_request != fixed_configuration:
            raise ValueError("Request hook changed fixed request policy")
        return {}


def _validate_tool_call_pairs(items: OpenAIItems) -> None:
    pending: set[str] = set()
    for item in items:
        if isinstance(item, dict):
            item_type = item.get("type")
            if item_type not in ("function_call", "function_call_output"):
                continue
            call_id = item.get("call_id")
        elif isinstance(
            item, (ResponseFunctionToolCall, ResponseFunctionToolCallOutputItem)
        ):
            item_type = item.type
            call_id = item.call_id
        else:
            continue
        if not isinstance(call_id, str) or not call_id:
            raise ValueError("Function call pairing requires a call_id")
        if item_type == "function_call":
            if call_id in pending:
                raise ValueError("Function call has no output before its ID is reused")
            pending.add(call_id)
        else:
            if call_id not in pending:
                raise ValueError("Function call output has no preceding unpaired call")
            pending.remove(call_id)
    if pending:
        raise ValueError("Function call is missing its output")


def _configure_request(source: ResponseCreateParamsBase) -> ResponseCreateParamsBase:
    """套用 Core 固定政策；角色仍必須明示模型、effort 及輸出容量。"""
    request = deepcopy(source)
    if request.get("input"):
        raise ValueError("Model request input must be absent or empty")
    request["input"] = []
    for key in _FORBIDDEN_FIELDS:
        if request.get(key) is not None:
            raise ValueError(
                "Agent request cannot override tools or local execution policy"
            )
        cast(dict[str, object], request).pop(key, None)
    if not request.get("model"):
        raise ValueError("Model request must supply model")
    maximum = request.get("max_output_tokens")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum <= 0:
        raise ValueError("Model request must supply positive max_output_tokens")
    reasoning = request.get("reasoning")
    if not reasoning or not reasoning.get("effort"):
        raise ValueError("Model request must supply reasoning.effort")
    if reasoning.get("context") not in (None, "all_turns"):
        raise ValueError("Agent requires reasoning.context=all_turns")
    request["reasoning"] = {**reasoning, "context": "all_turns"}
    policy: ResponseCreateParamsBase = {
        "store": False,
        "background": False,
        "parallel_tool_calls": True,
        "tool_choice": "auto",
        "truncation": "disabled",
        "service_tier": "default",
    }
    for key, value in policy.items():
        if request.get(key) is not None and request.get(key) != value:
            raise ValueError(f"Agent requires {key}={value!r}")
    default_include: list[ResponseIncludable] = ["reasoning.encrypted_content"]
    include = request.get("include")
    if include is None:
        include = default_include
    if "reasoning.encrypted_content" not in include:
        raise ValueError("Agent requires reasoning.encrypted_content")
    return {**request, **policy, "include": list(include)}
