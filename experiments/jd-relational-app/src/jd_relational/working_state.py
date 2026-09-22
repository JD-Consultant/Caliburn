"""Thread-scoped interview Working State over the existing LangGraph checkpoint.

This is a non-authoritative work surface for the main consultant.  Canonical
conversation, Memory and JD remain with their existing owners.  The model sees
only Runtime-issued evidence keys; persisted items keep the resolved source
references in the same checkpoint state.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID, uuid4
import json

from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool, ToolException
from langgraph.config import get_config
from langgraph.types import Command
from pydantic import (
    BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator,
)


WORKING_STATE_READ_NAME = "read_interview_working_item"
WORKING_STATE_UPDATE_NAME = "update_interview_working_state"
WORKING_STATE_UPDATE_KIND = "interview_working_state_update"
WORKING_STATE_TOOL_NAMES = frozenset({
    WORKING_STATE_READ_NAME, WORKING_STATE_UPDATE_NAME,
})
MAX_WORKING_ITEMS = 128
MAX_BATCH_OPERATIONS = 32
MAX_SOURCE_REFS = 32
MAX_RELATED_REFS = 32
_ITEM_PREFIX = "wi_"
_SOURCE_INSTRUCTION = (
    "此 evidence_key 只定位本輪已保存的員工原話及列明的前一則 AI 公開上下文。"
    "正文仍在對應的原 user/assistant 訊息中；AI 文字不是員工事實。"
    "模型只選 App 提供的 key，不產生或猜測來源、offset、版本或 checkpoint。"
)
_WORKING_INSTRUCTION = (
    "Working State 是訪談中的暫時工作面，不是員工事實、Memory、JD 或背景整理輸入。"
    "只有語意真的改變時才更新；不要保存隱藏推理或把缺少 JD 欄位自動變成待辦。"
    "目錄未展開的項目可按 item_id 讀取；來源只使用 Runtime 提供的 evidence_key。"
)


class WorkingStateError(ValueError):
    def __init__(self, code: str = "invalid_working_state"):
        self.code = code
        super().__init__(code)


def _json(value: object) -> str:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    )


def _digest(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def working_state_digest(value: object) -> str:
    """Canonical digest shared by the checkpoint tool and run closure."""
    return _digest(_json(value))


def _item_id(value: str) -> str:
    if (type(value) is not str or not value.startswith(_ITEM_PREFIX)
            or len(value) != len(_ITEM_PREFIX) + 32
            or any(char not in "0123456789abcdef" for char in value[len(_ITEM_PREFIX):])):
        raise ValueError("invalid_item_id")
    return value


def _new_item_id() -> str:
    return _ITEM_PREFIX + uuid4().hex


class WorkingItem(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    item_id: str
    subject: str = Field(min_length=1, max_length=240)
    known_and_open: str = Field(min_length=1, max_length=6000)
    why_it_matters: str | None = Field(default=None, min_length=1, max_length=3000)
    information_needed: str = Field(min_length=1, max_length=4000)
    status: Literal["open", "parked", "captured_pending_memory"]
    priority: Literal[
        "employee_requested", "correction_or_conflict", "high_jd_impact", "normal",
    ]
    source_refs: list[str] = Field(default_factory=list, max_length=MAX_SOURCE_REFS)
    related_refs: list[str] = Field(default_factory=list, max_length=MAX_RELATED_REFS)

    @field_validator("item_id")
    @classmethod
    def valid_item_id(cls, value: str) -> str:
        return _item_id(value)

    @field_validator("subject", "known_and_open", "why_it_matters", "information_needed")
    @classmethod
    def meaningful_text(cls, value: str | None) -> str | None:
        if value is not None and (not value.strip() or "\x00" in value):
            raise ValueError("invalid_text")
        return value

    @field_validator("source_refs", "related_refs")
    @classmethod
    def unique_refs(cls, value: list[str]) -> list[str]:
        if (len(set(value)) != len(value)
                or any(type(item) is not str or not item.strip() or "\x00" in item
                       or len(item.encode("utf-8")) > 4096 for item in value)):
            raise ValueError("invalid_refs")
        return value


class InterviewWorkingState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    format_version: Literal[1] = 1
    focus_item_id: str | None = None
    items: list[WorkingItem] = Field(default_factory=list, max_length=MAX_WORKING_ITEMS)

    @field_validator("focus_item_id")
    @classmethod
    def valid_focus_id(cls, value: str | None) -> str | None:
        return _item_id(value) if value is not None else None

    @model_validator(mode="after")
    def coherent(self):
        identifiers = [item.item_id for item in self.items]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("duplicate_item")
        if self.focus_item_id is not None:
            focus = next((item for item in self.items if item.item_id == self.focus_item_id), None)
            if focus is None or focus.status != "open":
                raise ValueError("invalid_focus")
        return self


class _Create(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["create"]
    subject: str = Field(min_length=1, max_length=240)
    known_and_open: str = Field(min_length=1, max_length=6000)
    information_needed: str = Field(min_length=1, max_length=4000)
    why_it_matters: str | None = Field(default=None, min_length=1, max_length=3000)
    priority: Literal[
        "employee_requested", "correction_or_conflict", "high_jd_impact", "normal",
    ] = "normal"
    source_evidence_keys: list[str] = Field(default_factory=list, max_length=MAX_SOURCE_REFS)
    related_handles: list[str] = Field(default_factory=list, max_length=MAX_RELATED_REFS)
    make_focus: bool = False


class _Revise(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["revise"]
    item_id: str
    subject: str | None = Field(default=None, min_length=1, max_length=240)
    known_and_open: str | None = Field(default=None, min_length=1, max_length=6000)
    information_needed: str | None = Field(default=None, min_length=1, max_length=4000)
    why_it_matters: str | None = Field(default=None, max_length=3000)
    priority: Literal[
        "employee_requested", "correction_or_conflict", "high_jd_impact", "normal",
    ] | None = None
    source_evidence_keys: list[str] | None = Field(default=None, max_length=MAX_SOURCE_REFS)
    related_handles: list[str] | None = Field(default=None, max_length=MAX_RELATED_REFS)

    @field_validator("item_id")
    @classmethod
    def valid_item_id(cls, value: str) -> str:
        return _item_id(value)

    @model_validator(mode="after")
    def has_patch(self):
        if not (self.model_fields_set - {"op", "item_id"}):
            raise ValueError("empty_patch")
        for name in ("subject", "known_and_open", "information_needed", "priority",
                     "source_evidence_keys", "related_handles"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError("invalid_patch")
        if "why_it_matters" in self.model_fields_set and self.why_it_matters is not None:
            if not self.why_it_matters.strip() or "\x00" in self.why_it_matters:
                raise ValueError("invalid_text")
        return self


class _Lifecycle(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["park", "reopen", "mark_captured"]
    item_id: str

    @field_validator("item_id")
    @classmethod
    def valid_item_id(cls, value: str) -> str:
        return _item_id(value)


class _Remove(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["remove"]
    item_id: str
    reason: Literal["memory_reconciled", "no_longer_relevant", "superseded"]
    memory_handle: str | None = Field(default=None, min_length=1, max_length=4096)
    source_evidence_key: str | None = Field(default=None, min_length=3, max_length=64)
    replacement_item_id: str | None = None

    @field_validator("item_id", "replacement_item_id")
    @classmethod
    def valid_item_id(cls, value: str | None) -> str | None:
        return _item_id(value) if value is not None else None

    @model_validator(mode="after")
    def one_guard(self):
        present = {
            "memory_reconciled": self.memory_handle is not None,
            "no_longer_relevant": self.source_evidence_key is not None,
            "superseded": self.replacement_item_id is not None,
        }
        if not present[self.reason] or sum(present.values()) != 1:
            raise ValueError("invalid_remove_guard")
        return self


class _SetFocus(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    op: Literal["set_focus"]
    item_id: str | None

    @field_validator("item_id")
    @classmethod
    def valid_item_id(cls, value: str | None) -> str | None:
        return _item_id(value) if value is not None else None


_Operation = Annotated[
    _Create | _Revise | _Lifecycle | _Remove | _SetFocus,
    Field(discriminator="op"),
]


class WorkingStateUpdateInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    operations: list[_Operation] = Field(min_length=1, max_length=MAX_BATCH_OPERATIONS)


_MODEL_WORKING_FIELDS = {
    "subject": "text",
    "known_and_open": "text",
    "information_needed": "text",
    "why_it_matters": "text",
    "priority": "priority",
    "source_evidence_keys": "evidence_keys",
    "related_handles": "related_handles",
}
_MODEL_WORKING_PRIORITIES = [
    "employee_requested", "correction_or_conflict", "high_jd_impact", "normal",
]


def _strict_nullable(kind: str) -> dict:
    return {"type": [kind, "null"]}


def _strict_object(properties: dict) -> dict:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties,
        "required": list(properties),
    }


def _model_revise_schema() -> dict:
    return _strict_object({
        "op": {"type": "string", "enum": ["revise"]},
        "item_id": {"type": "string"},
        "changes": {
            "type": "array", "minItems": 1, "maxItems": len(_MODEL_WORKING_FIELDS),
            "items": _strict_object({
                "field": {
                    "type": "string", "enum": list(_MODEL_WORKING_FIELDS),
                    "description": "要修改的 Working State 欄位；只能選本工具列出的欄位。",
                },
                "action": {
                    "type": "string", "enum": ["set", "clear"],
                    "description": "set 設定新值；clear 明確清除。只有既有 Domain 允許清除的欄位可使用 clear。",
                },
                "text": {
                    **_strict_nullable("string"),
                    "description": "field 為 subject、known_and_open、information_needed 或 why_it_matters 且 action=set 時填文字；其他情況填 null。",
                },
                "priority": {"type": ["string", "null"],
                              "enum": [*_MODEL_WORKING_PRIORITIES, None],
                              "description": "field 為 priority 且 action=set 時填優先級；其他情況填 null。"},
                "evidence_keys": {"type": ["array", "null"],
                                   "items": {"type": "string"},
                                   "maxItems": MAX_SOURCE_REFS,
                                   "description": "field 為 source_evidence_keys 且 action=set 時填 Runtime 提供且本輪可用的 evidence key；其他情況填 null。"},
                "related_handles": {"type": ["array", "null"],
                                     "items": {"type": "string"},
                                     "maxItems": MAX_RELATED_REFS,
                                     "description": "field 為 related_handles 且 action=set 時填 Runtime 提供的相關項目 handle；其他情況填 null。"},
            }),
        },
    })


def _model_create_schema() -> dict:
    return _strict_object({
        "op": {"type": "string", "enum": ["create"]},
        "subject": {"type": "string", "minLength": 1, "maxLength": 240},
        "known_and_open": {"type": "string", "minLength": 1, "maxLength": 6000},
        "information_needed": {"type": "string", "minLength": 1, "maxLength": 4000},
        "why_it_matters": {"type": ["string", "null"], "minLength": 1,
                            "maxLength": 3000},
        "priority": {"type": "string", "enum": _MODEL_WORKING_PRIORITIES},
        "source_evidence_keys": {"type": "array", "items": {"type": "string"},
                                  "maxItems": MAX_SOURCE_REFS},
        "related_handles": {"type": "array", "items": {"type": "string"},
                             "maxItems": MAX_RELATED_REFS},
        "make_focus": {"type": "boolean"},
    })


def _model_lifecycle_schema() -> dict:
    return _strict_object({
        "op": {"type": "string", "enum": ["park", "reopen", "mark_captured"]},
        "item_id": {"type": "string"},
    })


def _model_remove_schema() -> dict:
    return _strict_object({
        "op": {"type": "string", "enum": ["remove"]},
        "item_id": {"type": "string"},
        "reason": {"type": "string", "enum": [
            "memory_reconciled", "no_longer_relevant", "superseded",
        ]},
        "memory_handle": _strict_nullable("string"),
        "source_evidence_key": _strict_nullable("string"),
        "replacement_item_id": _strict_nullable("string"),
    })


def _model_focus_schema() -> dict:
    return _strict_object({
        "op": {"type": "string", "enum": ["set_focus"]},
        "item_id": _strict_nullable("string"),
    })


def model_working_state_schema() -> dict:
    """Return the strict model view; Domain input remains the authority."""
    return _strict_object({
        "operations": {
            "type": "array", "minItems": 1, "maxItems": MAX_BATCH_OPERATIONS,
            "items": {"anyOf": [
                _model_create_schema(),
                _model_revise_schema(),
                _model_lifecycle_schema(),
                _model_remove_schema(),
                _model_focus_schema(),
            ]},
        },
    })


def _model_working_state_to_domain(arguments: object) -> dict:
    """Translate only the strict revise representation into the Domain shape."""
    if type(arguments) is not dict or set(arguments) != {"operations"}:
        raise ValueError("invalid_working_state_wire")
    operations = arguments["operations"]
    if type(operations) is not list:
        raise ValueError("invalid_working_state_wire")

    translated = []
    for operation in operations:
        if type(operation) is not dict:
            raise ValueError("invalid_working_state_wire")
        if operation.get("op") != "revise":
            translated.append(operation)
            continue
        if set(operation) != {"op", "item_id", "changes"}:
            raise ValueError("invalid_working_state_wire")
        changes = operation["changes"]
        if type(changes) is not list or not changes:
            raise ValueError("empty_patch")
        patch = {"op": "revise", "item_id": operation["item_id"]}
        seen = set()
        for change in changes:
            if (type(change) is not dict
                    or set(change) != {
                        "field", "action", "text", "priority", "evidence_keys",
                        "related_handles",
                    }):
                raise ValueError("invalid_working_state_wire")
            field = change["field"]
            action = change["action"]
            if field not in _MODEL_WORKING_FIELDS:
                raise ValueError("unknown_field")
            if field in seen:
                raise ValueError("duplicate_field")
            seen.add(field)
            value_key = _MODEL_WORKING_FIELDS[field]
            value_keys = ("text", "priority", "evidence_keys", "related_handles")
            if action == "clear":
                if (field != "why_it_matters"
                        or any(change[key] is not None for key in value_keys)):
                    raise ValueError("field_cannot_clear")
                patch[field] = None
                continue
            if action != "set":
                raise ValueError("unknown_action")
            if any(change[key] is not None for key in value_keys if key != value_key):
                raise ValueError("unexpected_value")
            value = change[value_key]
            if value is None:
                raise ValueError("set_requires_value")
            patch[field] = value
        if len(patch) == 2:
            raise ValueError("empty_patch")
        translated.append(patch)
    return {"operations": translated}


@dataclass(frozen=True)
class WorkingEvidence:
    evidence_key: str
    source_reference: str
    scope_kind: Literal["current_turn", "working_item"]
    scope_id: str
    status: Literal["visible", "available", "read_complete"]
    next_offset: int | None = 0


def checked_working_state(value: object) -> InterviewWorkingState | None:
    if value is None:
        return None
    try:
        return InterviewWorkingState.model_validate(value, strict=True)
    except Exception:
        raise WorkingStateError() from None


def _validate_state_sources(state: InterviewWorkingState, context: object) -> None:
    owner = getattr(getattr(context, "memory_session", None), "source", None)
    if owner is None:
        return
    try:
        for item in state.items:
            for reference in item.source_refs:
                owner.validate_reference(reference)
    except Exception:
        raise WorkingStateError("invalid_working_source") from None


def _scope(context: object) -> tuple[str, str, str]:
    try:
        values = tuple(getattr(context, name) for name in ("dataset_id", "document_id", "run_id"))
        if any(str(UUID(value)) != value for value in values):
            raise ValueError()
        return values
    except Exception:
        raise WorkingStateError("invalid_working_state_context") from None


def _source_notice(value: object, context: object) -> dict | None:
    if value is None:
        return None
    try:
        dataset_id, document_id, run_id = _scope(context)
        if (type(value) is not dict
                or set(value) != {"type", "source_ref", "messages", "instruction"}
                or value["type"] != "conversation_source_notice"
                or type(value["source_ref"]) is not str
                or type(value["messages"]) is not list
                or type(value["instruction"]) is not str):
            raise ValueError()
        messages = value["messages"]
        if (not messages or any(type(item) is not dict
                or set(item) != {"message_id", "role"}
                or type(item["message_id"]) is not str
                or item["role"] not in {"user", "assistant"} for item in messages)):
            raise ValueError()
        owner = getattr(getattr(context, "memory_session", None), "source", None)
        if owner is not None:
            owner.validate_reference(value["source_ref"])
        from .memory_context import issue_scoped_evidence_key
        key = issue_scoped_evidence_key(
            dataset_id=dataset_id, document_id=document_id, run_id=run_id,
            scope_kind="current_turn", scope_id=run_id,
            source_reference=value["source_ref"],
        )
        return {**value, "evidence_key": key}
    except WorkingStateError:
        raise
    except Exception:
        raise WorkingStateError("invalid_working_source") from None


def sanitized_source_notice(value: object, context: object) -> dict | None:
    notice = _source_notice(value, context)
    if notice is None:
        return None
    return {
        "type": "conversation_source_notice",
        "evidence_key": notice["evidence_key"],
        "messages": notice["messages"],
        "instruction": _SOURCE_INSTRUCTION,
    }


def _item_key(context: object, item_id: str, source_reference: str) -> str:
    dataset_id, document_id, run_id = _scope(context)
    from .memory_context import issue_scoped_evidence_key
    return issue_scoped_evidence_key(
        dataset_id=dataset_id, document_id=document_id, run_id=run_id,
        scope_kind="working_item", scope_id=item_id,
        source_reference=source_reference,
    )


def _project_item(item: WorkingItem, context: object) -> dict:
    return {
        "item_id": item.item_id,
        "subject": item.subject,
        "known_and_open": item.known_and_open,
        "why_it_matters": item.why_it_matters,
        "information_needed": item.information_needed,
        "status": item.status,
        "priority": item.priority,
        "evidence_keys": [
            _item_key(context, item.item_id, reference) for reference in item.source_refs
        ],
        "related_handles": item.related_refs,
    }


def working_state_notice(state: object, context: object) -> dict:
    current = checked_working_state(state)
    if current is None:
        current = InterviewWorkingState()
    _validate_state_sources(current, context)
    expanded = {
        item.item_id for item in current.items
        if item.item_id == current.focus_item_id or item.priority == "correction_or_conflict"
    }
    return {
        "type": "interview_working_state",
        "instruction": _WORKING_INSTRUCTION,
        "focus_item_id": current.focus_item_id,
        "item_count": len(current.items),
        "directory": [{
            "item_id": item.item_id,
            "subject": item.subject,
            "status": item.status,
            "priority": item.priority,
        } for item in current.items],
        "expanded_items": [
            _project_item(item, context) for item in current.items if item.item_id in expanded
        ],
        "read_tool": "read_interview_working_item",
    }


def _turn_messages(messages: object, run_id: str) -> list:
    if type(messages) not in (list, tuple):
        raise WorkingStateError()
    positions = [index for index, message in enumerate(messages)
                 if isinstance(message, HumanMessage) and message.id == run_id]
    if len(positions) != 1:
        raise WorkingStateError()
    return list(messages[positions[0]:])


def _read_item_ids(messages: object, state: InterviewWorkingState, context: object) -> set[str]:
    _, _, run_id = _scope(context)
    scoped = _turn_messages(messages, run_id)
    calls: dict[str, dict] = {}
    for message in scoped:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call.get("name") == "read_interview_working_item":
                    call_id = call.get("id")
                    if type(call_id) is not str or not call_id or call_id in calls:
                        raise WorkingStateError()
                    calls[call_id] = call
    known = {item.item_id: item for item in state.items}
    result: set[str] = set()
    seen: set[str] = set()
    dataset_id, document_id, run_id = _scope(context)
    for message in scoped:
        if (not isinstance(message, ToolMessage)
                or message.tool_call_id not in calls):
            continue
        if message.tool_call_id in seen:
            raise WorkingStateError()
        seen.add(message.tool_call_id)
        if message.status != "success":
            continue
        call = calls[message.tool_call_id]
        artifact = message.artifact
        try:
            item_id = call["args"]["item_id"]
            item = known[item_id]
            content = _json(_project_item(item, context))
            if (type(artifact) is not dict or artifact != {
                    "format_version": 1, "kind": "working_item",
                    "dataset_id": dataset_id, "document_id": document_id,
                    "run_id": run_id, "item_id": item_id,
                    "content_digest": _digest(content),
                    "source_refs": item.source_refs,
                    } or message.content != content):
                raise ValueError()
        except Exception:
            raise WorkingStateError() from None
        result.add(item_id)
    return result


def _working_evidence_progress(messages: object, available: dict[str, WorkingEvidence],
                               context: object) -> dict[str, int | None]:
    _, _, run_id = _scope(context)
    scoped = _turn_messages(messages, run_id)
    calls: dict[str, dict] = {}
    for message in scoped:
        if isinstance(message, AIMessage):
            for call in message.tool_calls:
                if call.get("name") == "read_evidence":
                    call_id = call.get("id")
                    if type(call_id) is not str or not call_id or call_id in calls:
                        raise WorkingStateError()
                    calls[call_id] = call
    progress: dict[str, int | None] = {}
    seen: set[str] = set()
    dataset_id, document_id, run_id = _scope(context)
    for message in scoped:
        if not isinstance(message, ToolMessage) or message.tool_call_id not in calls:
            continue
        artifact = message.artifact
        if type(artifact) is not dict or artifact.get("kind") != "working_evidence":
            continue
        if message.tool_call_id in seen:
            raise WorkingStateError()
        seen.add(message.tool_call_id)
        if message.status != "success":
            continue
        try:
            call = calls[message.tool_call_id]
            key = call["args"]["evidence_key"]
            entry = available[key]
            offset = progress.get(key, 0)
            if offset is None:
                offset = 0
            expected = {
                "format_version": 1, "kind": "working_evidence",
                "dataset_id": dataset_id, "document_id": document_id,
                "run_id": run_id, "scope_kind": entry.scope_kind,
                "scope_id": entry.scope_id, "evidence_key": key,
                "source_reference": entry.source_reference,
                "read_offset": offset,
                "next_offset": artifact.get("next_offset"),
                "content_digest": _digest(message.content),
            }
            if artifact != expected:
                raise ValueError()
            following = artifact["next_offset"]
            if following is not None and (type(following) is not int or following <= offset):
                raise ValueError()
            payload = json.loads(message.content)
            if (payload.get("evidence_key") != key
                    or payload.get("has_more") is not (following is not None)):
                raise ValueError()
            progress[key] = following
        except Exception:
            raise WorkingStateError() from None
    return progress


def working_evidence_catalog(*, state: object, context: object, messages: object,
                             raw_source_notice: object) -> dict[str, WorkingEvidence]:
    current = checked_working_state(state)
    if current is None:
        current = InterviewWorkingState()
    _validate_state_sources(current, context)
    notice = _source_notice(raw_source_notice, context)
    available: dict[str, WorkingEvidence] = {}
    if notice is not None:
        key = notice["evidence_key"]
        available[key] = WorkingEvidence(
            key, notice["source_ref"], "current_turn", _scope(context)[2], "visible", 0,
        )
    expanded = {
        item.item_id for item in current.items
        if item.item_id == current.focus_item_id or item.priority == "correction_or_conflict"
    }
    expanded |= _read_item_ids(messages, current, context)
    for item in current.items:
        if item.item_id not in expanded:
            continue
        for reference in item.source_refs:
            key = _item_key(context, item.item_id, reference)
            entry = WorkingEvidence(key, reference, "working_item", item.item_id, "available", 0)
            if key in available and available[key] != entry:
                raise WorkingStateError()
            available[key] = entry
    progress = _working_evidence_progress(messages, available, context)
    return {
        key: WorkingEvidence(
            entry.evidence_key, entry.source_reference, entry.scope_kind, entry.scope_id,
            "read_complete" if progress.get(key, 0) is None else entry.status,
            progress.get(key, 0),
        )
        for key, entry in available.items()
    }


def working_evidence_projection(entry: WorkingEvidence, page: dict, context: object) -> tuple[str, dict]:
    dataset_id, document_id, run_id = _scope(context)
    content = _json({
        "evidence_key": entry.evidence_key,
        "source_order": "oldest_to_newest",
        "segments": [{
            "role": segment["role"],
            "text": segment["text"],
            "continued_from_previous_page": segment["text_offset"] > 0,
        } for segment in page["segments"]],
        "has_more": page["next_offset"] is not None,
    })
    return content, {
        "format_version": 1, "kind": "working_evidence",
        "dataset_id": dataset_id, "document_id": document_id, "run_id": run_id,
        "scope_kind": entry.scope_kind, "scope_id": entry.scope_id,
        "evidence_key": entry.evidence_key,
        "source_reference": entry.source_reference,
        "read_offset": page["read_offset"], "next_offset": page["next_offset"],
        "content_digest": _digest(content),
    }


def _runtime_material(runtime: ToolRuntime):
    context = runtime.context
    dataset_id, document_id, run_id = _scope(context)
    if get_config().get("configurable", {}).get("thread_id") != document_id:
        raise WorkingStateError("invalid_working_state_context")
    source = context.source_notice(runtime.state.get("messages", ())) \
        if context.source_notice is not None else None
    current = checked_working_state(runtime.state.get("interview_working_state"))
    try:
        from .memory_context import memory_session
        session = memory_session(runtime) if context.memory_session is not None else None
    except Exception:
        raise WorkingStateError("working_state_dependency_unavailable") from None
    if current is None:
        current = InterviewWorkingState()
    catalog = working_evidence_catalog(
        state=current.model_dump(mode="json"), context=context,
        messages=runtime.state.get("messages", ()), raw_source_notice=source,
    )
    return context, current, source, session, catalog


def _allowed_related_handles(runtime: ToolRuntime, current: InterviewWorkingState) -> set[str]:
    allowed = {value for item in current.items for value in item.related_refs}
    try:
        from .memory_context import layered_read_proof
        from .memory_context import memory_session
        session = memory_session(runtime)
        if session.head is not None and session.artifacts.bundle_base(session.head.memory) is not None:
            proof = layered_read_proof(
                runtime.state.get("messages", ()), dataset_id=session.dataset_id,
                document_id=session.document_id, run_id=session.run_id,
                revision=session.head.revision, version_id=session.head.memory.version_id,
            )
            allowed |= {f"case:{case_id}" for case_id in proof.case_evidence}
            allowed |= {f"understanding:{identity}" for identity in proof.understanding_ids}
    except Exception:
        # No layered read means no new Memory handle is eligible. Existing
        # stored handles remain representable until the consultant revises them.
        pass
    return allowed


def _resolve_sources(keys: list[str], *, catalog: dict[str, WorkingEvidence],
                     existing: list[str], context: object, raw_source_notice: object,
                     session: object | None) -> list[str]:
    if len(set(keys)) != len(keys):
        raise WorkingStateError("invalid_working_state_update")
    references: list[str] = []
    for key in keys:
        entry = catalog.get(key)
        if entry is None or (entry.status not in {"visible", "read_complete"}
                             and entry.source_reference not in existing):
            raise WorkingStateError("working_source_not_read")
        references.append(entry.source_reference)
    if len(set(references)) != len(references):
        raise WorkingStateError("invalid_working_state_update")
    if len(references) <= 1:
        return references
    notice = _source_notice(raw_source_notice, context)
    service = getattr(getattr(session, "source", None), "service", None)
    if notice is None or service is None:
        raise WorkingStateError("working_source_not_available")
    wanted, ordered, offset = set(references), [], 0
    try:
        while True:
            page = service.history_exchanges(
                notice["source_ref"], _scope(context)[1], offset=offset,
            )
            ordered.extend(exchange.source_ref for exchange in page["exchanges"]
                           if exchange.source_ref in wanted)
            if page["next_offset"] is None:
                break
            offset = page["next_offset"]
    except Exception:
        raise WorkingStateError("working_source_not_available") from None
    if set(ordered) != wanted or len(ordered) != len(wanted):
        raise WorkingStateError("working_source_not_available")
    return ordered


def _memory_handles(runtime: ToolRuntime, session: object | None) -> set[str]:
    if session is None or session.head is None:
        return set()
    try:
        from .memory_context import layered_read_proof
        proof = layered_read_proof(
            runtime.state.get("messages", ()), dataset_id=session.dataset_id,
            document_id=session.document_id, run_id=session.run_id,
            revision=session.head.revision, version_id=session.head.memory.version_id,
        )
        return ({f"case:{identity}" for identity in proof.case_evidence}
                | {f"understanding:{identity}" for identity in proof.understanding_ids})
    except Exception:
        return set()


def _apply_update(parsed: WorkingStateUpdateInput, *, runtime: ToolRuntime,
                  context: object, current: InterviewWorkingState,
                  raw_source_notice: object, session: object | None,
                  catalog: dict[str, WorkingEvidence]) -> tuple[InterviewWorkingState, list[dict]]:
    items = {item.item_id: item for item in current.items}
    order = [item.item_id for item in current.items]
    focus = current.focus_item_id
    lifecycle: set[str] = set()
    revised: set[str] = set()
    explicit_focus = 0
    created: list[dict] = []
    related = _allowed_related_handles(runtime, current)
    memory_handles = _memory_handles(runtime, session)

    def item(identity: str) -> WorkingItem:
        try:
            return items[identity]
        except KeyError:
            raise WorkingStateError("working_item_not_found") from None

    def checked_related(values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        if len(set(values)) != len(values) or any(value not in related for value in values):
            raise WorkingStateError("unknown_related_handle")
        return list(values)

    for index, operation in enumerate(parsed.operations):
        if isinstance(operation, _Create):
            identity = _new_item_id()
            sources = _resolve_sources(
                operation.source_evidence_keys, catalog=catalog, existing=[],
                context=context, raw_source_notice=raw_source_notice, session=session,
            )
            values = checked_related(operation.related_handles) or []
            candidate = WorkingItem(
                item_id=identity, subject=operation.subject,
                known_and_open=operation.known_and_open,
                why_it_matters=operation.why_it_matters,
                information_needed=operation.information_needed,
                status="open", priority=operation.priority,
                source_refs=sources, related_refs=values,
            )
            items[identity] = candidate
            order.append(identity)
            created.append({"operation_index": index, "item_id": identity})
            if operation.make_focus:
                explicit_focus += 1
                focus = identity
            continue

        if isinstance(operation, _SetFocus):
            explicit_focus += 1
            if operation.item_id is not None and item(operation.item_id).status != "open":
                raise WorkingStateError("working_item_not_open")
            focus = operation.item_id
            continue

        identity = operation.item_id
        current_item = item(identity)
        if isinstance(operation, _Revise):
            if identity in revised:
                raise WorkingStateError("duplicate_working_item_operation")
            revised.add(identity)
            changes = {}
            for name in ("subject", "known_and_open", "information_needed",
                         "why_it_matters", "priority"):
                if name in operation.model_fields_set:
                    changes[name] = getattr(operation, name)
            if "source_evidence_keys" in operation.model_fields_set:
                changes["source_refs"] = _resolve_sources(
                    operation.source_evidence_keys or [], catalog=catalog,
                    existing=current_item.source_refs, context=context,
                    raw_source_notice=raw_source_notice, session=session,
                )
            if "related_handles" in operation.model_fields_set:
                changes["related_refs"] = checked_related(operation.related_handles) or []
            items[identity] = current_item.model_copy(update=changes)
            WorkingItem.model_validate(items[identity].model_dump(mode="json"), strict=True)
            continue

        if identity in lifecycle:
            raise WorkingStateError("duplicate_working_item_operation")
        lifecycle.add(identity)
        if isinstance(operation, _Lifecycle):
            expected = {"park": "open", "reopen": "parked", "mark_captured": "open"}
            target = {"park": "parked", "reopen": "open",
                      "mark_captured": "captured_pending_memory"}
            if current_item.status != expected[operation.op]:
                raise WorkingStateError("invalid_working_item_transition")
            items[identity] = current_item.model_copy(update={"status": target[operation.op]})
            if focus == identity and target[operation.op] != "open":
                focus = None
            continue

        if operation.reason == "memory_reconciled":
            if operation.memory_handle not in memory_handles:
                raise WorkingStateError("working_memory_not_read")
        elif operation.reason == "no_longer_relevant":
            evidence = catalog.get(operation.source_evidence_key)
            if evidence is None or evidence.status not in {"visible", "read_complete"}:
                raise WorkingStateError("working_source_not_read")
        else:
            replacement = operation.replacement_item_id
            if replacement == identity or replacement not in items:
                raise WorkingStateError("working_replacement_not_found")
        del items[identity]
        order.remove(identity)
        if focus == identity:
            focus = None

    if explicit_focus > 1:
        raise WorkingStateError("duplicate_working_focus")
    if len(items) > MAX_WORKING_ITEMS:
        raise WorkingStateError("working_state_too_large")
    if focus is not None and (focus not in items or items[focus].status != "open"):
        raise WorkingStateError("working_item_not_open")
    result = InterviewWorkingState(
        focus_item_id=focus,
        items=[items[identity] for identity in order],
    )
    return result, created


def build_working_state_tools() -> list[BaseTool]:
    @tool("read_interview_working_item", response_format="content_and_artifact")
    def read_interview_working_item(item_id: str, runtime: ToolRuntime):
        """依目錄中的 item_id 讀取一筆完整訪談 Working State；不要猜 ID。"""
        try:
            context, current, _, _, _ = _runtime_material(runtime)
            identity = _item_id(item_id)
            item = next(value for value in current.items if value.item_id == identity)
            content = _json(_project_item(item, context))
            dataset_id, document_id, run_id = _scope(context)
            return content, {
                "format_version": 1, "kind": "working_item",
                "dataset_id": dataset_id, "document_id": document_id,
                "run_id": run_id, "item_id": identity,
                "content_digest": _digest(content), "source_refs": item.source_refs,
            }
        except (StopIteration, ValueError):
            raise ToolException("working_item_not_found: 請只使用目前目錄中的 item_id。") from None
        except WorkingStateError as error:
            raise ToolException(f"{error.code}: Working State 目前無法讀取。") from None

    def update(runtime: ToolRuntime, **arguments):
        try:
            try:
                domain_arguments = _model_working_state_to_domain(arguments)
            except ValueError:
                raise ToolException(
                    "invalid_working_state_update: 請依 strict operation 格式修正；本批未套用。"
                ) from None
            parsed = WorkingStateUpdateInput.model_validate(domain_arguments, strict=True)
            context, current, source, session, catalog = _runtime_material(runtime)
            updated, created = _apply_update(
                parsed, runtime=runtime, context=context, current=current,
                raw_source_notice=source, session=session, catalog=catalog,
            )
            content = _json({
                "status": "updated", "effect": "working_state_updated",
                "created": created, "focus_item_id": updated.focus_item_id,
                "item_count": len(updated.items),
            })
            artifact = {
                "format_version": 1,
                "kind": WORKING_STATE_UPDATE_KIND,
                "dataset_id": context.dataset_id,
                "document_id": context.document_id,
                "run_id": context.run_id,
                "input_digest": working_state_digest(parsed.model_dump(mode="json")),
                "state_digest": working_state_digest(updated.model_dump(mode="json")),
            }
            message = ToolMessage(
                id=str(uuid4()), name=WORKING_STATE_UPDATE_NAME,
                tool_call_id=runtime.tool_call_id, content=content,
                artifact=artifact, status="success",
            )
            return Command(update={
                "messages": [message],
                "interview_working_state": updated.model_dump(mode="json"),
            })
        except ValidationError:
            raise ToolException(
                "invalid_working_state_update: 請使用一批明確的 create、revise、lifecycle、remove 或 set_focus 操作。"
            ) from None
        except WorkingStateError as error:
            raise ToolException(f"{error.code}: 本批 Working State 變更未套用。") from None

    from langchain_core.tools import StructuredTool
    update_tool = StructuredTool(
        name="update_interview_working_state",
        description=(
            "只在訪談 Focus、未完線索、已知／未知、優先順序或個別項目狀態真的改變時，"
            "原子更新同一文件的 Working State。它不是 Memory、JD、背景整理或問題清單；"
            "create 只寫語意，revise 只送改變欄位，生命週期用單一 operation。"
            "來源只選 Runtime 提供且當輪可見或已完整讀取的 evidence key；"
            "不要提供 source reference、文件／run、版本、ID、時間、receipt 或 offset。"
        ),
        args_schema=model_working_state_schema(),
        func=update,
        handle_validation_error=(
            "invalid_working_state_update: 請依 operation 的必要欄位修正；本批未套用。"
        ),
    )
    read_interview_working_item.handle_tool_error = True
    read_interview_working_item.handle_validation_error = (
        "invalid_input: 請只提供目前目錄中的 item_id。"
    )
    return [read_interview_working_item, update_tool]
