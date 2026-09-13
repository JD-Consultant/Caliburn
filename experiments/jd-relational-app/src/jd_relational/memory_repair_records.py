"""Pure C call/result bindings in native ToolMessage artifacts.

Artifacts are App metadata, not model content (LangChain 1.4 / core 1.6.3).
This module performs no reads, publication, execution, retry or recovery. An
artifact validates a saved representation; a real receipt remains publication
authority. The caller owns original-call admission and stopped-task proofs.
"""
from dataclasses import asdict
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID, uuid4

from caliburn_memory.memory import MemoryVersion
from caliburn_memory.patch import MAX_PATCH_CHARACTERS, PATHS
from caliburn_memory.publication import PublishedHead, PublishRequest
from caliburn_memory.repair import MemoryEdit
from langchain_core.messages import AIMessage, ToolMessage
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

REPAIR_NAME = "repair_memory"
_CORRECTABLE = frozenset({"invalid_edit", "stale", "no_memory"})
_STATUSES = _CORRECTABLE | {"applied", "repair_limit", "not_executed", "not_published"}
_PATHS = tuple(PATHS.values())


class MemoryRepairError(ValueError):
    def __init__(self, code="invalid_repair_binding"):
        if type(code) is not str or code not in {"invalid_repair_input", "invalid_repair_binding", "invalid_repair_message"}:
            code = "invalid_repair_binding"
        self.code = code
        super().__init__(code)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError()
    return value


def _text(value, *, maximum=None):
    if (type(value) is not str or not value.strip() or "\x00" in value
            or maximum is not None and len(value) > maximum):
        raise ValueError()
    return value


def _shape(value, keys):
    if type(value) is not dict or set(value) != set(keys):
        raise ValueError()
    return value


def _memory(value, document_id):
    _shape(value, ("document_id", "version_id"))
    if _uuid(value["document_id"]) != document_id:
        raise ValueError()
    return {"document_id": document_id, "version_id": _uuid(value["version_id"])}


def _head(value, document_id):
    if value is None:
        return None
    if type(value) is PublishedHead:
        value = asdict(value)
    _shape(value, ("revision", "memory", "processed_source"))
    if type(value["revision"]) is not int or value["revision"] < 1:
        raise ValueError()
    source = value["processed_source"]
    if source is not None:
        _text(source, maximum=4096)
    return {"revision": value["revision"], "memory": _memory(value["memory"], document_id),
            "processed_source": source}


class RepairBinding(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    format_version: Literal[1]
    dataset_id: str
    document_id: str
    run_id: str
    message_id: str
    tool_call_id: str
    operation_id: str
    input_digest: str = Field(pattern="^[0-9a-f]{64}$")
    base: dict | None
    source_reference: str

    @model_validator(mode="before")
    @classmethod
    def strict_format(cls, value):
        if type(value) is not dict or type(value.get("format_version")) is not int:
            raise ValueError()
        return value

    @field_validator("dataset_id", "document_id", "run_id", "operation_id")
    @classmethod
    def identifiers(cls, value):
        return _uuid(value)

    @field_validator("message_id", "tool_call_id")
    @classmethod
    def call_identifiers(cls, value):
        return _text(value)

    @field_validator("source_reference")
    @classmethod
    def source_shape(cls, value):
        return _text(value, maximum=4096)

    @model_validator(mode="after")
    def base_scope(self):
        _head(self.base, self.document_id)
        return self


def _binding(value):
    if type(value) is RepairBinding:
        value = value.model_dump(mode="json")
    return RepairBinding.model_validate(value)


def parse_repair_input(args) -> list[dict]:
    try:
        _shape(args, ("edits",))
        values = args["edits"]
        if type(values) is not list or not 1 <= len(values) <= 8:
            raise ValueError()
        edits = [MemoryEdit.model_validate(value) for value in values]
        if (sum(len(edit.diff) for edit in edits) > MAX_PATCH_CHARACTERS
                or any(edit.path not in _PATHS or not edit.diff.strip() for edit in edits)):
            raise ValueError()
        return [edit.model_dump(mode="json") for edit in edits]
    except Exception:
        raise MemoryRepairError("invalid_repair_input") from None


def _original_call(message, call_id=None):
    """Locate this original repair call; binding always requires a lone call.

    Only an unbound result may name one call of a response the App refused as
    invalid, and it still identifies exactly one call with its own arguments.
    """
    if (type(message) is not AIMessage or message.invalid_tool_calls
            or (len(message.tool_calls) != 1 if call_id is None else not message.tool_calls)):
        raise ValueError()
    _text(message.id)
    if call_id is None:
        call = message.tool_calls[0]
    else:
        matching = [c for c in message.tool_calls if c["id"] == _text(call_id)]
        if len(matching) != 1:
            raise ValueError()
        call = matching[0]
    if call["name"] != REPAIR_NAME:
        raise ValueError()
    _text(call["id"])
    digest = sha256(_json(call["args"]).encode("utf-8")).hexdigest()
    return call, digest


def make_repair_binding(message, *, dataset_id, document_id, run_id, base,
                        source_reference) -> RepairBinding:
    try:
        call, digest = _original_call(message)
        return RepairBinding(format_version=1, dataset_id=dataset_id, document_id=document_id,
            run_id=run_id, message_id=message.id, tool_call_id=call["id"],
            operation_id=str(uuid4()), input_digest=digest, base=_head(base, document_id),
            source_reference=source_reference)
    except Exception:
        raise MemoryRepairError() from None


def decode_repair_bindings(value, *, dataset_id, document_id, run_id) -> tuple[RepairBinding, ...]:
    try:
        scope = tuple(_uuid(v) for v in (dataset_id, document_id, run_id))
        if value is None:
            return ()  # older checkpoints have no repair bindings
        if type(value) is not list:
            raise ValueError()
        bindings = tuple(_binding(item) for item in value)
        if any((b.dataset_id, b.document_id, b.run_id) != scope for b in bindings):
            raise ValueError()
        if any(len({getattr(b, key) for b in bindings}) != len(bindings)
               for key in ("message_id", "tool_call_id", "operation_id")):
            raise ValueError()
        return bindings
    except Exception:
        raise MemoryRepairError() from None


def verify_repair_binding_message(binding, messages) -> None:
    try:
        binding = _binding(binding)
        if type(messages) not in (list, tuple):
            raise ValueError()
        matches = [m for m in messages if isinstance(m, AIMessage) and m.id == binding.message_id]
        if len(matches) != 1:
            raise ValueError()
        call, digest = _original_call(matches[0])
        if call["id"] != binding.tool_call_id or digest != binding.input_digest:
            raise ValueError()
        # Another response cannot claim this original provider call identity.
        if sum(c.get("id") == binding.tool_call_id for m in messages
               if isinstance(m, AIMessage) for c in m.tool_calls) != 1:
            raise ValueError()
    except Exception:
        raise MemoryRepairError() from None


def _request(value, binding):
    if value is None:
        return None
    if type(value) is PublishRequest:
        value = json.loads(_json(asdict(value)))
    _shape(value, ("operation_id", "memory", "expected_revision", "kind", "artifact_digest",
                   "processed_source", "repair_sources"))
    if (binding.base is None or value["operation_id"] != binding.operation_id
            or type(value["expected_revision"]) is not int
            or value["expected_revision"] != binding.base["revision"]
            or value["kind"] != "repair" or value["processed_source"] is not None
            or type(value["repair_sources"]) is not list
            or value["repair_sources"] != [binding.source_reference]
            or type(value["artifact_digest"]) is not str or len(value["artifact_digest"]) != 64
            or any(c not in "0123456789abcdef" for c in value["artifact_digest"])):
        raise ValueError()
    memory = MemoryVersion(**_memory(value["memory"], binding.document_id))
    return PublishRequest(binding.operation_id, memory, value["expected_revision"], "repair",
                          value["artifact_digest"], repair_sources=(binding.source_reference,))


def decode_repair_request(value, binding) -> PublishRequest:
    """Decode one exact native-saved request; never rebuild it from edits."""
    try:
        request = _request(value, _binding(binding))
        if request is None:
            raise ValueError()
        return request
    except Exception:
        raise MemoryRepairError("invalid_repair_message") from None


def _outcome(value, binding, request, *, strip_changes=False):
    if type(value) is not dict:
        raise ValueError()
    value = json.loads(_json(value))
    if strip_changes:
        value.pop("changes", None)
    if (set(value) - {"status", "detail", "head", "guide", "read_paths", "applied_head", "source_reference"}
            or value.get("status") not in _STATUSES):
        raise ValueError()
    _text(value.get("detail"))
    if "source_reference" in value and value["source_reference"] != binding.source_reference:
        raise ValueError()
    if "read_paths" in value:
        paths = value["read_paths"]
        if (type(paths) is not list or any(type(p) is not str or p not in _PATHS for p in paths)
                or len(set(paths)) != len(paths)):
            raise ValueError()
    status = value["status"]
    if status in {"applied", "stale", "no_memory"}:
        if "head" not in value or "guide" not in value:
            raise ValueError()
        value["head"] = _head(value["head"], binding.document_id)
        guide = value["guide"]
        if type(guide) is not str or len(guide) > 4000 or (value["head"] is None and guide != ""):
            raise ValueError()
        if binding.base and (value["head"] is None or value["head"]["revision"] < binding.base["revision"]):
            raise ValueError()
    elif "head" in value or "guide" in value:
        raise ValueError()
    if status == "applied":
        if request is None or value["head"] is None:
            raise ValueError()
        saved = _head(value.get("applied_head"), binding.document_id)
        if (saved is None or saved["memory"] != asdict(request.memory)
                or saved["revision"] != request.expected_revision + 1
                or saved["processed_source"] != binding.base["processed_source"]
                or value["head"]["revision"] < saved["revision"]
                or value["head"]["revision"] == saved["revision"] and value["head"] != saved):
            raise ValueError()
        value["applied_head"] = saved
    elif "applied_head" in value or request is not None and status != "stale":
        raise ValueError()
    return value


def _content(outcome, failures_before):
    if type(failures_before) is not int or not 0 <= failures_before <= 2:
        raise ValueError()
    result = {"status": outcome["status"], "detail": outcome["detail"],
              "read_paths": outcome.get("read_paths", list(_PATHS)),
              "retryable": outcome["status"] in _CORRECTABLE and failures_before < 1}
    if "guide" in outcome:
        result["guide"] = outcome["guide"]
    return result


def make_repair_message(binding, outcome, request=None, *, failures_before=0) -> ToolMessage:
    try:
        binding = _binding(binding)
        request = _request(request, binding)
        outcome = _outcome(outcome, binding, request, strip_changes=True)
        artifact = {"format_version": 1, "operation_id": binding.operation_id,
                    "input_digest": binding.input_digest, "outcome": outcome,
                    "request": json.loads(_json(asdict(request))) if request else None}
        return ToolMessage(content=_json(_content(outcome, failures_before)), name=REPAIR_NAME,
            tool_call_id=binding.tool_call_id, status="success" if outcome["status"] == "applied" else "error",
            artifact=artifact)
    except Exception:
        raise MemoryRepairError("invalid_repair_message") from None


NOT_EXECUTED_DETAIL = "這次 Memory 更正尚未執行；回合已停止，Memory 沒有變更。"
_UNBOUND_OUTCOME = {"status": "not_executed", "detail": NOT_EXECUTED_DETAIL}


def make_unbound_repair_message(message, call_id=None) -> ToolMessage:
    """Close one original call that stopped before any binding existed.

    No operation, base, source or request has been assigned yet, so none may be
    invented here. Only the original call and its own argument digest are kept,
    which keeps this result distinguishable from a bound correction result.
    """
    try:
        call, digest = _original_call(message, call_id)
        artifact = {"format_version": 1, "operation_id": None, "input_digest": digest,
                    "outcome": dict(_UNBOUND_OUTCOME), "request": None}
        return ToolMessage(content=_json(_content(_UNBOUND_OUTCOME, 0)), name=REPAIR_NAME,
            tool_call_id=call["id"], status="error", artifact=artifact)
    except Exception:
        raise MemoryRepairError("invalid_repair_message") from None


def validate_unbound_repair_message(result, message) -> None:
    """Accept a saved unbound result only against its own original call."""
    try:
        if type(result) is not ToolMessage or result.name != REPAIR_NAME:
            raise ValueError()
        call, digest = _original_call(message, result.tool_call_id)
        if result.tool_call_id != call["id"] or result.status != "error":
            raise ValueError()
        artifact = _shape(result.artifact, ("format_version", "operation_id", "input_digest",
                                            "outcome", "request"))
        if (type(artifact["format_version"]) is not int or artifact["format_version"] != 1
                or artifact["operation_id"] is not None or artifact["request"] is not None
                or artifact["input_digest"] != digest or artifact["outcome"] != _UNBOUND_OUTCOME
                or type(result.content) is not str
                or result.content != _json(_content(_UNBOUND_OUTCOME, 0))):
            raise ValueError()
    except Exception:
        raise MemoryRepairError("invalid_repair_message") from None


def validate_repair_message(message, binding, failures_before=0) -> tuple[dict, PublishRequest | None]:
    try:
        binding = _binding(binding)
        if (type(message) is not ToolMessage or message.name != REPAIR_NAME
                or message.tool_call_id != binding.tool_call_id):
            raise ValueError()
        artifact = _shape(message.artifact, ("format_version", "operation_id", "input_digest", "outcome", "request"))
        if (type(artifact["format_version"]) is not int or artifact["format_version"] != 1
                or artifact["operation_id"] != binding.operation_id
                or artifact["input_digest"] != binding.input_digest):
            raise ValueError()
        request = _request(artifact["request"], binding)
        outcome = _outcome(artifact["outcome"], binding, request)
        if (message.status != ("success" if outcome["status"] == "applied" else "error")
                or type(message.content) is not str or message.content != _json(_content(outcome, failures_before))):
            raise ValueError()
        return outcome, request
    except Exception:
        raise MemoryRepairError("invalid_repair_message") from None
