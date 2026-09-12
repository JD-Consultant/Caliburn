"""Small input adapters for the isolated candidate probe, without execution or I/O."""

from copy import deepcopy
import json
from pathlib import Path

from pydantic import ValidationError

from .generated.models import CreateTaskInput, ReviseWorkInput


REQUEST_LIMIT = 1024 * 1024
CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "jd-work.schema.json"
MODELS = {"jd_create_task": CreateTaskInput, "jd_revise_work": ReviseWorkInput}
DESCRIPTIONS = {
    "jd_create_task": (
        "當某項工作已能辨識時，建立任務及目前已知的成果、要求、既有知識技能引用。"
        "名稱或敘述至少一項有內容；其他清單可空，不為填滿補造。使用 App 已提供的 refs；"
        "整組驗證，任何一項無效都不應留下部分任務。basis_refs 僅列已核對的確切來源。"
    ),
    "jd_revise_work": (
        "依新資訊一次修訂相依的正文、成果／要求、知識技能引用與全職位條件。"
        "只使用同一版已取得的 refs；每欄一次，勿對同項改又刪或對同關係反覆設定。"
        "整組成功或全部拒絕，不拆散同一次工作更正；本次新增項目不能當引用或排序錨點。"
        "basis_refs 為空保留原依據，非空新增或刷新明列來源。"
    ),
}


class TransportError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise TransportError("invalid_input")
        result[key] = value
    return result


def _reject_constant(_):
    raise TransportError("invalid_input")


def model_command(tool: str, arguments: str | dict) -> dict:
    """Parse model or manual arguments to the same internal command, no defaults."""
    if tool not in MODELS:
        raise TransportError("unknown_tool")
    try:
        raw = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > REQUEST_LIMIT:
            raise TransportError("request_too_large")
        payload = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        value = MODELS[tool].model_validate(payload, strict=True)
        return {"tool": tool, "arguments": value.model_dump(mode="json")}
    except TransportError:
        raise
    except (ValueError, TypeError, UnicodeError, ValidationError, RecursionError) as error:
        # Never return the SDK context or echo arbitrary input in a tool error.
        raise TransportError("invalid_input") from error


def manual_command(envelope: dict) -> dict:
    """Probe adapter; the actual generated HTTP envelope is a later RS-1 step."""
    if not isinstance(envelope, dict) or set(envelope) != {"tool", "arguments"}:
        raise TransportError("invalid_input")
    if not isinstance(envelope["tool"], str) or not isinstance(envelope["arguments"], dict):
        raise TransportError("invalid_input")
    return model_command(envelope["tool"], envelope["arguments"])


def tool_definition(provider: str, tool: str) -> dict:
    if tool not in MODELS:
        raise TransportError("unknown_tool")
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    title = "CreateTaskInput" if tool == "jd_create_task" else "ReviseWorkInput"
    schema = deepcopy(contract["$defs"][title])
    schema["$defs"] = deepcopy(contract["$defs"])
    common = {"name": tool, "description": DESCRIPTIONS[tool], "strict": True}
    if provider == "openai":
        return {"type": "function", **common, "parameters": schema}
    if provider == "anthropic":
        return {**common, "input_schema": schema}
    raise TransportError("unknown_provider")


def tool_output(provider: str, call_id: str, result: dict) -> dict:
    """Wire packaging only; callers must supply observed results, never invented saves."""
    if not isinstance(call_id, str) or not call_id or not isinstance(result, dict):
        raise TransportError("invalid_result")
    content = json.dumps(result, ensure_ascii=False, allow_nan=False)
    if provider == "openai":
        return {"type": "function_call_output", "call_id": call_id, "output": content}
    if provider == "anthropic":
        return {"type": "tool_result", "tool_use_id": call_id, "content": content, "is_error": result.get("status") == "error"}
    raise TransportError("unknown_provider")
