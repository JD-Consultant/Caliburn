"""Small input adapters for the isolated candidate probe, without execution or I/O."""

import json

from pydantic import ValidationError

from .result_transport import ResultValidationError, validate_result

from .generated.models import (
    CreateTaskInput, ReviseWorkInput, SetTextInput, InsertItemInput,
    DeleteItemInput, MoveItemInput, RestoreRevisionInput, SetTaskCapabilityInput, UndoAiTurnInput,
    ReplaceSelectionInput,
)
from .generated.model_inputs import (
    CreateTaskInput as ModelCreateTaskInput,
    ReviseWorkInput as ModelReviseWorkInput,
    SetTextInput as ModelSetTextInput,
    InsertItemInput as ModelInsertItemInput,
    DeleteItemInput as ModelDeleteItemInput,
    MoveItemInput as ModelMoveItemInput,
    SetTaskCapabilityInput as ModelSetTaskCapabilityInput,
    ReplaceSelectionInput as ModelReplaceSelectionInput,
)


REQUEST_LIMIT = 1024 * 1024
# Manual-only business operations. They share this transport, the same command
# shape and the same writer, but are never offered to the model: taking a whole
# document back is the employee's decision, not something a turn may choose.
MANUAL_MODELS = {"restore_revision": RestoreRevisionInput, "undo_ai_turn": UndoAiTurnInput}
DOMAIN_MODELS = {"jd_create_task": CreateTaskInput, "jd_revise_work": ReviseWorkInput,
                 "jd_set_text": SetTextInput, "jd_insert_item": InsertItemInput,
                 "jd_delete_item": DeleteItemInput, "jd_move_item": MoveItemInput,
                 "jd_set_task_capability": SetTaskCapabilityInput,
                 "jd_replace_selection": ReplaceSelectionInput}
MODEL_MODELS = {"jd_create_task": ModelCreateTaskInput, "jd_revise_work": ModelReviseWorkInput,
                "jd_set_text": ModelSetTextInput, "jd_insert_item": ModelInsertItemInput,
                "jd_delete_item": ModelDeleteItemInput, "jd_move_item": ModelMoveItemInput,
                "jd_set_task_capability": ModelSetTaskCapabilityInput,
                "jd_replace_selection": ModelReplaceSelectionInput}
# Public model-tool catalogue. The domain catalogue stays separate so the
# human transport continues to receive canonical source refs.
MODELS = MODEL_MODELS
DESCRIPTIONS = {
    "jd_set_text": "單独修改一個既有欄位的完整文字。多欄相依更正用 jd_revise_work；選區修改用 jd_replace_selection。保留未知，不用清空模擬刪除項目。",
    "jd_insert_item": "新增職責、協作對象、知識、技能、成果、要求或全職位條件。container_ref 必須從最新一次成功的 jd_read current 中，按 type=container 的 child_kind／owner_ref 選擇相符種類並原樣複製；不可使用 item_ref 或 type=item 記錄中的 container_ref，不可推算、縮短或沿用舊值。未知內容可空，任務改用 jd_create_task 一次建立。",
    "jd_delete_item": "依明確意圖刪除項目。刪职責保留其任務及子項並解除分組；仍被任務引用的知識技能不能直接刪。刪職責可同次補齊存活任務的必要範圍，其他刪除不帶內容更正。",
    "jd_move_item": "將任務移至另一職責或未分組，或在同一清單重排項目；保留身分、子項及引用。任務換組可一併修正相關範圍；不要刪除後重建，也不要改不相關工作。",
    "jd_set_task_capability": "新增或解除任務對既有知識或技能的引用；使用已發配refs，不用名稱猜測。解除引用不刪共用定義、不影響其他任務；unlink時basis_evidence_keys為空。",
    "jd_replace_selection": "只替換App已提供selection_ref的選取文字。replacement_text只放選區替代文字；不提供行號、offset、舊文或整欄全文。過時先重讀，不能搜尋同字續改；來源須核完整正式target。",
    "jd_create_task": (
        "當某項工作已能辨識時，建立任務及目前已知的成果、要求、既有知識技能引用。"
        "名稱或敘述至少一項有內容；其他清單可空，不為填滿補造。使用 App 已提供的 refs；"
        "職責下任務的 container_ref 必須取自 type=container、child_kind=task，且 owner_ref"
        "等於該 duty item_ref 的記錄；未分組任務則使用相同 child_kind 且 owner_ref=null 的記錄，"
        "不可使用 duty 的 item_ref 或該 duty 的 type=item 記錄中的 container_ref。"
        "整組驗證，任何一項無效都不應留下部分任務。basis_evidence_keys 僅列已完整讀取的證據。"
    ),
    "jd_revise_work": (
        "依新資訊一次修訂相依的正文、成果／要求、知識技能引用與全職位條件。"
        "只使用同一版已取得的 refs；每欄一次，勿對同項改又刪或對同關係反覆設定。"
        "整組成功或全部拒絕，不拆散同一次工作更正；本次新增項目不能當引用或排序錨點。"
        "basis_evidence_keys 為空保留原依據，非空新增或刷新明列證據。"
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


def _command(tool: str, arguments: str | dict, catalog: dict) -> dict:
    """Parse arguments to the internal command shape, with no defaults."""
    if not isinstance(tool, str) or tool not in catalog:
        raise TransportError("unknown_tool")
    try:
        raw = arguments if isinstance(arguments, str) else json.dumps(arguments, ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > REQUEST_LIMIT:
            raise TransportError("request_too_large")
        payload = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
        value = catalog[tool].model_validate(payload, strict=True)
        return {"tool": tool, "arguments": value.model_dump(mode="json")}
    except TransportError:
        raise
    except (ValueError, TypeError, UnicodeError, ValidationError, RecursionError):
        # Never return the SDK context or echo arbitrary input in a tool error.
        raise TransportError("invalid_input") from None


def model_command(tool: str, arguments: str | dict) -> dict:
    """Parse model arguments, then resolve its evidence-key field name later.

    Manual-only operations are deliberately absent here: a model asking for one
    is an unknown tool, not a permission failure to explain away.
    """
    model_value = _command(tool, arguments, MODEL_MODELS)
    canonical = _rename_model_evidence_keys(model_value["arguments"])
    return _command(tool, canonical, DOMAIN_MODELS)


def model_arguments(tool: str, arguments: str | dict) -> dict:
    """Validate and return the model-visible shape without canonicalizing it."""
    return _command(tool, arguments, MODEL_MODELS)


def _rename_model_evidence_keys(value):
    if isinstance(value, list):
        return [_rename_model_evidence_keys(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        canonical_key = "basis_refs" if key == "basis_evidence_keys" else key
        if canonical_key in result:
            raise TransportError("invalid_input")
        result[canonical_key] = _rename_model_evidence_keys(item)
    return result


def manual_command(envelope: dict) -> dict:
    """Shared inner command shape; ManualSaveInput owns the outer HTTP identity.

    The employee may also ask for the manual-only operations, which parse and
    validate exactly as every other command does.
    """
    if not isinstance(envelope, dict) or set(envelope) != {"tool", "arguments"}:
        raise TransportError("invalid_input")
    if not isinstance(envelope["tool"], str) or not isinstance(envelope["arguments"], dict):
        raise TransportError("invalid_input")
    return _command(envelope["tool"], envelope["arguments"], {**DOMAIN_MODELS, **MANUAL_MODELS})


def tool_definition(provider: str, tool: str) -> dict:
    if not isinstance(tool, str) or tool not in MODEL_MODELS:
        raise TransportError("unknown_tool")
    # The DTO is generated from SSOT. Pydantic emits only definitions this tool
    # actually uses, without a custom ref resolver or unrelated catalog entries.
    schema = MODEL_MODELS[tool].model_json_schema(mode="validation")
    common = {"name": tool, "description": DESCRIPTIONS[tool], "strict": True}
    if provider == "openai":
        return {"type": "function", **common, "parameters": schema}
    if provider == "anthropic":
        return {**common, "input_schema": schema}
    raise TransportError("unknown_provider")


def tool_output(provider: str, call_id: str, result: dict) -> dict:
    """Validate the common observation, then wrap it without executing anything.

    Shape validation cannot prove a commit. Only the App's durable-result owner
    may supply a confirmed result; preparation candidates are not accepted here.
    """
    if not isinstance(call_id, str) or not call_id.strip() or len(call_id) > 4096 or not isinstance(result, dict):
        raise TransportError("invalid_result")
    try:
        value = validate_result(result)
        content = json.dumps(value, ensure_ascii=False, allow_nan=False)
    except (ResultValidationError, ValueError, TypeError, UnicodeError):
        raise TransportError("invalid_result") from None
    if provider == "openai":
        return {"type": "function_call_output", "call_id": call_id, "output": content}
    if provider == "anthropic":
        return {"type": "tool_result", "tool_use_id": call_id, "content": content, "is_error": value["error"] is not None}
    raise TransportError("unknown_provider")
