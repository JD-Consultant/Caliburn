"""One foreground turn's C bindings, native handoff and result projection.

No separate worker, Saver, message table or Memory copy. The static C child
inherits its parent's Saver. A started repair drains before foreground closure;
requesting cancellation never means that an in-flight publication was undone.
"""
from dataclasses import dataclass, replace
from typing import Any

from caliburn_memory import MemoryVersion, PublishedHead
from caliburn_memory.publication import PublishRequest
from caliburn_memory.patch import PATCH_GUIDANCE
from caliburn_memory.repair import RepairWorkflow, build_repair_graph
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.config import get_config
from langgraph.runtime import Runtime
from langgraph.types import Command

from .memory_context import MemoryReadSession
from .memory_repair_records import (
    REPAIR_NAME, MemoryRepairError, decode_repair_bindings, make_repair_binding,
    make_repair_message, parse_repair_input, validate_repair_message,
    validate_unbound_repair_message, verify_repair_binding_message,
)

_CORRECTABLE = frozenset({"invalid_edit", "stale", "no_memory"})
_HANDOFF_FIELDS = ("messages", "jd_ai_run", "jd_ai_bindings", "jd_ai_read",
    "jd_memory_view", "jd_model_view", "jd_memory_repair_bindings")


@dataclass(frozen=True)
class RepairProgress:
    bindings: tuple
    results: tuple
    failures: int
    outcome: dict | None


def repair_progress(state, *, dataset_id, document_id, run_id):
    """Derive this run's read view/correctable count from its original results.

    Earlier runs' messages remain conversation history, but cannot refresh this
    run's selected reader. This is a projection, not receipt verification.
    """
    bindings = decode_repair_bindings(state.get("jd_memory_repair_bindings", []),
        dataset_id=dataset_id, document_id=document_id, run_id=run_id)
    if len(bindings) > 96:
        raise MemoryRepairError()
    messages = state.get("messages", [])
    results, failures, latest, pending = [], 0, None, False
    for binding in bindings:
        verify_repair_binding_message(binding, messages)
        matches = [m for m in messages if isinstance(m, ToolMessage)
            and m.tool_call_id == binding.tool_call_id]
        if len(matches) > 1 or pending:
            raise MemoryRepairError()
        if not matches:
            pending = True
            continue
        outcome, request = validate_repair_message(matches[0], binding, failures)
        results.append((binding, matches[0], outcome, request))
        if outcome["status"] in _CORRECTABLE:
            failures += 1
        if failures > 2:
            raise MemoryRepairError()
        if "head" in outcome:
            latest = outcome
    return RepairProgress(bindings, tuple(results), failures, latest)


def unbound_repair_results(messages, bindings):
    """Pair saved not-executed results with original calls that never bound.

    A bound correction keeps its own binding/receipt path. This projection only
    recognizes calls the App closed without any operation; such a result never
    refreshes this run's Memory read version and is not a correctable failure.
    """
    bound = {(b.message_id, b.tool_call_id) for b in bindings}
    verified = set()
    for message in messages:
        if not isinstance(message, ToolMessage) or message.name != REPAIR_NAME:
            continue
        origins = [m for m in messages if isinstance(m, AIMessage)
            and any(call["id"] == message.tool_call_id for call in m.tool_calls)]
        if len(origins) != 1:
            raise MemoryRepairError()
        key = (origins[0].id, message.tool_call_id)
        if key in bound:
            continue
        validate_unbound_repair_message(message, origins[0])
        verified.add(key)
    return frozenset(verified)


class MemoryRepairSession:
    """Resources/cached original inputs owned by the existing foreground run."""
    def __init__(self, initial: MemoryReadSession, publication):
        if (not isinstance(initial, MemoryReadSession)
                or publication.document_id != initial.document_id):
            raise MemoryRepairError()
        self.initial = initial
        self.workflow = RepairWorkflow(initial.artifacts, publication, initial.source)
        self.scope = {key: getattr(initial, key) for key in ("dataset_id", "document_id", "run_id")}
        self._prepared: dict[str, tuple] = {}

    def progress(self, state):
        return repair_progress(state, **self.scope)

    def current_read(self, state):
        outcome = self.progress(state).outcome
        if outcome is None:
            return self.initial
        # A successful repair pins this turn to the version that repair
        # actually produced. A later background publication remains current in
        # the database, but is not an implicit refresh of this foreground turn.
        # Accept older saved result envelopes whose observational `head` was
        # later than `applied_head`, while projecting the corrected rule here.
        data = (outcome["applied_head"]
                if outcome["status"] == "applied" else outcome["head"])
        head = PublishedHead(data["revision"], MemoryVersion(**data["memory"]),
            data["processed_source"]) if data else None
        guide = (self.initial.artifacts.guide(head.memory)
                 if outcome["status"] == "applied" and head else outcome["guide"])
        return replace(self.initial, head=head, guide=guide,
            backend=self.initial.artifacts.reader(head.memory if head else None))

    def prepare(self, state, runtime):
        message = state["messages"][-1]
        progress = self.progress(state)
        existing = next((b for b in progress.bindings if b.message_id == message.id), None)
        if existing is not None:
            if self._prepared.get(existing.operation_id) is None:
                raise MemoryRepairError()  # Recovery never rebinds/replays an old call.
            return None
        if len(progress.results) != len(progress.bindings):
            raise MemoryRepairError()
        notice = runtime.context.source_notice(state["messages"])
        current = self.current_read(state)
        binding = make_repair_binding(message, **self.scope,
            base=current.head, source_reference=notice["source_ref"])
        self.initial.source.validate_reference(binding.source_reference)
        outcome, edits = None, None
        try:
            layered = (current.head is not None
                       and current.artifacts.bundle_base(current.head.memory) is not None)
        except Exception:
            raise MemoryRepairError() from None
        if layered:
            outcome = {"status": "unsupported_memory_format",
                "detail": "目前分層 Memory 尚未支援即時修補；本次沒有修改 Memory。",
                "read_paths": []}
        elif progress.failures >= 2:
            outcome = {"status": "repair_limit", "detail": "本輪 Memory 更正已兩次失敗；停止更正，先釐清工作內容。"}
        else:
            try:
                edits = parse_repair_input(message.tool_calls[0]["args"])
            except MemoryRepairError:
                outcome = {"status": "invalid_edit", "detail": "請提供兩個現有 Memory 路徑的1–8筆path/diff；總diff上限12000字。"}
        self._prepared[binding.operation_id] = (binding, edits, outcome, progress.failures)
        return {"jd_memory_repair_bindings": [b.model_dump(mode="json") for b in (*progress.bindings, binding)]}

    def prepared(self, state, call_id=None):
        progress = self.progress(state)
        if not progress.bindings or len(progress.results) != len(progress.bindings) - 1:
            raise MemoryRepairError()
        binding = progress.bindings[-1]
        cached = self._prepared.get(binding.operation_id)
        if (cached is None or cached[0] != binding
                or call_id is not None and binding.tool_call_id != call_id
                or not isinstance(state["messages"][-1], AIMessage)
                or state["messages"][-1].id != binding.message_id):
            raise MemoryRepairError()
        return cached

    def handoff(self, runtime):
        binding, _, outcome, failures = self.prepared(runtime.state, runtime.tool_call_id)
        if outcome is not None:
            return make_repair_message(binding, outcome, failures_before=failures)
        # ToolNode validates the native parent Command. Root checkpoints this
        # exact AI call/binding before starting the static C node.
        return Command(graph=Command.PARENT, goto="memory_repair",
            update={key: runtime.state[key] for key in _HANDOFF_FIELDS if key in runtime.state})


def repair_session(runtime, *, check_stop=True):
    context = runtime.context
    session = getattr(context, "memory_repair_session", None)
    if (not isinstance(session, MemoryRepairSession)
            or any(getattr(context, key, None) != value for key, value in session.scope.items())
            or getattr(context, "memory_session", None) is not session.initial
            or runtime.store is not session.initial.artifacts.store
            or get_config().get("configurable", {}).get("thread_id") != session.initial.document_id
            or check_stop and context.stop_event is not None and context.stop_event.is_set()):
        raise MemoryRepairError()
    return session


def build_repair_node():
    # Capture the compiled graph directly: LangGraph can discover it here.
    # Calling a graph through a ToolNode function hides its saved child state.
    child = build_repair_graph(lambda runtime: repair_session(runtime, check_stop=False).workflow)
    def execute(state, runtime: Runtime):
        session = repair_session(runtime)
        binding, edits, outcome, failures = session.prepared(state)
        if outcome is not None or edits is None:
            raise MemoryRepairError()
        result = child.invoke({"operation_id": binding.operation_id, "base": binding.base,
            "source_reference": binding.source_reference, "edits": edits}, context=runtime.context)
        request = result.get("request")
        if request is not None:
            # The core's native state keeps tuple semantics. Convert that exact
            # saved material to its typed request before the JSON artifact
            # boundary; persisted artifact decoding remains deliberately strict.
            data = dict(request)
            data["memory"] = MemoryVersion(**data["memory"])
            data["repair_sources"] = tuple(data["repair_sources"])
            request = PublishRequest(**data)
        message = make_repair_message(binding, result["outcome"], request,
            failures_before=failures)
        return {"messages": [message]}
    return execute


def build_repair_tool():
    def execute(runtime: ToolRuntime, **arguments):
        return repair_session(runtime).handoff(runtime)
    return StructuredTool(name=REPAIR_NAME,
        description=("只有已取得的員工補充或更正足以修正既有工作理解時，才修補Memory；不必每輪修改。"
            "先read_file讀目前內容，再提供patch；App處理身分、版本與來源。只改兩個現有檔案。"
            "失敗先依結果重讀並重新判斷；retryable=false就停止本輪更正。" + PATCH_GUIDANCE),
        args_schema={"type": "object", "properties": {"edits": {"type": "array", "minItems": 1, "maxItems": 8,
            "items": {"type": "object", "properties": {"path": {"type": "string", "enum": ["/memory/knowledge.md", "/memory/guide.md"]},
                "diff": {"type": "string"}}, "required": ["path", "diff"], "additionalProperties": False}}},
            "required": ["edits"], "additionalProperties": False}, func=execute)
