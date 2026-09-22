"""Model read request/result envelopes. Neither provider executes the read here."""

import json
from pydantic import ValidationError

from .generated.reads import ReadInput, ReadPage, ReadFailure
from .reads import ReadError, read_json
from .transport import TransportError

DESCRIPTION = (
    "讀取目前完整 JD、指定項目／章節或唯讀歷史。current 的 target_ref 為 null；"
    "item／section 使用先前讀取的同類 ref；history 的 null target 列歷史，revision ref 讀舊稿。"
    "has_more 為 true 必須沿原 view／target_ref 與 next_cursor 續讀；不可將缺頁當完整工作。"
    "開始撰寫、收到人工更改通知或定位過時時先讀 current；歷史 refs 不可寫入。"
    "欄位全文、任務成果要求與 K/S 關係可查；source readability 與 basis_status 是不同事實。"
    "type=item 記錄中的 container_ref 只表示目前父清單，不是新增子項的目標；"
    "新增子項應從 type=container 記錄依 child_kind／owner_ref 配對後取 container_ref。"
)
ERRORS = {
    "invalid_input": (
        "讀取參數不符；請依該工具說明提供必要參數。",
        "correct_arguments",
    ),
    "invalid_ref": ("引用不適用於此文件或用途；請重新讀取目前 JD。", "reread_current"),
    "stale_view": ("JD 已有較新版本；請重新讀取目前稿，不接續舊頁。", "reread_current"),
    "target_missing": ("找不到指定文件或內容；請重新讀取並確認目標。", "reread_current"),
    "read_failed": ("目前無法確認讀取結果；請停止並保留現有內容。", "stop"),
}


def read_tool_definition(provider):
    schema = ReadInput.model_json_schema(mode="validation")
    common = dict(name="jd_read", description=DESCRIPTION, strict=True)
    if provider == "openai":
        return dict(type="function", **common, parameters=schema)
    if provider == "anthropic":
        return dict(**common, input_schema=schema)
    raise TransportError("unknown_provider")


def parse_read_arguments(arguments):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_key")
            result[key] = value
        return result

    def invalid_constant(_):
        raise ValueError("non_finite")

    try:
        raw = (
            arguments
            if isinstance(arguments, str)
            else json.dumps(arguments, ensure_ascii=False, allow_nan=False)
        )
        if len(raw.encode("utf-8")) > 16384:
            raise ValueError("input_too_large")
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
        return ReadInput.model_validate(value, strict=True).model_dump(mode="json")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ReadError("invalid_input") from None


def read_failure(code):
    if code not in ERRORS:
        code = "read_failed"
    message, action = ERRORS[code]
    return ReadFailure(
        type="read_error", code=code, message=message, next_action=action
    ).model_dump(mode="json")


def read_tool_output(provider, call_id, result):
    try:
        if (
            not isinstance(call_id, str)
            or not call_id.strip()
            or len(call_id) > 4096
            or not isinstance(result, dict)
        ):
            raise ValueError("invalid_result")
        error = result.get("type") == "read_error"
        if error:
            value = ReadFailure.model_validate(result, strict=True).model_dump(mode="json")
            if (value["message"], value["next_action"]) != ERRORS[value["code"]]:
                raise ValueError("invalid_error")
        else:
            value = ReadPage.model_validate(result, strict=True).model_dump(mode="json")
            if value["has_more"] != (value["next_cursor"] is not None):
                raise ValueError("invalid_page")
            if value["oversized_unit"] and len(value["records"]) != 1:
                raise ValueError("invalid_page")
            end = value["start_index"] + len(value["records"])
            if value["total_records"] is not None and end > value["total_records"]:
                raise ValueError("invalid_page")
        content = read_json(value)
        content.encode("utf-8")
    except (ValueError, TypeError, UnicodeError, ValidationError):
        raise TransportError("invalid_result") from None
    if provider == "openai":
        return dict(type="function_call_output", call_id=call_id, output=content)
    if provider == "anthropic":
        return dict(type="tool_result", tool_use_id=call_id, content=content, is_error=error)
    raise TransportError("unknown_provider")
