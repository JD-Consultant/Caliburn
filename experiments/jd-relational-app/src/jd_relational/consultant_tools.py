"""Native named tools over existing JD ports; identity binding precedes tool SQL.

The foreground host must invoke with native sync durability. After-model state
contains only recovery identity; commands and read materials stay in this run's
memory. A missing cache never triggers source reads or command reconstruction.
"""

from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Any
from uuid import UUID, uuid4

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
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
from .transport import DESCRIPTIONS, MODELS, TransportError, model_command, tool_output


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
        command = model_command(call["name"], call["args"])
        if (call["id"] != binding.tool_call_id or command["tool"] != binding.command_kind
                or _digest(_json({"name": command["tool"], "args": command["arguments"]})) != binding.input_digest):
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
    if code in {"invalid_ref", "stale_view", "target_missing", "revision_missing", "read_required"}:
        return _unbound("請先用 jd_read current 取得本輪目前稿與可寫引用；本次未進入保存。", "reread_current")
    return _unbound("本次工具參數不符；請依具名工具的欄位與限制修正。")


@dataclass(frozen=True)
class _Prepared:
    name: str
    message_id: str
    call_id: str
    input_digest: str
    error: dict | None = field(default=None, repr=False)
    intent: BoundEdit | None = field(default=None, repr=False)
    binding: dict | None = field(default=None, repr=False)


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
            page = ReadPage.model_validate(json.loads(message.content), strict=True)
            if page.access != "current" or page.view not in {"current", "item", "section"}:
                raise ValueError()
            reference = self.codec.resolve(page.revision_ref, document_id=self.document_id,
                                           roles={"revision"}, purposes={"history"})
            if reference.revision_id != value["revision_id"]:
                raise ValueError()
            return UUID(value["revision_id"])
        except Exception:
            raise ReadError("read_required") from None

    def prepare(self, state):
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
            elif name in MEMORY_READ_NAMES:
                # Native ToolNode owns these tools' argument validation. They
                # cannot create a JD write binding or operation receipt.
                prepared = _Prepared(name, message.id, call_id, digest)
            elif name == "jd_change_read":
                parse_change_arguments(call["args"])
                prepared = _Prepared(name, message.id, call_id, digest)
            else:
                command = model_command(name, call["args"])
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
            message = _message(name, prepared.call_id, result)
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
        if name not in {*MODELS, "jd_read", "jd_change_read", *MEMORY_READ_NAMES}:
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
        return _session(runtime).prepare(state)

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
