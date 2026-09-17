"""One foreground turn's C bindings, native handoff and result projection.

No separate worker, Saver, message table or Memory copy. The static C child
inherits its parent's Saver. A started repair drains before foreground closure;
requesting cancellation never means that an in-flight publication was undone.
"""
from dataclasses import asdict, dataclass
from typing import Any

from caliburn_memory import (
    LayeredRepair, LayeredRepairWorkflow, MemoryArtifacts, MemoryVersion, PublishedHead,
)
from caliburn_memory.publication import PublishRequest
from caliburn_memory.repair import RepairWorkflow
from deepagents.middleware.filesystem import FilesystemState
from langchain.tools import ToolRuntime
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.config import get_config
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command

from .memory_context import MemoryReadError, MemoryReadSession, layered_read_proof
from .memory_repair_records import (
    REPAIR_NAME, LayeredRepairInput, MemoryRepairError, decode_repair_bindings,
    make_repair_binding, make_repair_message, parse_layered_repair_input,
    validate_repair_message,
    validate_unbound_repair_message, verify_repair_binding_message,
)
from .memory_sources import MemorySourceReader

_CORRECTABLE = frozenset({"invalid_edit", "stale", "no_memory", "read_required"})
_HANDOFF_FIELDS = ("messages", "jd_ai_run", "jd_ai_bindings", "jd_ai_read",
    "jd_memory_view", "jd_model_view", "jd_memory_repair_bindings")


class _RepairNodeState(FilesystemState):
    """One durable child schema for current layered and historical v1 starts."""

    operation_id: str
    base: dict
    source_reference: str
    repair: dict
    edits: list[dict]
    index: int
    case_stage: dict
    understanding_stage: dict
    material: dict
    version: dict
    request: dict
    outcome: dict | None


def _build_app_repair_graph():
    def execute(name):
        def step(state: _RepairNodeState, runtime: Runtime):
            session = repair_session(runtime, check_stop=False)
            workflow = (session.layered_workflow
                        if state.get("repair") is not None else session.workflow)
            return getattr(workflow, "_" + name)(state)
        return step

    def after_seed(state):
        if state.get("outcome"):
            return END
        if state.get("repair") is not None:
            return "edit" if state["repair"]["understanding_updates"] else "validate"
        return "edit"

    def after_edit(state):
        if state.get("outcome"):
            return END
        values = (state["repair"]["understanding_updates"]
                  if state.get("repair") is not None else state["edits"])
        return "edit" if state["index"] < len(values) else "validate"

    builder = StateGraph(_RepairNodeState)
    for name in ("seed", "edit", "validate", "save", "prepare", "publish"):
        builder.add_node(name, execute(name))
    builder.add_edge(START, "seed")
    builder.add_conditional_edges("seed", after_seed)
    builder.add_conditional_edges("edit", after_edit)
    builder.add_conditional_edges("validate", lambda state: END if state.get("outcome") else "save")
    builder.add_edge("save", "prepare")
    builder.add_edge("prepare", "publish")
    builder.add_edge("publish", END)
    return builder.compile()


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
        # Legacy workflow is retained only to reconcile historical format-1
        # checkpoints. The current tool schema can create layered repairs only.
        self.workflow = RepairWorkflow(initial.artifacts, publication, initial.source)
        layered_source = MemorySourceReader(
            initial.source.service, initial.document_id, window_references=True,
        )
        layered_artifacts = MemoryArtifacts(
            initial.artifacts.store, initial.document_id, source=layered_source,
        )
        self.layered_workflow = LayeredRepairWorkflow(
            layered_artifacts,
            type(publication)(publication.engine, layered_artifacts),
            layered_source,
        )
        self.scope = {key: getattr(initial, key) for key in ("dataset_id", "document_id", "run_id")}
        self._prepared: dict[str, tuple] = {}

    def progress(self, state):
        return repair_progress(state, **self.scope)

    def recovery_workflow(self, binding):
        """Use legacy core only for already-saved format-1 checkpoints."""
        return self.layered_workflow if binding.format_version == 2 else self.workflow

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
        return self.initial.at_head(head)

    def _feedback(self, status, head, detail):
        selected = self.initial.at_head(head)
        return {"status": status, "head": asdict(head) if head else None,
                "guide": selected.guide, "detail": detail}

    def _resolve_layered(self, args, state, current, source_reference):
        """Resolve model evidence keys against exact saved current-version reads."""
        value = parse_layered_repair_input(args)
        proof = layered_read_proof(
            state.get("messages", []), run_id=self.initial.run_id,
            revision=current.head.revision,
            version_id=current.head.memory.version_id,
        )
        case_id = value["case_id"]
        evidence = proof.case_evidence.get(case_id)
        if evidence is None:
            raise MemoryReadError("case_read_required")
        if set(evidence.values()) - proof.complete_sources:
            raise MemoryReadError("case_sources_read_required")
        try:
            manifest = current.artifacts.bundle_manifest(current.head.memory)
        except Exception:
            raise MemoryRepairError() from None
        required = {
            binding.understanding_id
            for binding in manifest.understanding_case_bindings
            if binding.case_id == case_id
        }
        supplied = {
            item["understanding_id"] for item in value["understanding_updates"]
        }
        if supplied != required:
            raise MemoryRepairError("invalid_repair_input")
        if required - proof.understanding_ids:
            raise MemoryReadError("understanding_read_required")
        selected_cases = {
            case_id
            for item in value["understanding_updates"]
            for case_id in item["supporting_case_ids"]
        }
        if selected_cases - set(proof.case_evidence):
            raise MemoryReadError("supporting_case_read_required")
        try:
            removals = [evidence[key] for key in value["remove_evidence_keys"]]
        except KeyError:
            raise MemoryRepairError("invalid_repair_input") from None
        if source_reference in removals:
            raise MemoryRepairError("invalid_repair_input")
        return LayeredRepair(
            case_id=case_id,
            case_diff=value["case_diff"],
            case_route_note=value["case_route_note"],
            remove_source_references=removals,
            understanding_updates=value["understanding_updates"],
        ).model_dump(mode="json")

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
        source_reference = notice["source_ref"]
        self.initial.source.validate_reference(source_reference)
        outcome, repair = None, None
        try:
            layered_head = (current.head is not None
                            and current.artifacts.bundle_base(current.head.memory) is not None)
        except Exception:
            raise MemoryRepairError() from None
        if progress.failures >= 2:
            outcome = {"status": "repair_limit",
                "detail": "本輪 Memory 更正已兩次失敗；停止更正，先釐清工作內容。"}
        else:
            try:
                parse_layered_repair_input(message.tool_calls[0]["args"])
            except MemoryRepairError:
                outcome = {"status": "invalid_edit",
                    "detail": ("請使用既有案例與工作理解ID、Runtime提供的evidence key，"
                               "並依 revise/revalidate 規則提供最小修改。")}
        if not layered_head:
            latest = None
        else:
            latest = self.layered_workflow.publication.current()
        if outcome is not None:
            pass
        elif not layered_head:
            outcome = self._feedback(
                "no_memory", current.head,
                "目前沒有可供正式即時修補的分層 Memory；新內容交由背景整理。",
            )
        elif latest != current.head:
            outcome = self._feedback(
                "stale", latest,
                "Memory 已更新；請依新導覽按需重讀並重新判斷，不要只重送舊修改。",
            )
        else:
            try:
                repair = self._resolve_layered(
                    message.tool_calls[0]["args"], state, current, source_reference,
                )
            except MemoryReadError:
                outcome = {"status": "read_required",
                    "detail": ("修補前必須讀取目前案例、完整相關原話、每個直接受影響的"
                               "工作理解，以及這次要保留的支持案例。")}
            except MemoryRepairError:
                supplied = message.tool_calls[0].get("args", {})
                try:
                    parsed = parse_layered_repair_input(supplied)
                    manifest = current.artifacts.bundle_manifest(current.head.memory)
                    required = {item.understanding_id
                        for item in manifest.understanding_case_bindings
                        if item.case_id == parsed["case_id"]}
                    provided = {item["understanding_id"]
                        for item in parsed["understanding_updates"]}
                except Exception:
                    required, provided = set(), set()
                outcome = ({"status": "scope_too_broad",
                            "detail": ("這次修補沒有完整處理所有直接受影響的目前工作理解；"
                                       "請交由背景整理，不能部分發布。")}
                           if required != provided and (required or provided)
                           else {"status": "invalid_edit",
                                 "detail": ("請使用既有案例與工作理解ID、Runtime提供的evidence key，"
                                            "並依 revise/revalidate 規則提供最小修改。")})
        binding = make_repair_binding(
            message, **self.scope, base=current.head,
            source_reference=source_reference,
            repair=repair, layered=True,
        )
        self._prepared[binding.operation_id] = (binding, repair, outcome, progress.failures)
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
    child = _build_app_repair_graph()
    def execute(state, runtime: Runtime):
        session = repair_session(runtime)
        binding, repair, outcome, failures = session.prepared(state)
        if outcome is not None or repair is None:
            raise MemoryRepairError()
        payload = {"operation_id": binding.operation_id, "base": binding.base,
                   "source_reference": binding.source_reference,
                   "repair" if binding.format_version == 2 else "edits": repair}
        result = child.invoke(payload, context=runtime.context)
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
        description=("只在員工已明確指出既有案例的錯誤、正確內容與適用範圍，且本輪需要立即使用修正版時修補。"
            "先讀目前案例、其完整相關原話、每個直接受影響的工作理解與要保留的支持案例。"
            "只能 revise 一個既有案例，並對每個直接依賴理解做 revise 或 revalidate；"
            "新內容、未解衝突、拆分合併或廣泛分析交背景整理。只使用導覽ID與 Runtime 回傳的 evidence key；"
            "不要提供來源reference、版本、digest、路徑、offset或operation ID。"
            "case_diff與understanding_updates中的diff只填既有正文的V4A差異內容：以@@開始區段，"
            "未變行前加一個空格、刪除行前加-、新增行前加+，並帶足以唯一定位的真實上下文。"
            "不要填完整正文、數字行號、Markdown圍欄、檔案路徑或patch檔頭；不匹配時先重讀再修正。"),
        args_schema=LayeredRepairInput.model_json_schema(mode="validation"), func=execute,
        handle_validation_error="工具參數不符；本次未進入修補。")
