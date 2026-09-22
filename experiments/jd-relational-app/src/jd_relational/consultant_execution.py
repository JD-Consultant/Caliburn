"""App-owned execution decisions for one consultant child run.

This module does not retry a tool and does not persist a second execution
counter.  It inspects the canonical messages already saved by the agent and
returns the smallest request policy needed by the model-call middleware.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Literal, Sequence

from langchain.agents.middleware import AgentMiddleware
from langchain.agents.middleware.types import ModelRequest, ModelResponse
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage

from .change_transport import change_tool_output
from .generated.reads import ReadFailure, ReadPage
from .read_transport import read_tool_output
from .result_transport import ResultValidationError, validate_result
from .transport import MODELS


class ConsultantExecutionError(ValueError):
    """A fixed internal execution error; never expose saved tool contents."""


_JD_MUTATIONS = frozenset(MODELS)
_JD_READS = frozenset({"jd_read", "jd_change_read"})
_KNOWN_JD_TOOLS = _JD_MUTATIONS | _JD_READS
_CORRECTABLE_ACTIONS = frozenset({"correct_arguments", "reread_current"})
_NONRECOVERABLE_ACTIONS = frozenset({"stop", "reconcile_operation"})


@dataclass(frozen=True)
class ExecutionDecision:
    finalize: bool
    reason: Literal[
        "model_budget", "correction_exhausted", "nonrecoverable_result", "no_progress"
    ] | None = None


@dataclass(frozen=True)
class _ToolEvent:
    call_id: str
    name: str
    arguments: dict
    result: dict
    signature: str


@dataclass
class _Correction:
    origin_name: str
    replacements: int
    previous_signature: str


def _canonical(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError, UnicodeError, RecursionError):
        raise ConsultantExecutionError("invalid_tool_result") from None


def _digest(value) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _run_messages(messages: Sequence[BaseMessage], run_id: str) -> list[BaseMessage]:
    positions = [
        index for index, message in enumerate(messages)
        if isinstance(message, HumanMessage) and message.id == run_id
    ]
    if len(positions) != 1:
        raise ConsultantExecutionError("invalid_run_boundary")
    start = positions[0]
    if any(isinstance(message, HumanMessage) for message in messages[start + 1:]):
        raise ConsultantExecutionError("invalid_run_boundary")
    return list(messages[start + 1:])


def _json_content(message: ToolMessage) -> dict:
    if type(message.content) is not str:
        raise ConsultantExecutionError("invalid_tool_result")
    try:
        value = json.loads(message.content)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ConsultantExecutionError("invalid_tool_result") from None
    if type(value) is not dict:
        raise ConsultantExecutionError("invalid_tool_result")
    return value


def _decode_result(name: str, call_id: str, message: ToolMessage, *, run_id: str) -> dict:
    if type(message.name) is not str or message.name != name or message.tool_call_id != call_id:
        raise ConsultantExecutionError("invalid_tool_result")
    value = _json_content(message)
    try:
        if name in _JD_MUTATIONS:
            result = validate_result(value)
            expected_status = "error" if result["error"] is not None else "success"
        elif name in _JD_READS and message.artifact is not None:
            # consultant_tools reaches consultant_context, which owns this
            # middleware. Import only while decoding a saved tool result so
            # the modules keep their existing composition boundary.
            from .consultant_tools import AiToolError, _decode_jd_read_message
            try:
                result, _ = _decode_jd_read_message(
                    message, name=name, call_id=call_id, run_id=run_id,
                )
            except AiToolError:
                raise ConsultantExecutionError("invalid_tool_result") from None
            expected_status = "error" if result.get("type") == "read_error" else "success"
        elif name == "jd_read":
            read_tool_output("openai", call_id, value)
            result = ReadFailure.model_validate(value, strict=True).model_dump(mode="json") \
                if value.get("type") == "read_error" else ReadPage.model_validate(value, strict=True).model_dump(mode="json")
            expected_status = "error" if value.get("type") == "read_error" else "success"
        elif name == "jd_change_read":
            change_tool_output("openai", call_id, value)
            # Compatibility for canonical test fixtures and pre-projection
            # checkpoints. Production model-safe reads carry a private artifact.
            result = value
            expected_status = "error" if value.get("type") == "read_error" else "success"
        else:
            raise ConsultantExecutionError("unknown_tool")
    except ConsultantExecutionError:
        raise
    except (ResultValidationError, ValueError, TypeError, UnicodeError, RecursionError):
        raise ConsultantExecutionError("invalid_tool_result") from None
    if message.status != expected_status:
        raise ConsultantExecutionError("invalid_tool_result")
    return result


def _events(messages: Sequence[BaseMessage], *, run_id: str) -> list[_ToolEvent]:
    calls: dict[str, tuple[str, dict]] = {}
    results: dict[str, ToolMessage] = {}
    call_order: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                try:
                    name, call_id, arguments = call["name"], call["id"], call["args"]
                except (KeyError, TypeError):
                    raise ConsultantExecutionError("invalid_tool_call") from None
                if name in _KNOWN_JD_TOOLS:
                    if type(call_id) is not str or not call_id or type(arguments) is not dict:
                        raise ConsultantExecutionError("invalid_tool_call")
                    if call_id in calls:
                        raise ConsultantExecutionError("invalid_tool_call")
                    calls[call_id] = (name, arguments)
                    call_order.append(call_id)
        elif isinstance(message, ToolMessage) and message.tool_call_id in calls:
            if message.tool_call_id in results:
                raise ConsultantExecutionError("invalid_tool_result")
            results[message.tool_call_id] = message

    if set(calls) != set(results):
        raise ConsultantExecutionError("invalid_tool_result")

    result = []
    for call_id in call_order:
        name, arguments = calls[call_id]
        decoded = _decode_result(name, call_id, results[call_id], run_id=run_id)
        result.append(_ToolEvent(call_id, name, arguments, decoded,
                                 _digest({"name": name, "args": arguments, "result": decoded})))
    return result


def _failure_kind(event: _ToolEvent) -> tuple[str, str] | None:
    result = event.result
    if event.name in _JD_MUTATIONS:
        status = result["status"]
        if status in {"committed", "no_change"}:
            return None
        return status, result["next_action"]
    if result.get("type") != "read_error":
        return None
    return result["code"], result["next_action"]


def _is_success(event: _ToolEvent) -> bool:
    if event.name in _JD_MUTATIONS:
        return event.result["status"] in {"committed", "no_change"}
    return event.result.get("type") != "read_error"


def _is_replacement(event: _ToolEvent, correction: _Correction) -> bool:
    if correction.origin_name in _JD_MUTATIONS:
        return event.name in _JD_MUTATIONS
    return event.name == correction.origin_name


def decide_consultant_execution(
    messages: Sequence[BaseMessage],
    *,
    run_id: str,
    model_requests_used: int,
    max_model_requests: int = 64,
    max_correction_submissions: int = 2,
) -> ExecutionDecision:
    """Derive the next request policy from one current run's saved messages."""
    if (type(run_id) is not str or not run_id
            or type(model_requests_used) is not int or model_requests_used < 0
            or type(max_model_requests) is not int or max_model_requests < 1
            or type(max_correction_submissions) is not int or max_correction_submissions < 0):
        raise ConsultantExecutionError("invalid_execution_policy")

    current = _run_messages(messages, run_id)
    events = _events(current, run_id=run_id)
    correction: _Correction | None = None

    for event in events:
        failure = _failure_kind(event)
        if failure is None:
            if correction is not None and (
                (correction.origin_name in _JD_READS and event.name in _JD_MUTATIONS)
                or (correction.origin_name in _JD_MUTATIONS and event.name in _JD_MUTATIONS)
                or (correction.origin_name in _JD_READS and event.name == correction.origin_name)
            ):
                correction = None
            continue

        status, action = failure
        if action in _NONRECOVERABLE_ACTIONS or status in {
            "save_failed", "read_failed", "operation_conflict", "outcome_unknown",
            "invalid_ref", "archived", "busy",
        }:
            return ExecutionDecision(True, "nonrecoverable_result")
        if status == "dependent_items":
            continue
        if action not in _CORRECTABLE_ACTIONS:
            return ExecutionDecision(True, "nonrecoverable_result")

        if correction is None:
            if max_correction_submissions == 0:
                return ExecutionDecision(True, "correction_exhausted")
            correction = _Correction(event.name, 0, event.signature)
            continue
        if not _is_replacement(event, correction):
            continue
        if event.signature == correction.previous_signature:
            return ExecutionDecision(True, "no_progress")
        correction.replacements += 1
        correction.previous_signature = event.signature
        if correction.replacements >= max_correction_submissions:
            return ExecutionDecision(True, "correction_exhausted")

    if model_requests_used >= max_model_requests - 1:
        return ExecutionDecision(True, "model_budget")
    return ExecutionDecision(False, None)


FINALIZATION_INSTRUCTION = (
    "這是 Runtime 的最後無工具收尾請求。只輸出簡潔、自然的繁體中文使用者回覆，"
    "整理已確認保存的成果，並誠實說明尚未完成或下一輪需要處理的事項。"
    "不得模擬工具呼叫，不得輸出 JSON、程式碼區塊、工具名稱、參數、內部引用、"
    "識別碼或 Runtime／除錯細節。不能再讀取、修改 JD、修補 Memory、呼叫背景工作"
    "或呼叫任何工具，也不得把未確認結果說成已保存。不能再呼叫工具。"
)


def _append_finalization_instruction(system_message: SystemMessage | None) -> SystemMessage:
    """Copy the assembled system blocks and append a request-only constraint."""
    if system_message is None:
        blocks = []
    elif isinstance(system_message.content, str):
        blocks = [{"type": "text", "text": system_message.content}]
    elif isinstance(system_message.content, list):
        blocks = list(system_message.content)
    else:
        raise ConsultantExecutionError("invalid_final_request")
    blocks.append({"type": "text", "text": FINALIZATION_INSTRUCTION})
    return SystemMessage(content=blocks)


def _validate_final_response(response: ModelResponse) -> ModelResponse:
    if not isinstance(response, ModelResponse) or len(response.result) != 1:
        raise ConsultantExecutionError("invalid_final_response")
    message = response.result[0]
    if (not isinstance(message, AIMessage) or message.tool_calls
            or message.invalid_tool_calls):
        raise ConsultantExecutionError("invalid_final_response")
    return response


class ConsultantExecutionMiddleware(AgentMiddleware):
    """Apply the App-owned correction and final no-tools policy synchronously."""

    def wrap_model_call(self, request: ModelRequest, handler):
        runtime = request.runtime
        context = getattr(runtime, "context", None)
        run_id = getattr(context, "run_id", None)
        model_requests_used = request.state.get("thread_model_call_count", 0)
        decision = decide_consultant_execution(
            request.state.get("messages", request.messages),
            run_id=run_id,
            model_requests_used=model_requests_used,
        )
        if not decision.finalize:
            return handler(request)
        final_request = request.override(
            system_message=_append_finalization_instruction(request.system_message),
            # Keep the identical tool schema prefix for provider caching. The
            # provider-level prohibition is tool_choice=none; response
            # validation remains the final fail-closed boundary.
            tools=request.tools,
            tool_choice="none",
            model_settings=request.model_settings,
        )
        return _validate_final_response(handler(final_request))
