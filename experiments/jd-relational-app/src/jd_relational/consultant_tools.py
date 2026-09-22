"""Native named tools over existing JD ports; identity binding precedes tool SQL.

The foreground host must invoke with native sync durability. After-model state
contains only recovery identity; commands and read materials stay in this run's
memory. A missing cache never triggers source reads or command reconstruction.
"""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.config import get_config
from langgraph.errors import GraphBubbleUp
from langgraph.types import Command

from .change_transport import DESCRIPTION as CHANGE_DESCRIPTION, change_tool_output, parse_change_arguments
from .generated.reads import ChangeReadInput, ReadInput, ReadPage
from .intents import AdmittedIdentity, BoundEdit, IntentValidationError, bind_edit
from .memory_context import MEMORY_READ_NAMES, bind_memory_read_request
from .observation_projection import project_observation
from .read_transport import DESCRIPTION as READ_DESCRIPTION, parse_read_arguments, read_failure, read_tool_output
from .reads import ReadError, command_context
from .references import ReferenceCodec
from .storage.history import HistoryError
from .storage.receipts import WriteObservation
from .transport import DESCRIPTIONS, MODELS, TransportError, model_arguments, model_command, tool_output
from .working_state import WORKING_STATE_TOOL_NAMES
from caliburn_memory.requests import REQUEST_TOOL_NAME


class AiToolError(ValueError):
    """Fixed safe graph-stop code, never arbitrary arguments or exception text."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class AiToolPending(AiToolError):
    def __init__(self):
        super().__init__("ai_tool_pending")


class AiToolState(AgentState):
    jd_ai_bindings: list[dict[str, Any]]
    jd_ai_read: dict[str, Any] | None
    jd_memory_repair_bindings: list[dict[str, Any]]


_BINDING_KEYS = frozenset({"format_version", "dataset_id", "document_id", "run_id", "message_id",
    "tool_call_id", "input_digest", "operation_id", "base_revision_id", "origin", "request_digest", "command_kind"})
_READ_KEYS = frozenset({"format_version", "dataset_id", "document_id", "run_id", "revision_id",
                      "tool_message_id", "tool_call_id", "content_digest"})
_JD_READ_ARTIFACT_KEYS = frozenset({
    "format_version", "kind", "dataset_id", "document_id", "run_id",
    "tool_call_id", "content_digest", "canonical_result", "evidence",
})


@dataclass(frozen=True)
class RuntimeEvidence:
    """One Runtime-owned source handle available to the current A run."""
    evidence_key: str
    source_reference: str
    scope_kind: str
    scope_id: str
    status: str
    next_offset: int | None = 0


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(text):
    return sha256(text.encode("utf-8")).hexdigest()


def _uuid(value):
    return type(value) is str and str(UUID(value)) == value


def _hex(value):
    return type(value) is str and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _identifier(value, maximum=4096):
    return (type(value) is str and bool(value.strip()) and "\x00" not in value
            and len(value.encode("utf-8")) <= maximum)


@dataclass(frozen=True)
class AiToolBinding:
    identity: AdmittedIdentity
    dataset_id: str
    run_id: str
    message_id: str
    tool_call_id: str
    input_digest: str

    @property
    def command_kind(self):
        return self.identity.command_kind

    def to_dict(self):
        return {"format_version": 1, "dataset_id": self.dataset_id, "document_id": self.identity.document_id,
            "run_id": self.run_id, "message_id": self.message_id, "tool_call_id": self.tool_call_id,
            "input_digest": self.input_digest, "operation_id": str(self.identity.operation_id),
            "base_revision_id": str(self.identity.base_revision_id), "origin": "ai",
            "request_digest": self.identity.request_digest, "command_kind": self.command_kind}


def decode_ai_binding(value, *, dataset_id, document_id, run_id) -> AiToolBinding:
    """Shared recovery decoder. Shape/scope validation is not writer admission."""
    try:
        if (type(value) is not dict or set(value) != _BINDING_KEYS
                or type(value["format_version"]) is not int or value["format_version"] != 1
                or value["origin"] != "ai"
                or any(not _uuid(value[key]) for key in ("dataset_id", "document_id", "run_id", "operation_id", "base_revision_id"))
                or (value["dataset_id"], value["document_id"], value["run_id"]) != (dataset_id, document_id, run_id)
                or not _identifier(value["message_id"], 512) or not _identifier(value["tool_call_id"])
                or not _hex(value["input_digest"]) or not _hex(value["request_digest"])):
            raise ValueError()
        identity = AdmittedIdentity(document_id, UUID(value["operation_id"]), UUID(value["base_revision_id"]),
                                    "ai", run_id, value["request_digest"], value["command_kind"])
        return AiToolBinding(identity, dataset_id, run_id, value["message_id"], value["tool_call_id"], value["input_digest"])
    except Exception:
        raise AiToolError("invalid_ai_binding") from None


def decode_ai_bindings(value, *, dataset_id, document_id, run_id) -> tuple[AiToolBinding, ...]:
    if type(value) is not list:
        raise AiToolError("invalid_ai_binding")
    result = tuple(decode_ai_binding(item, dataset_id=dataset_id, document_id=document_id, run_id=run_id) for item in value)
    if (len({item.tool_call_id for item in result}) != len(result)
            or len({item.identity.operation_id for item in result}) != len(result)):
        raise AiToolError("invalid_ai_binding")
    return result


def verify_binding_message(binding: AiToolBinding, messages) -> None:
    """Verify the original saved AI call without rebuilding context or intent."""
    try:
        if not isinstance(binding, AiToolBinding):
            raise ValueError()
        matching = [message for message in messages if isinstance(message, AIMessage) and message.id == binding.message_id]
        if len(matching) != 1 or matching[0].invalid_tool_calls or len(matching[0].tool_calls) != 1:
            raise ValueError()
        call = matching[0].tool_calls[0]
        model_value = model_arguments(call["name"], call["args"])
        command = model_command(call["name"], call["args"])
        if (call["id"] != binding.tool_call_id or command["tool"] != binding.command_kind
                or _digest(_json({"name": command["tool"], "args": model_value["arguments"]})) != binding.input_digest):
            raise ValueError()
    except Exception:
        raise AiToolError("invalid_ai_binding") from None


def _unbound(message, action="correct_arguments"):
    return {"status": "invalid_input", "effect": "unchanged", "receipt_durability": "unconfirmed",
        "operation_ref": None, "result_revision_ref": None, "change_ref": None,
        "error": {"code": "invalid_input", "message": message, "related_refs": []}, "next_action": action}


def _no_sources(*_):
    raise ReadError("source_not_available")


def _error_result(error):
    code = getattr(error, "code", None)
    if code == "selection_not_available":
        return _unbound("目前沒有可驗證的來源或選區接點；本次未進入保存。", "stop")
    if code == "invalid_ref":
        return _unbound(
            "提交的引用不是最新一次成功的 jd_read current 發配的相容可寫引用；"
            "請重新讀取；新增子項時從 type=container 記錄依 child_kind／owner_ref 配對後"
            "原樣複製 container_ref，不可使用 item_ref 或 type=item 記錄中的 container_ref，"
            "不可推測、縮短或沿用舊引用；本次未進入保存。",
            "reread_current",
        )
    if code in {"stale_view", "target_missing", "revision_missing", "read_required"}:
        return _unbound("請先用 jd_read current 取得本輪目前稿與可寫引用；本次未進入保存。", "reread_current")
    if code == "invalid_jd_evidence":
        return _unbound("目前的 JD 讀取接點已失效；請重新用 jd_read current 取得本輪內容。", "reread_current")
    if code == "source_not_read":
        return _unbound("請先用 read_evidence 完整讀取本輪已提供的證據；本次未進入保存。")
    return _unbound("本次工具參數不符；請依具名工具的欄位與限制修正。")


def _jd_read_message(name: str, call_id: str, result: dict, *, dataset_id: str,
                     document_id: str, run_id: str) -> ToolMessage:
    try:
        serialize = read_tool_output if name == "jd_read" else change_tool_output
        envelope = serialize("anthropic", call_id, result)
        canonical = json.loads(envelope["content"])
        projected, evidence = _project_jd_read_result(
            canonical, dataset_id=dataset_id, document_id=document_id, run_id=run_id,
        )
        content = _json(projected)
        artifact = {
            "format_version": 1, "kind": name, "dataset_id": dataset_id,
            "document_id": document_id, "run_id": run_id,
            "tool_call_id": call_id, "content_digest": _digest(content),
            "canonical_result": canonical,
            "evidence": [entry.__dict__ for entry in evidence],
        }
        return ToolMessage(id=str(uuid4()), name=name, tool_call_id=call_id,
                           content=content, artifact=artifact,
                           status="error" if envelope["is_error"] else "success")
    except Exception:
        raise AiToolError("invalid_tool_result") from None


def _decode_jd_read_message(message: ToolMessage, *, name: str, call_id: str,
                            dataset_id: str | None = None,
                            document_id: str | None = None,
                            run_id: str | None = None) -> tuple[dict, tuple[RuntimeEvidence, ...]]:
    """Validate one model-safe JD read and recover its canonical private result."""
    try:
        artifact = message.artifact
        if (type(message.name) is not str or message.name != name
                or message.tool_call_id != call_id or type(message.content) is not str
                or type(artifact) is not dict or set(artifact) != _JD_READ_ARTIFACT_KEYS
                or artifact["format_version"] != 1 or artifact["kind"] != name
                or artifact["tool_call_id"] != call_id
                or artifact["content_digest"] != _digest(message.content)
                or name not in {"jd_read", "jd_change_read"}):
            raise ValueError("invalid_jd_read_artifact")
        for expected, actual in (
            (dataset_id, artifact["dataset_id"]),
            (document_id, artifact["document_id"]),
            (run_id, artifact["run_id"]),
        ):
            if expected is not None and actual != expected:
                raise ValueError("invalid_jd_read_scope")
        if not all(_identifier(artifact[key]) for key in ("dataset_id", "document_id", "run_id")):
            raise ValueError("invalid_jd_read_scope")

        canonical = artifact["canonical_result"]
        serialize = read_tool_output if name == "jd_read" else change_tool_output
        envelope = serialize("anthropic", call_id, canonical)
        expected_status = "error" if envelope["is_error"] else "success"
        if message.status != expected_status:
            raise ValueError("invalid_jd_read_status")
        canonical = json.loads(envelope["content"])
        projected, evidence = _project_jd_read_result(
            canonical,
            dataset_id=artifact["dataset_id"],
            document_id=artifact["document_id"],
            run_id=artifact["run_id"],
        )
        if (_json(projected) != message.content
                or [entry.__dict__ for entry in evidence] != artifact["evidence"]):
            raise ValueError("invalid_jd_read_projection")
        return canonical, evidence
    except AiToolError:
        raise
    except Exception:
        raise AiToolError("invalid_jd_evidence") from None


def _merge_evidence(target: dict[str, RuntimeEvidence], entries) -> None:
    for entry in entries:
        if entry.evidence_key in target and target[entry.evidence_key] != entry:
            raise AiToolError("invalid_jd_evidence")
        target[entry.evidence_key] = entry


def reproject_active_evidence_catalog(runtime, state=None) -> dict[str, RuntimeEvidence]:
    """Rebuild A's active evidence view from canonical checkpoint owners.

    This is deliberately a projection, not a cache or a new registry.  It is
    called again after request-only compaction and after checkpoint restore so
    the model-facing keys are always derived from the canonical messages,
    private ToolMessage artifacts, Working State, and existing Memory proof.
    A continuation summary is never an input to this projection and therefore
    cannot create a key, read proof, or JD basis.
    """
    from .working_state import working_evidence_catalog
    from .memory_context import layered_read_proof, memory_session

    context = runtime.context
    state = state if state is not None else getattr(runtime, "state", {})
    messages = state.get("messages", ())
    catalog = jd_evidence_catalog(runtime, state)
    source_notice = getattr(context, "source_notice", None)
    raw_source = source_notice(messages) if source_notice is not None else None
    working_state = state.get("interview_working_state")
    if working_state is not None or raw_source is not None:
        working = working_evidence_catalog(
            state=working_state, context=context,
            messages=messages, raw_source_notice=raw_source,
        )
        _merge_evidence(catalog, (RuntimeEvidence(
            value.evidence_key, value.source_reference, value.scope_kind, value.scope_id,
            value.status, value.next_offset,
        ) for value in working.values()))
    # Node-style middleware receives the current state as the hook argument;
    # LangChain's hook Runtime carries context/store but does not expose that
    # state as ``runtime.state``.  Reuse the existing session validator with
    # the same state explicitly, as the model middleware already does.
    session = (memory_session(SimpleNamespace(context=context, state=state,
                                               store=runtime.store))
               if getattr(context, "memory_session", None) is not None else None)
    if session is not None and session.head is not None:
        try:
            if session.artifacts.bundle_base(session.head.memory) is not None:
                proof = layered_read_proof(
                    messages, dataset_id=session.dataset_id, document_id=session.document_id,
                    run_id=session.run_id, revision=session.head.revision,
                    version_id=session.head.memory.version_id,
                )
                for case_id, mapping in proof.case_evidence.items():
                    for key, reference in mapping.items():
                        _merge_evidence(catalog, [RuntimeEvidence(
                            key, reference, "case", case_id,
                            "read_complete" if (case_id, key) in proof.complete_case_evidence else "available",
                            proof.evidence_next_offsets.get(key, 0),
                        )])
        except Exception as error:
            if isinstance(error, AiToolError):
                raise
            raise AiToolError("invalid_jd_evidence") from None
    return catalog


def _resolve_model_evidence(value: object, catalog: dict[str, RuntimeEvidence]) -> object:
    if isinstance(value, list):
        return [_resolve_model_evidence(item, catalog) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key == "basis_refs":
            if not isinstance(item, list) or len(set(item)) != len(item):
                raise AiToolError("invalid_jd_evidence")
            resolved = []
            for evidence_key in item:
                entry = catalog.get(evidence_key)
                if entry is None or entry.status not in {"visible", "read_complete"}:
                    raise AiToolError("source_not_read")
                resolved.append(entry.source_reference)
            result[key] = resolved
        else:
            result[key] = _resolve_model_evidence(item, catalog)
    return result


@dataclass(frozen=True)
class _Prepared:
    name: str
    message_id: str
    call_id: str
    input_digest: str
    error: dict | None = field(default=None, repr=False)
    intent: BoundEdit | None = field(default=None, repr=False)
    binding: dict | None = field(default=None, repr=False)


def _jd_evidence_key(*, dataset_id: str, document_id: str, run_id: str,
                     target_ref: str, related_capability_ref: str | None,
                     source_reference: str) -> str:
    from .memory_context import issue_scoped_evidence_key
    scope_id = f"{target_ref}|{related_capability_ref or ''}"
    return issue_scoped_evidence_key(
        dataset_id=dataset_id, document_id=document_id, run_id=run_id,
        scope_kind="jd_source", scope_id=scope_id,
        source_reference=source_reference,
    )


def _project_jd_read_result(value: dict, *, dataset_id: str, document_id: str,
                            run_id: str) -> tuple[dict, tuple[RuntimeEvidence, ...]]:
    """Hide signed source locators while retaining source order and read state."""
    entries: dict[str, RuntimeEvidence] = {}

    def source_key(item: dict, source_reference: str) -> str:
        target_ref = item.get("target_ref")
        related_capability_ref = item.get("related_capability_ref")
        if (not _identifier(target_ref, 4096)
                or related_capability_ref is not None and not _identifier(related_capability_ref, 4096)
                or not _identifier(source_reference, 4096)):
            raise AiToolError("invalid_jd_evidence")
        key = _jd_evidence_key(
            dataset_id=dataset_id, document_id=document_id, run_id=run_id,
            target_ref=target_ref,
            related_capability_ref=related_capability_ref,
            source_reference=source_reference,
        )
        entry = RuntimeEvidence(key, source_reference, "jd_source",
                                f"{target_ref}|{related_capability_ref or ''}",
                                "available", 0)
        previous = entries.get(key)
        if previous is not None and previous != entry:
            raise AiToolError("invalid_jd_evidence")
        entries[key] = entry
        return key

    def visit(item):
        if isinstance(item, list):
            return [visit(value) for value in item]
        if not isinstance(item, dict):
            return item
        result = {key: visit(value) for key, value in item.items()}
        if item.get("type") == "source" and isinstance(item.get("source_ref"), str):
            source_reference = item["source_ref"]
            result.pop("source_ref", None)
            result["evidence_key"] = source_key(item, source_reference)
            result["read_status"] = "available"
        elif item.get("type") == "source_placement":
            target_ref = item.get("target_ref")
            related_capability_ref = item.get("related_capability_ref")
            if (not _identifier(target_ref, 4096)
                    or related_capability_ref is not None
                    and not _identifier(related_capability_ref, 4096)):
                raise AiToolError("invalid_jd_evidence")
            for old, new in (("previous_source_ref", "previous_evidence_key"),
                             ("next_source_ref", "next_evidence_key")):
                source_reference = item.get(old)
                if source_reference is not None:
                    result.pop(old, None)
                    result[new] = source_key(item, source_reference)
        return result

    return visit(value), tuple(entries.values())


def jd_evidence_catalog(runtime, state=None) -> dict[str, RuntimeEvidence]:
    """Rebuild JD source handles from trusted private read artifacts."""
    try:
        state = state if state is not None else getattr(runtime, "state", {})
        scope = runtime.context
        dataset_id, document_id, run_id = scope.dataset_id, scope.document_id, scope.run_id
        messages = state.get("messages", ())
        starts = [index for index, message in enumerate(messages)
                  if isinstance(message, HumanMessage) and message.id == run_id]
        # Production A runs mark their first HumanMessage with run_id. Keep a
        # narrow compatibility fallback for isolated unit fixtures that do not
        # carry that marker; they have no prior-turn evidence to trust.
        scoped = messages[starts[0]:] if len(starts) == 1 else messages
        catalog: dict[str, RuntimeEvidence] = {}
        calls = {}
        evidence_calls = {}
        for message in scoped:
            if isinstance(message, AIMessage):
                for call in message.tool_calls:
                    if call.get("name") in {"jd_read", "jd_change_read"}:
                        calls[call.get("id")] = call
                    elif call.get("name") == "read_evidence":
                        evidence_calls[call.get("id")] = call
        for message in scoped:
            if (not isinstance(message, ToolMessage) or message.tool_call_id not in calls
                    or message.status != "success"):
                continue
            call = calls[message.tool_call_id]
            _, projected_entries = _decode_jd_read_message(
                message,
                name=call.get("name"),
                call_id=message.tool_call_id,
                dataset_id=dataset_id,
                document_id=document_id,
                run_id=run_id,
            )
            for entry in projected_entries:
                if (not _identifier(entry.evidence_key, 64)
                        or not _identifier(entry.source_reference, 4096)
                        or not _identifier(entry.scope_id, 4096)
                        or entry.scope_kind != "jd_source"
                        or entry.status not in {"available", "read_complete"}
                        or (entry.next_offset is not None
                            and (type(entry.next_offset) is not int or entry.next_offset < 0))):
                    raise AiToolError("invalid_jd_evidence")
                previous = catalog.get(entry.evidence_key)
                if previous is not None:
                    if (previous.source_reference, previous.scope_kind, previous.scope_id) != (
                            entry.source_reference, entry.scope_kind, entry.scope_id):
                        raise AiToolError("invalid_jd_evidence")
                    # Re-reading a JD page must not erase an already completed
                    # evidence read.  JD projections begin at offset zero;
                    # foreground read progress is applied below.
                    if previous.next_offset is None or entry.next_offset is None:
                        entry = RuntimeEvidence(
                            entry.evidence_key, entry.source_reference, entry.scope_kind,
                            entry.scope_id, "read_complete", None,
                        )
                    elif previous.next_offset != 0:
                        entry = previous
                catalog[entry.evidence_key] = entry
        for message in scoped:
            if (not isinstance(message, ToolMessage)
                    or message.tool_call_id not in evidence_calls
                    or message.status != "success"):
                continue
            artifact = message.artifact
            call = evidence_calls[message.tool_call_id]
            # read_evidence is shared by JD, layered Memory and Working State.
            # Their own validators own these known foreign artifacts; an
            # unknown kind still fails closed below.
            if type(artifact) is dict and artifact.get("kind") in {
                    "evidence", "working_evidence"}:
                continue
            if (type(artifact) is not dict or set(artifact) != {
                    "format_version", "kind", "dataset_id", "document_id", "run_id",
                    "scope_kind", "scope_id", "evidence_key", "source_reference",
                    "read_offset", "next_offset", "content_digest"
                } or artifact.get("format_version") != 1
                    or artifact.get("kind") != "jd_evidence"
                    or (artifact.get("dataset_id"), artifact.get("document_id"), artifact.get("run_id"))
                    != (dataset_id, document_id, run_id)
                    or artifact.get("content_digest") != _digest(message.content)):
                raise AiToolError("invalid_jd_evidence")
            key = call.get("args", {}).get("evidence_key")
            entry = catalog.get(key)
            if (entry is None or entry.scope_kind != "jd_source"
                    or artifact.get("scope_kind") != entry.scope_kind
                    or artifact.get("scope_id") != entry.scope_id
                    or artifact.get("evidence_key") != key
                    or artifact.get("source_reference") != entry.source_reference):
                raise AiToolError("invalid_jd_evidence")
            expected_offset = entry.next_offset
            if expected_offset is None:
                expected_offset = 0
            offset = artifact.get("read_offset")
            following = artifact.get("next_offset")
            if (type(offset) is not int or offset != expected_offset
                    or (following is not None
                        and (type(following) is not int or following <= offset))):
                raise AiToolError("invalid_jd_evidence")
            try:
                payload = json.loads(message.content)
            except Exception:
                raise AiToolError("invalid_jd_evidence") from None
            if (type(payload) is not dict or payload.get("evidence_key") != key
                    or payload.get("has_more") is not (following is not None)):
                raise AiToolError("invalid_jd_evidence")
            catalog[key] = RuntimeEvidence(
                entry.evidence_key, entry.source_reference, entry.scope_kind,
                entry.scope_id, "read_complete" if following is None else "available",
                following,
            )
        return catalog
    except AiToolError:
        raise
    except Exception:
        raise AiToolError("invalid_jd_evidence") from None


class AiToolSession:
    """One admitted foreground run's nonpersistent tool material cache."""
    def __init__(self, owner, permit, history, reads, changes, codec: ReferenceCodec, *, source_resolver=None):
        try:
            identity = permit.identity
            if (not _uuid(identity.document_id) or not _uuid(identity.run_id)
                    or not _hex(identity.request_digest) or not isinstance(codec, ReferenceCodec)
                    or not _uuid(codec.dataset_id) or not callable(permit.stop_event.is_set)
                    or not callable(owner.execute_foreground)
                    or any(not callable(port) for port in (history.read_revision, reads.read, changes.read))
                    or source_resolver is not None and not callable(source_resolver)):
                raise ValueError()
        except Exception:
            raise AiToolError("invalid_tool_session") from None
        self.owner, self.permit = owner, permit
        self.history, self.reads, self.changes, self.codec = history, reads, changes, codec
        self.document_id, self.run_id, self.dataset_id = identity.document_id, identity.run_id, codec.dataset_id
        self.source_resolver = source_resolver or _no_sources
        self._calls: dict[str, _Prepared] = {}

    @property
    def scope(self):
        return dict(dataset_id=self.dataset_id, document_id=self.document_id, run_id=self.run_id)

    def _read_base(self, state):
        value = state.get("jd_ai_read")
        if value is None:
            raise ReadError("read_required")
        try:
            if (type(value) is not dict or set(value) != _READ_KEYS
                    or type(value["format_version"]) is not int or value["format_version"] != 1
                    or any(value[key] != expected for key, expected in self.scope.items())
                    or not _uuid(value["revision_id"]) or not _identifier(value["tool_message_id"], 512)
                    or not _identifier(value["tool_call_id"]) or not _hex(value["content_digest"])):
                raise ValueError()
            messages = [message for message in state.get("messages", ())
                        if isinstance(message, ToolMessage) and message.id == value["tool_message_id"]]
            if len(messages) != 1:
                raise ValueError()
            message = messages[0]
            if (message.name != "jd_read" or message.status != "success" or message.tool_call_id != value["tool_call_id"]
                    or type(message.content) is not str or _digest(message.content) != value["content_digest"]):
                raise ValueError()
            artifact = message.artifact
            if (type(artifact) is not dict or artifact.get("format_version") != 1
                    or artifact.get("kind") != "jd_read"
                    or artifact.get("tool_call_id") != value["tool_call_id"]
                    or artifact.get("content_digest") != value["content_digest"]
                    or type(artifact.get("canonical_result")) is not dict):
                raise ValueError()
            # The model sees the evidence-key projection. The writer still
            # validates the private canonical JD read produced by the App.
            page = ReadPage.model_validate(artifact["canonical_result"], strict=True)
            if page.access != "current" or page.view not in {"current", "item", "section"}:
                raise ValueError()
            reference = self.codec.resolve(page.revision_ref, document_id=self.document_id,
                                           roles={"revision"}, purposes={"history"})
            if reference.revision_id != value["revision_id"]:
                raise ValueError()
            return UUID(value["revision_id"])
        except Exception:
            raise ReadError("read_required") from None

    def prepare(self, state, runtime=None):
        message = state["messages"][-1]
        if not isinstance(message, AIMessage) or message.invalid_tool_calls:
            raise AiToolError("invalid_tool_call")
        if not message.tool_calls:
            return None
        if len(message.tool_calls) != 1:
            raise AiToolError("multiple_tool_calls")
        call = message.tool_calls[0]
        name, call_id, digest = _call_identity(call)
        if not _identifier(message.id, 512):
            raise AiToolError("invalid_tool_call")
        bindings = state.get("jd_ai_bindings", [])
        decoded = decode_ai_bindings(bindings, **self.scope)
        for bound in decoded:
            verify_binding_message(bound, state.get("messages", ()))
        existing = next((item for item in decoded if item.tool_call_id == call_id), None)
        cached = self._calls.get(call_id)
        if cached is not None:
            if (cached.name, cached.message_id, cached.input_digest) != (name, message.id, digest):
                raise AiToolError("tool_call_conflict")
            if cached.binding is not None:
                if existing is not None:
                    if existing != decode_ai_binding(cached.binding, **self.scope):
                        raise AiToolError("invalid_ai_binding")
                    return None
                return {"jd_ai_bindings": [*bindings, dict(cached.binding)]}
            return None
        if existing is not None:
            # Recovery observes original identities; it never rebinds from history/source.
            raise AiToolError("binding_cache_unavailable")
        try:
            if name == "jd_read":
                parse_read_arguments(call["args"])
                prepared = _Prepared(name, message.id, call_id, digest)
            elif (name in MEMORY_READ_NAMES or name in WORKING_STATE_TOOL_NAMES
                  or name == REQUEST_TOOL_NAME):
                # Native ToolNode owns these tools' argument validation. They
                # cannot create a JD write binding or operation receipt. The
                # consolidation notification has its own receipt artifact,
                # but no JD operation binding.
                prepared = _Prepared(name, message.id, call_id, digest)
            elif name == "jd_change_read":
                parse_change_arguments(call["args"])
                prepared = _Prepared(name, message.id, call_id, digest)
            else:
                command = model_command(name, call["args"])
                if runtime is not None:
                    command = _resolve_model_evidence(
                        command, reproject_active_evidence_catalog(runtime, state)
                    )
                base = self._read_base(state)
                original = self.history.read_revision(self.document_id, base)
                context = command_context(original.domain, command, self.codec, self.source_resolver, lambda: str(uuid4()))
                intent = bind_edit(uuid4(), "ai", self.run_id, command, context)
                binding = {"format_version": 1, **self.scope, "message_id": message.id, "tool_call_id": call_id,
                    "input_digest": digest, "operation_id": str(intent.operation_id), "base_revision_id": str(base),
                    "origin": "ai", "request_digest": intent.request_digest, "command_kind": name}
                decode_ai_binding(binding, **self.scope)
                prepared = _Prepared(name, message.id, call_id, digest, intent=intent, binding=binding)
        except (ReadError, TransportError, IntentValidationError) as error:
            if isinstance(error, ReadError) and error.code == "source_not_available":
                # A source-store failure is not a model argument error. Stop
                # this run; closure uses saved calls/receipts without replay.
                raise AiToolError("ai_tool_unavailable") from None
            result = read_failure("invalid_input") if name in {"jd_read", "jd_change_read"} else _error_result(error)
            prepared = _Prepared(name, message.id, call_id, digest, error=result)
        except HistoryError as error:
            if error.code not in {"document_missing", "revision_missing"}:
                raise AiToolError("ai_tool_unavailable") from None
            prepared = _Prepared(name, message.id, call_id, digest, error=_error_result(ReadError("target_missing")))
        except AiToolError as error:
            if error.code not in {"source_not_read", "invalid_jd_evidence"}:
                raise
            prepared = _Prepared(name, message.id, call_id, digest, error=_error_result(error))
        except GraphBubbleUp:
            raise
        except Exception:
            raise AiToolError("ai_tool_unavailable") from None
        self._calls[call_id] = prepared
        return {"jd_ai_bindings": [*bindings, dict(prepared.binding)]} if prepared.binding else None

    def prepared(self, call, state):
        name, call_id, digest = _call_identity(call)
        cached = self._calls.get(call_id)
        if cached is None:
            raise AiToolError("unprepared_tool_call")
        message = state.get("messages", ())[-1]
        if (not isinstance(message, AIMessage) or message.id != cached.message_id
                or (cached.name, cached.input_digest) != (name, digest)):
            raise AiToolError("tool_call_conflict")
        return cached

    def execute(self, name, arguments, runtime):
        call = {"name": name, "args": arguments, "id": runtime.tool_call_id}
        prepared = self.prepared(call, runtime.state)
        if prepared.error is not None:
            return _message(name, prepared.call_id, prepared.error)
        if name in {"jd_read", "jd_change_read"}:
            try:
                result = self.reads.read(self.document_id, parse_read_arguments(arguments)) if name == "jd_read" else self.changes.read(
                    self.document_id, parse_change_arguments(arguments))
            except ReadError as error:
                return _message(name, prepared.call_id, read_failure(error.code))
            except GraphBubbleUp:
                raise
            except Exception:
                raise AiToolError("ai_tool_unavailable") from None
            message = _jd_read_message(
                name, prepared.call_id, result, dataset_id=self.dataset_id,
                document_id=self.document_id, run_id=self.run_id,
            )
            if name == "jd_read" and result.get("access") == "current" and result.get("view") in {"current", "item", "section"}:
                ref = self.codec.resolve(result["revision_ref"], document_id=self.document_id,
                                         roles={"revision"}, purposes={"history"})
                binding = {"format_version": 1, **self.scope, "revision_id": ref.revision_id,
                    "tool_message_id": message.id, "tool_call_id": prepared.call_id, "content_digest": _digest(message.content)}
                return Command(update={"messages": [message], "jd_ai_read": binding})
            return message
        intent = prepared.intent
        if not isinstance(intent, BoundEdit) or prepared.binding is None:
            raise AiToolError("invalid_ai_binding")

        def confirm_bound(identity):
            bindings = decode_ai_bindings(runtime.state.get("jd_ai_bindings"), **self.scope)
            matching = [item for item in bindings if item.tool_call_id == prepared.call_id]
            if (identity != intent.identity or len(matching) != 1
                    or matching[0] != decode_ai_binding(prepared.binding, **self.scope)
                    or self._calls.get(prepared.call_id) is not prepared):
                raise AiToolError("invalid_ai_binding")
            verify_binding_message(matching[0], runtime.state.get("messages", ()))

        confirm_bound(intent.identity)
        try:
            handle = self.owner.execute_foreground(self.permit, intent, confirm_bound)
            observed = handle.wait(timeout=None).observation
        except GraphBubbleUp:
            raise
        except Exception:
            raise AiToolPending() from None
        if (not isinstance(observed, WriteObservation) or not observed.confirmed
                or observed.document_id != self.document_id or observed.operation_id != intent.operation_id):
            raise AiToolPending()
        try:
            result = project_observation(observed, self.codec)
            message = _message(name, prepared.call_id, result)
            # A stale or missing target invalidates the exact current-read
            # base.  Force the next model submission through jd_read current;
            # do not let an old binding be reused for another operation.
            if result.get("status") in {"target_missing", "stale_view"}:
                return Command(update={"messages": [message], "jd_ai_read": None})
            return message
        except Exception:
            raise AiToolError("ai_tool_projection_failed") from None


def _call_identity(call):
    try:
        name, call_id, args = call["name"], call["id"], call["args"]
        if name not in {
                *MODELS, "jd_read", "jd_change_read", *MEMORY_READ_NAMES,
                *WORKING_STATE_TOOL_NAMES, REQUEST_TOOL_NAME}:
            raise AiToolError("unknown_tool")
        if not _identifier(call_id) or type(args) is not dict:
            raise ValueError()
        return name, call_id, _digest(_json({"name": name, "args": args}))
    except AiToolError:
        raise
    except Exception:
        raise AiToolError("invalid_tool_call") from None


def _session(runtime, *, check_stop=True):
    try:
        context = runtime.context
        session = context.tool_session
        if (not isinstance(session, AiToolSession)
                or any(getattr(context, key) != expected for key, expected in session.scope.items())
                or get_config().get("configurable", {}).get("thread_id") != session.document_id):
            raise AiToolError("invalid_tool_session")
        if check_stop and session.permit.stop_event.is_set():
            raise AiToolError("ai_run_stopped")
        return session
    except AiToolError:
        raise
    except Exception:
        raise AiToolError("invalid_tool_session") from None


def _message(name, call_id, result):
    try:
        serialize = read_tool_output if name == "jd_read" else change_tool_output if name == "jd_change_read" else tool_output
        envelope = serialize("anthropic", call_id, result)
        return ToolMessage(id=str(uuid4()), name=name, tool_call_id=call_id, content=envelope["content"],
                           status="error" if envelope["is_error"] else "success")
    except Exception:
        raise AiToolError("invalid_tool_result") from None


class AiToolMiddleware(AgentMiddleware):
    state_schema = AiToolState

    def __init__(self, *, inspection_only=False):
        if type(inspection_only) is not bool:
            raise AiToolError("invalid_tool_context")
        self._inspection_only = inspection_only

    @hook_config(can_jump_to=["end"])
    def before_model(self, state, runtime):
        """Do not start another model call after the foreground stop signal."""
        if self._inspection_only:
            return None  # InspectionGuard owns the explicit disabled result.
        session = _session(runtime, check_stop=False)
        if session.permit.stop_event.is_set():
            return {"jump_to": "end"}
        return None

    async def abefore_model(self, state, runtime):
        return self.before_model(state, runtime)

    def after_model(self, state, runtime):
        if self._inspection_only:
            from .inspection_model import InspectionExecutionDisabled
            raise InspectionExecutionDisabled()
        message = state.get("messages", ())[-1]
        if (isinstance(message, AIMessage) and len(message.tool_calls) == 1
                and message.tool_calls[0].get("name") == "repair_memory"):
            # The App always supplies both foreground sessions. Validate the JD
            # owner as well as C before binding the original provider call.
            _session(runtime)
            from .memory_repair_session import repair_session
            return repair_session(runtime).prepare(state, runtime)
        return _session(runtime).prepare(state, runtime)

    async def aafter_model(self, state, runtime):
        import asyncio
        return await asyncio.to_thread(self.after_model, state, runtime)

    def wrap_tool_call(self, request, handler):
        if request.tool_call.get("name") == "repair_memory":
            _session(request.runtime)
            from .memory_repair_session import repair_session
            session = repair_session(request.runtime)
            _, _, outcome, _ = session.prepared(request.state, request.tool_call.get("id"))
            if outcome is not None:
                return session.handoff(request.runtime)
            try:
                return handler(request)
            except (AiToolError, GraphBubbleUp):
                raise
            except Exception:
                raise AiToolError("ai_tool_unavailable") from None
        session = _session(request.runtime)
        prepared = session.prepared(request.tool_call, request.state)
        # Reject original inputs before ToolNode injects runtime or fires tool callbacks.
        if prepared.error is not None:
            return _message(prepared.name, prepared.call_id, prepared.error)
        try:
            return handler(bind_memory_read_request(request))
        except (AiToolError, GraphBubbleUp):
            raise
        except Exception:
            raise AiToolError("ai_tool_unavailable") from None

    async def awrap_tool_call(self, request, handler):
        if request.tool_call.get("name") == "repair_memory":
            _session(request.runtime)
            from .memory_repair_session import repair_session
            session = repair_session(request.runtime)
            _, _, outcome, _ = session.prepared(request.state, request.tool_call.get("id"))
            if outcome is not None:
                return session.handoff(request.runtime)
            try:
                return await handler(request)
            except (AiToolError, GraphBubbleUp):
                raise
            except Exception:
                raise AiToolError("ai_tool_unavailable") from None
        session = _session(request.runtime)
        prepared = session.prepared(request.tool_call, request.state)
        if prepared.error is not None:
            return _message(prepared.name, prepared.call_id, prepared.error)
        try:
            return await handler(bind_memory_read_request(request))
        except (AiToolError, GraphBubbleUp):
            raise
        except Exception:
            raise AiToolError("ai_tool_unavailable") from None


# LangChain names each middleware hook node after the middleware itself. This
# is the node that binds an original repair call. A pinned snapshot listing it
# as next means its writes are not applied there, so recovery reads it together
# with the committed bindings, never as a claim on its own. Recovery matches
# this exact name and keeps its gate when it does not appear.
BINDING_NODE = f"{AiToolMiddleware.__name__}.after_model"


def build_jd_tools() -> list[StructuredTool]:
    """SSOT JSON Schema is presentation; existing strict parsers validate calls."""
    definitions = {**{name: (model, DESCRIPTIONS[name]) for name, model in MODELS.items()},
                   "jd_read": (ReadInput, READ_DESCRIPTION), "jd_change_read": (ChangeReadInput, CHANGE_DESCRIPTION)}
    def make(name, model, description):
        def execute(runtime: ToolRuntime, **arguments):
            return _session(runtime).execute(name, arguments, runtime)
        return StructuredTool(name=name, description=description,
            args_schema=model.model_json_schema(mode="validation"), func=execute,
            handle_validation_error="工具參數不符；本次未進入保存。")
    return [make(name, model, description) for name, (model, description) in definitions.items()]
