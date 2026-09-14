"""Strict jd_change_read envelopes; serialization proves no durable effects."""

import json

from .generated.reads import (
    ChangeReadInput, ChangeReadPage, ReadFailure, RestorePreviewInput,
)
from .read_transport import ERRORS
from .reads import ReadError, read_json
from .transport import TransportError


DESCRIPTION = (
    "完整讀取已發配 change_ref 所屬原保存操作的前後淨差異。"
    "只接受 change_ref 與 cursor；首次 cursor 為 null。"
    "has_more 為 true 必須沿同一 change_ref 與 next_cursor 續讀，頁面可在同一 change_index 中間切開。"
    "每個文字欄位保留全文；來源基準摘要與排序、關係與受影響任務均可查。"
    "前後鄰項僅表示當時實際排序，不推定拖動動作。"
    "全部內容 refs 均為唯讀歷史，不可寫入；需要修改時先讀目前 JD。"
    "來源 readability 尚未檢查，basis_status 只對該側歷史稿計算。"
)


def change_tool_definition(provider):
    schema = ChangeReadInput.model_json_schema(mode="validation")
    common = dict(name="jd_change_read", description=DESCRIPTION, strict=True)
    if provider == "openai":
        return dict(type="function", **common, parameters=schema)
    if provider == "anthropic":
        return dict(**common, input_schema=schema)
    raise TransportError("unknown_provider")


def parse_restore_preview_arguments(arguments):
    """The same strict re-parse as a saved-change read, for the preview shape."""
    return _parse_arguments(arguments, RestorePreviewInput)


def parse_change_arguments(arguments):
    return _parse_arguments(arguments, ChangeReadInput)


def _parse_arguments(arguments, model):
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
        raw = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > 16384:
            raise ValueError("input_too_large")
        value = json.loads(raw, object_pairs_hook=unique, parse_constant=invalid_constant)
        return model.model_validate(value, strict=True).model_dump(mode="json")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise ReadError("invalid_input") from None


def _validate_page(value):
    records = value["records"]
    end = value["start_index"] + len(records)
    if (value["has_more"] != (value["next_cursor"] is not None)
        or value["has_more"] != (end < value["total_records"])
        or end > value["total_records"]
        or value["oversized_unit"] and len(records) != 1
        or not records and (value["start_index"] != 0 or value["total_records"] != 0)
        or (value["total_changes"] == 0) != (value["total_records"] == 0)):
        raise ValueError("invalid_page")
    last_index = -1
    headers = set()
    for row in records:
        index = row["change_index"]
        if index >= value["total_changes"] or index < last_index:
            raise ValueError("invalid_change_index")
        if row["type"] == "change":
            if index in headers or not (row["before_exists"] or row["after_exists"]):
                raise ValueError("invalid_header")
            kind = row["kind"]
            if ((kind in {"create", "link"} and (row["before_exists"] or not row["after_exists"]))
                or (kind in {"delete", "unlink"} and (not row["before_exists"] or row["after_exists"]))
                or (kind in {"update", "move", "reorder"} and not (row["before_exists"] and row["after_exists"]))):
                raise ValueError("invalid_header")
            headers.add(index)
        if row["type"] == "affected_task" and row["before_task_ref"] is None and row["after_task_ref"] is None:
            raise ValueError("missing_affected_task")
        last_index = index
    if records and value["start_index"] == 0 and (records[0]["type"] != "change" or records[0]["change_index"] != 0):
        raise ValueError("missing_first_header")


def change_tool_output(provider, call_id, result):
    try:
        if (not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 4096 or not isinstance(result, dict)):
            raise ValueError("invalid_result")
        error = result.get("type") == "read_error"
        if error:
            value = ReadFailure.model_validate(result, strict=True).model_dump(mode="json")
            if (value["message"], value["next_action"]) != ERRORS[value["code"]]:
                raise ValueError("invalid_error")
        else:
            value = ChangeReadPage.model_validate(result, strict=True).model_dump(mode="json")
            _validate_page(value)
        content = read_json(value)
        content.encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise TransportError("invalid_result") from None
    if provider == "openai":
        return dict(type="function_call_output", call_id=call_id, output=content)
    if provider == "anthropic":
        return dict(type="tool_result", tool_use_id=call_id, content=content, is_error=error)
    raise TransportError("unknown_provider")
