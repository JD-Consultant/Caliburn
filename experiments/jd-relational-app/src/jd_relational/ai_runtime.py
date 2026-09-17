"""Owned local AI turns over native Agent/Saver and the shared JD writer.

No HTTP server, provider configuration, Memory substitute or automatic model
replay is created here. Foreground ownership is the same per-document owner used
by manual edits. Native run/SQL Futures must finish before recovery can publish
a terminal root. Only actual durable tool receipts become recovered results.
"""

from dataclasses import dataclass, field
from copy import deepcopy
import json
from threading import Event, Lock
from uuid import UUID, uuid4

from caliburn_memory.requests import REQUEST_KIND, REQUEST_TOOL_NAME
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.graph import START
from langgraph.types import StateSnapshot
from langsmith import tracing_context

from .ai_checkpoints import AiCheckpointError, AiRunCheckpoints, new_run_record
from .ai_history import AiRunHistory
from .change_reads import ChangeReadService
from .consultant_context import ConsultantContext, checked_model_view
from .consultant_tools import (
    BINDING_NODE, AiToolSession, decode_ai_bindings, verify_binding_message,
)
from .conversation_sources import ConversationSourceService
from .memory_context import MEMORY_READ_NAMES, MemoryReadSession
from .memory_repair_session import MemoryRepairSession
from .manual_runtime import ForegroundIdentity, ManualRuntime, RuntimeFailure
from .notice_history import NoticeHistoryReader
from .observation_projection import project_observation
from .read_transport import read_failure
from .reads import ReadService, read_json
from .references import ReferenceCodec
from .result_transport import validate_result
from .runtime_checkpoints import DocumentCheckpoints
from .storage.history import HistoryReader, HistoryError
from .storage.receipts import WriteObservation


class AiRuntimeError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class _StopOnToken(BaseCallbackHandler):
    """A cooperative stop; a blocked socket still needs its configured timeout."""
    raise_error = True

    def __init__(self, stop_event, tool_started=None):
        self.stop_event = stop_event
        self.tool_started = tool_started

    def on_tool_start(self, serialized, input_str, **kwargs):
        if self.tool_started is not None:
            self.tool_started.set()

    def on_llm_new_token(self, token, **kwargs):
        if self.stop_event.is_set():
            raise AiRuntimeError("run_cancelled")


@dataclass(frozen=True)
class AiRunResult:
    document_id: str
    run_id: str
    status: str
    input_saved: bool
    response_message_id: str | None


@dataclass(frozen=True)
class AiRunSnapshot:
    """Read-only facts for one original run, not another durable run record."""
    document_id: str
    run_id: str
    run_status: str
    input_state: str
    response_message_id: str | None
    stop_requested: bool | None
    effects_settled: bool
    receipts: tuple[WriteObservation, ...]


@dataclass
class _Attempt:
    record: object
    human: HumanMessage
    invoked: bool = False
    before_config: dict | None = None
    before_state: object | None = field(default=None, repr=False)
    tool_started: Event = field(default_factory=Event, repr=False)
    handle: object | None = None
    result: AiRunResult | None = None
    settling: Lock = field(default_factory=Lock)
    settled: Event = field(default_factory=Event)
    closure_error: str | None = None
    previous_host: bool = False


class AiRunHandle:
    def __init__(self, service, attempt):
        self._service, self._attempt = service, attempt

    def request_stop(self):
        if self._attempt.handle is not None:
            self._attempt.handle.request_stop()

    def wait(self, timeout=None):
        if self._attempt.result is not None:
            return self._attempt.result
        if not self._attempt.settled.wait(timeout):
            raise TimeoutError("run_closure_pending")
        if self._attempt.closure_error is not None:
            raise AiRuntimeError(self._attempt.closure_error)
        return self._attempt.result

    def recover(self):
        """Explicit receipt/closure reconciliation; never reruns the model or edit."""
        if self._attempt.result is not None:
            return self._attempt.result
        if not self._attempt.settled.is_set() or not self._attempt.settling.acquire(blocking=False):
            raise AiRuntimeError("run_recovery_pending")
        try:
            if self._attempt.result is None:
                self._attempt.result = self._service._settle(self._attempt)
                self._attempt.closure_error = None
            return self._attempt.result
        finally:
            self._attempt.settling.release()


def _pending_calls(messages):
    """Inspect native call/result order, without reconstructing or executing tools."""
    pending = {}
    for message in messages:
        if isinstance(message, AIMessage):
            if pending:
                raise AiRuntimeError("invalid_saved_conversation")
            for call in message.tool_calls:
                key = (message.id, call["id"])
                if key in pending:
                    raise AiRuntimeError("invalid_saved_conversation")
                pending[key] = call
        elif isinstance(message, ToolMessage):
            matches = [key for key in pending if key[1] == message.tool_call_id]
            if len(matches) != 1:
                raise AiRuntimeError("invalid_saved_conversation")
            key = matches[0]
            if message.name is not None and message.name != pending[key]["name"]:
                raise AiRuntimeError("invalid_saved_conversation")
            del pending[key]
        elif isinstance(message, HumanMessage) and pending:
            raise AiRuntimeError("invalid_saved_conversation")
    return pending


def _request_not_executed():
    """A consolidation notification that never ran, reported in its own terms.

    It borrows neither a JD operation result nor a publication receipt: no
    effect was attempted on either, so reporting one would state a false fact
    about a different subject. Nothing asked for scheduling, so nothing may be
    admitted for it either.
    """
    return {"error": "memory_consolidation_not_requested", "next_action": "stop"}


def _not_executed():
    return validate_result({"status": "invalid_input", "effect": "unchanged",
        "receipt_durability": "unconfirmed", "operation_ref": None,
        "result_revision_ref": None, "change_ref": None,
        "error": {"code": "invalid_input", "message": "這次工具尚未執行；回合已停止。", "related_refs": []},
        "next_action": "stop"})


def _run_messages(messages, run_id):
    """Slice exactly this run's own saved turn out of the shared conversation."""
    positions = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage) and m.id == run_id]
    if len(positions) != 1 or any(isinstance(m, HumanMessage) for m in messages[positions[0] + 1:]):
        raise AiRuntimeError("invalid_saved_conversation")
    return messages[positions[0] + 1:]


def _verify_saved_results(messages, bindings, receipts, codec, *, run_id=None,
                          verified_repair_calls=frozenset()):
    """A stored tool success is evidence only when its original SQL receipt agrees."""
    if run_id is not None:
        messages = _run_messages(messages, run_id)
    by_call = {(b.message_id, b.tool_call_id): b for b in bindings}
    active = {}
    for message in messages:
        if isinstance(message, AIMessage):
            active = {call["id"]: (call["name"], by_call.get((message.id, call["id"])), message.id)
                      for call in message.tool_calls}
        elif isinstance(message, ToolMessage):
            call = active.get(message.tool_call_id)
            if call is None:
                raise AiRuntimeError("invalid_saved_tool_result")
            name, binding, message_id = call
            if binding is None:
                if name == "repair_memory":
                    if (message_id, message.tool_call_id) not in verified_repair_calls:
                        raise AiRuntimeError("invalid_saved_tool_result")
                    continue
                if name == REQUEST_TOOL_NAME:
                    # This tool's own artifact is its whole receipt: there is no
                    # operation or publication behind it to agree with, and a
                    # success claim without that artifact is not evidence of one.
                    if message.name != name:
                        raise AiRuntimeError("invalid_saved_tool_result")
                    if message.status == "success":
                        if message.artifact != {"kind": REQUEST_KIND}:
                            raise AiRuntimeError("invalid_saved_tool_result")
                        continue
                    try:
                        stopped = json.loads(message.content) == _request_not_executed()
                    except Exception:
                        stopped = False
                    if not stopped:
                        raise AiRuntimeError("invalid_saved_tool_result")
                    continue
                # Read tools never bind writes. An unbound mutation is legal
                # only as a validated pre-execution error, never a saved write.
                if name not in {"jd_read", "jd_change_read", *MEMORY_READ_NAMES}:
                    try:
                        value = validate_result(json.loads(message.content))
                        if (message.status != "error" or message.name != name
                                or value["operation_ref"] is not None or value["effect"] != "unchanged"
                                or value["receipt_durability"] != "unconfirmed" or value["error"] is None):
                            raise ValueError()
                    except Exception:
                        raise AiRuntimeError("invalid_saved_tool_result") from None
                continue
            expected = project_observation(receipts[binding.identity.operation_id], codec)
            expected_status = "success" if expected["status"] in {"committed", "no_change"} else "error"
            try:
                if (type(message.content) is not str or json.loads(message.content) != expected
                        or message.status != expected_status or message.name != binding.command_kind):
                    raise ValueError()
            except Exception:
                raise AiRuntimeError("invalid_saved_tool_result") from None


class AiRuntime:
    def __init__(self, owner: ManualRuntime, codec: ReferenceCodec, *, source_resolver=None,
                 conversation_sources: ConversationSourceService | None = None,
                 memory_engine=None, background=None, background_availability=None,
                 execution_enabled: bool = True):
        if (not isinstance(owner, ManualRuntime) or not isinstance(owner.checkpoints, DocumentCheckpoints)
                or not isinstance(codec, ReferenceCodec)
                or source_resolver is not None and not callable(source_resolver)
                or conversation_sources is not None and (
                    not isinstance(conversation_sources, ConversationSourceService)
                    or conversation_sources.dataset_id != codec.dataset_id
                    or source_resolver is not None)
                or background is not None and not callable(background)
                or background_availability is not None and not callable(background_availability)
                or type(execution_enabled) is not bool):
            raise AiRuntimeError("invalid_ai_runtime")
        self.owner, self.codec = owner, codec
        self.graph = owner.checkpoints.graph
        self.checkpoints = AiRunCheckpoints(self.graph)
        self.run_history = AiRunHistory(self.checkpoints)
        self.history = HistoryReader(owner.storage.engine)
        self.notices = NoticeHistoryReader(owner.storage.engine)
        self.reads = ReadService(owner.storage, self.history, codec)
        self.changes = ChangeReadService(self.history, codec)
        self.conversation_sources = conversation_sources
        self._background = background
        self._background_availability = background_availability
        self.source_resolver = conversation_sources.resolve if conversation_sources is not None else source_resolver
        self.execution_enabled = execution_enabled
        if memory_engine is not None:
            from sqlalchemy.engine import Engine
            from langgraph.store.base import BaseStore
            if (not isinstance(memory_engine, Engine) or conversation_sources is None
                    or not isinstance(self.graph.store, BaseStore)):
                raise AiRuntimeError("invalid_ai_runtime")
        self.memory_engine = memory_engine
        self._registry = Lock()  # Only handles, never graph/DB I/O.
        self._latest = {}
        self._starts = {}
        owner.claim_foreground_coordinator(startup_recover=self._recover_previous)

    def _repair_material(self, observed, *, messages=None):
        """Reopen the immutable turn-start view and project saved C results."""
        from hashlib import sha256
        from caliburn_memory import MemoryArtifacts, MemoryVersion, PublishedHead, PublicationStore
        from .memory_context import checked_memory_view
        from .memory_repair_records import decode_repair_bindings
        from .memory_sources import MemorySourceReader

        record = observed.record
        bindings = decode_repair_bindings(observed.repair_bindings,
            dataset_id=record.dataset_id, document_id=record.document_id, run_id=record.run_id)
        if not bindings:
            return None, bindings, None
        if self.memory_engine is None or self.conversation_sources is None or self.graph.store is None:
            raise ValueError()
        view = checked_memory_view(observed.memory_view, dataset_id=record.dataset_id,
            document_id=record.document_id, run_id=record.run_id)
        first = bindings[0].base
        if view is None or (view["revision"] == 0) != (first is None):
            raise ValueError()
        source = MemorySourceReader(self.conversation_sources, record.document_id)
        artifacts = MemoryArtifacts(self.graph.store, record.document_id, source=source)
        if first is None:
            head, guide = None, ""
        else:
            head = PublishedHead(first["revision"], MemoryVersion(**first["memory"]),
                first["processed_source"])
            if (view["revision"] != head.revision or view["version_id"] != head.memory.version_id):
                raise ValueError()
            guide = artifacts.read_text("/memory/guide.md", head.memory)
        if sha256(guide.encode("utf-8")).hexdigest() != view["guide_digest"]:
            raise ValueError()
        initial = MemoryReadSession(record.dataset_id, record.document_id, record.run_id,
            artifacts, source, head, guide, artifacts.reader(head.memory if head else None))
        session = MemoryRepairSession(initial, PublicationStore(self.memory_engine, artifacts))
        progress = session.progress({"messages": observed.messages if messages is None else messages,
            "jd_memory_repair_bindings": observed.repair_bindings})
        return session, bindings, progress

    def _repair_evidence(self, observed, *, messages=None):
        """Validate saved C calls and their separate publication receipts.

        JD receipts stay owned by `_binding_receipts`. A repair ToolMessage is
        accepted only after its original binding/result and publication receipt
        agree; a later background head may legitimately differ from the saved
        tool feedback.
        """
        try:
            from .memory_repair_session import unbound_repair_results
            session, bindings, progress = self._repair_material(observed, messages=messages)
            saved = observed.messages if messages is None else messages
            # A call closed without any binding carries no operation, so it has
            # no receipt to agree with; its own original call is the only proof.
            # Earlier runs keep their own bindings, so scope this to this turn.
            verified = set(unbound_repair_results(
                _run_messages(saved, observed.record.run_id), bindings))
            if session is None:
                return frozenset(verified)
            for binding, _, outcome, request in progress.results:
                receipt = session.workflow.publication.receipt(binding.operation_id)
                if outcome["status"] == "applied":
                    confirmed = session.workflow.reconcile(request)
                    if (receipt is None or confirmed.get("applied_head") != outcome.get("applied_head")
                            or confirmed.get("source_reference") != binding.source_reference):
                        raise ValueError()
                elif receipt is not None:
                    raise ValueError()
                verified.add((binding.message_id, binding.tool_call_id))
            return frozenset(verified)
        except AiRuntimeError:
            raise
        except Exception:
            raise AiRuntimeError("run_recovery_required") from None

    def _close_unbound_repair(self, observed, messages, key, call, bindings, progress):
        """Close an original call that never reached a binding at all.

        The evidence is committed state, not an unapplied write: this run's
        saved bindings hold nothing for this call, and the root's pending task
        is still the consultant subgraph at its binding node. The tool node
        therefore never returned `Command.PARENT`, so the fixed C node never
        ran and no operation, base, source or request exists to record. Any
        other stopped position keeps the foreground gate.
        """
        from .memory_repair_records import make_unbound_repair_message
        if (observed.consultant_next != [BINDING_NODE] or observed.repair_checkpoint is not None
                or (progress is not None and len(progress.results) != len(bindings))
                or (progress is None and bindings)):
            raise AiRuntimeError("run_recovery_required")
        origins = [m for m in messages if isinstance(m, AIMessage) and m.id == key[0]]
        if len(origins) != 1 or call.get("id") != key[1]:
            raise ValueError()
        return make_unbound_repair_message(origins[0], key[1]).model_copy(update={"id": str(uuid4())})

    def _verify_repair_start(self, checkpoint, binding, call):
        """Match the fixed child's own saved START input to this original call."""
        from .memory_repair_records import parse_repair_input
        payload = checkpoint.get("input")
        if (type(payload) is not dict
                or set(payload) != {"operation_id", "base", "source_reference", "edits"}
                or payload["operation_id"] != binding.operation_id
                or payload["base"] != binding.base
                or payload["source_reference"] != binding.source_reference
                or payload["edits"] != parse_repair_input(call.get("args"))):
            raise AiRuntimeError("run_recovery_required")

    def _recover_pending_repair(self, observed, messages, pending):
        """Close one stopped C call from native request/receipt evidence only."""
        from .memory_repair_records import (
            NOT_EXECUTED_DETAIL, REPAIR_NAME, decode_repair_request, make_repair_message,
        )
        try:
            repair_calls = [(key, call) for key, call in pending.items()
                if call.get("name") == REPAIR_NAME]
            if not repair_calls:
                return None
            if len(repair_calls) != 1:
                raise ValueError()
            session, bindings, progress = self._repair_material(observed, messages=messages)
            key, call = repair_calls[0]
            if key not in {(b.message_id, b.tool_call_id) for b in bindings}:
                return self._close_unbound_repair(observed, messages, key, call, bindings, progress)
            # A bound call came from a single-call response, so nothing else of
            # that response can still be open beside it.
            if (session is None or progress is None or not bindings or len(pending) != 1
                    or len(progress.results) != len(bindings) - 1):
                raise ValueError()
            binding = bindings[-1]
            if (key != (binding.message_id, binding.tool_call_id)
                    or call.get("id") != binding.tool_call_id):
                raise ValueError()
            checkpoint = observed.repair_checkpoint
            request, outcome = None, None
            if checkpoint is not None:
                values = checkpoint.get("values")
                if type(values) is not dict:
                    raise ValueError()
                if values.get("request") is not None:
                    request = decode_repair_request(values["request"], binding)
                if values.get("outcome") is not None:
                    outcome = values["outcome"]
            receipt = session.workflow.publication.receipt(binding.operation_id)
            if receipt is not None:
                if request is None:
                    raise ValueError()
                outcome = session.workflow.reconcile(request)
            elif request is not None and outcome is None:
                # The saved publish request may have reached COMMIT even when a
                # current receipt read cannot prove it. Keep the foreground gate.
                raise AiRuntimeError("run_recovery_required")
            elif outcome is None:
                # The stopped native graph can prove publication was not
                # reached only before the saved `publish` boundary. Earlier
                # source/Store work may have run, so do not call this whole
                # tool "not executed". A missing/corrupt later boundary stays
                # unknown and keeps the foreground gate.
                next_step = None if checkpoint is None else checkpoint.get("next")
                if next_step == [START]:
                    # The fixed child holds only its own START channel, so no
                    # node has written state: not executed, not merely unpublished.
                    self._verify_repair_start(checkpoint, binding, call)
                    outcome = {"status": "not_executed", "detail": NOT_EXECUTED_DETAIL}
                elif checkpoint is None:
                    # Without a fixed child checkpoint the position must come
                    # from the root. `consultant_next` is set only while the
                    # root's single pending task is the consultant subgraph, so
                    # its presence — not which step it names — proves the root
                    # never committed the fixed repair step and C never ran.
                    # Any other shape leaves the position unknown: a missing
                    # child checkpoint plus a missing receipt is an absence of
                    # evidence, not evidence.
                    if observed.consultant_next is None:
                        raise AiRuntimeError("run_recovery_required")
                    outcome = {"status": "not_executed", "detail": NOT_EXECUTED_DETAIL}
                elif (type(next_step) is not list or len(next_step) != 1
                        or next_step[0] not in {"seed", "edit", "validate", "save", "prepare"}):
                    raise AiRuntimeError("run_recovery_required")
                else:
                    outcome = {"status": "not_published",
                        "detail": "Memory 更正未完成，沒有發布新版本；請在下一輪重新讀取後再判斷。"}
            elif type(outcome) is not dict or outcome.get("status") == "applied":
                # A publication and its receipt share one transaction, so a
                # saved applied outcome without a receipt is not self-evidence.
                raise AiRuntimeError("run_recovery_required")
            return make_repair_message(binding, outcome, request,
                failures_before=progress.failures).model_copy(update={"id": str(uuid4())})
        except AiRuntimeError:
            raise
        except Exception:
            raise AiRuntimeError("run_recovery_required") from None

    def _wake_background(self, document_id: str) -> None:
        """Tell the background this document is worth looking at again.

        Waking decides nothing: what may run is read from durable admission,
        Saver and publication state by whoever was wired in here. A failure to
        even consider background work is that side's own problem -- it must not
        change what the employee's turn did, nor stop a host from starting --
        and the next wake reconsiders from the same durable state.
        """
        if self._background is None:
            return
        try:
            self._background(document_id)
        except Exception:
            pass

    def _recover_previous(self, document_id: str, timeout: float) -> int:
        """Recover only foreground state while the host is still starting."""
        return self._recover_previous_run(document_id, timeout)

    def _recover_previous_run(self, document_id: str, timeout: float) -> int:
        """Inspect original native state within the host's complete startup scan.

        No model/tool is resumed. A foreign handle is adopted only through the
        owner's real prior-host capability; absence of a local Future is never
        substituted for that proof. Terminal turns remain read-only.
        """
        try:
            observed = self.checkpoints.discover(document_id, self.codec.dataset_id)
            with self._registry:
                cached = self._latest.get(document_id)
            if observed is None:
                if cached is not None:
                    raise AiRuntimeError("run_recovery_required")
                return 0
            record = observed.record
            if cached is not None:
                attempt = cached._attempt
                if (not attempt.previous_host or attempt.record.run_id != record.run_id
                        or attempt.record.request_digest != record.request_digest):
                    raise AiRuntimeError("run_recovery_required")
                if attempt.result is not None:
                    return 0
            elif record.status != "running":
                # Already-closed output must still agree with the original
                # tool calls and durable SQL results. Never repair a terminal
                # record by guessing, replaying, or silently relabelling it.
                bindings, receipts, missing = self._binding_receipts(observed, include_active=False)
                if not observed.closed or missing or _pending_calls(observed.messages):
                    raise AiRuntimeError("run_recovery_required")
                repairs = self._repair_evidence(observed)
                _verify_saved_results(observed.messages, bindings, receipts, self.codec,
                    run_id=record.run_id, verified_repair_calls=repairs)
                return 0
            else:
                identity = ForegroundIdentity(document_id, record.run_id, record.request_digest)
                def confirm_original(actual):
                    if (actual != identity or self.checkpoints.discover(document_id,
                            self.codec.dataset_id) != observed):
                        raise AiRuntimeError("run_recovery_required")
                handle = self.owner.adopt_previous_foreground(identity, confirm_original)
                human = next(m for m in observed.messages
                    if isinstance(m, HumanMessage) and m.id == record.run_id)
                attempt = _Attempt(record, human, handle=handle, previous_host=True)
                with self._registry:
                    self._latest[document_id] = AiRunHandle(self, attempt)
            if not attempt.settling.acquire(blocking=False):
                raise AiRuntimeError("run_recovery_pending")
            try:
                attempt.result = self._settle(attempt, timeout=timeout)
                attempt.closure_error = None
            except Exception:
                attempt.closure_error = "run_recovery_required"
                raise
            finally:
                attempt.settled.set()
                attempt.settling.release()
            return 1
        except AiRuntimeError:
            raise
        except Exception:
            raise AiRuntimeError("run_recovery_required") from None

    def start(self, document_id: str, run_id: str, text: str, *, expected_revision_id: UUID) -> AiRunHandle:
        if not isinstance(expected_revision_id, UUID):
            raise AiRuntimeError("invalid_input")
        record, human = new_run_record(self.codec.dataset_id, document_id, run_id, text,
                                      start_revision_id=str(expected_revision_id))
        with self._registry:
            start_lock = self._starts.setdefault(document_id, Lock())
        # Serialize handle publication only for this document. The owner remains
        # the shared admission authority; another document can proceed freely.
        with start_lock:
            try:
                return self._start(record, human)
            except (AiRuntimeError, RuntimeFailure):
                raise
            except Exception:
                raise AiRuntimeError("checkpoint_unavailable") from None

    def _start(self, record, human):
        document_id, run_id = record.document_id, record.run_id
        identity = ForegroundIdentity(document_id, run_id, record.request_digest)
        def inspect_original():
            original = self._lookup(document_id, run_id)
            if original is None:
                if not self.execution_enabled:
                    raise AiRuntimeError("execution_disabled")
                return None
            prior = original._attempt.record
            # A legacy request has no confirmed start revision. Read it through
            # lookup, never infer a base and pretend it passed the new contract.
            if prior.format_version != record.format_version:
                raise AiRuntimeError("original_run_lookup_required")
            if prior.request_digest != record.request_digest:
                raise AiRuntimeError("operation_conflict")
            return original
        attempt = _Attempt(record, human)
        admission = self.owner.admit_foreground(identity, lambda permit: self._run(attempt, permit),
            expected_revision=UUID(record.start_revision_id), lookup_original=inspect_original)
        if admission.original is not None:
            return admission.original
        attempt.handle = admission.handle
        result = AiRunHandle(self, attempt)
        with self._registry:
            existing = self._latest.get(document_id)
            if existing is not None and existing._attempt.handle is attempt.handle:
                return existing
            self._latest[document_id] = result
        attempt.handle.add_done_callback(lambda _: self._finish_automatically(attempt))
        return result

    def lookup(self, document_id: str, run_id: str) -> AiRunHandle | None:
        """Inspect the original request; no model invocation or implicit repair."""
        try:
            if type(run_id) is not str or str(UUID(run_id)) != run_id:
                raise ValueError()
        except (TypeError, ValueError):
            raise AiRuntimeError("invalid_input") from None
        try:
            return self.owner.inspect_document(document_id, lambda: self._lookup(document_id, run_id))
        except (AiRuntimeError, RuntimeFailure, AiCheckpointError):
            raise
        except Exception:
            raise AiRuntimeError("checkpoint_unavailable") from None

    def _lookup(self, document_id, run_id):
        # The owner tracks these reads or holds new-admission reservation.
        with self._registry:
            cached = self._latest.get(document_id)
        if cached is not None and cached._attempt.record.run_id == run_id:
            return cached
        original = self.run_history.find(document_id, run_id, self.codec.dataset_id)
        if original is None:
            return None
        if original.record.status == "running":
            raise AiRuntimeError("run_recovery_required")
        bindings, receipts, missing = self._binding_receipts(original, include_active=False)
        if not original.closed or missing or _pending_calls(original.messages):
            raise AiRuntimeError("run_recovery_required")
        repairs = self._repair_evidence(original)
        _verify_saved_results(original.messages, bindings, receipts, self.codec,
            run_id=run_id, verified_repair_calls=repairs)
        human = next(m for m in original.messages if isinstance(m, HumanMessage) and m.id == run_id)
        return AiRunHandle(self, _Attempt(original.record, human, result=self._result(original)))

    def inspect_run(self, document_id: str, run_id: str) -> AiRunSnapshot:
        """Pin native input first, then inspect original SQL effects without repair.

        An active run may advance during reads. Only its terminal native record
        plus actual local closure and the complete SQL set establish settled.
        The HTTP service separately observes the current document write gate.
        """
        try:
            if type(run_id) is not str or str(UUID(run_id)) != run_id:
                raise ValueError()
        except (TypeError, ValueError):
            raise AiRuntimeError("invalid_input") from None
        try:
            return self.owner.inspect_document(document_id, lambda: self._inspect_run(document_id, run_id))
        except (AiRuntimeError, RuntimeFailure, AiCheckpointError):
            raise
        except HistoryError as error:
            raise AiRuntimeError("document_missing" if error.code == "document_missing"
                                 else "checkpoint_unavailable") from None
        except Exception:
            raise AiRuntimeError("checkpoint_unavailable") from None

    def request_stop(self, document_id: str, run_id: str) -> None:
        """Stop only the specified local attempt; an old terminal run is a no-op."""
        handle = self.lookup(document_id, run_id)
        if handle is not None:
            handle.request_stop()

    def recover_run(self, document_id: str, run_id: str) -> None:
        """Explicit original closure only; never resume the model or rebuild edits."""
        handle = self.lookup(document_id, run_id)
        if handle is not None:
            try:
                handle.wait(0)
            except TimeoutError:
                return  # Actual work/automatic closure still owns the attempt.
            except AiRuntimeError:
                pass  # Only an already-failed closure can be explicitly retried.
            self.owner.inspect_document(document_id, handle.recover)

    def _inspect_run(self, document_id, run_id):
        with self._registry:
            cached = self._latest.get(document_id)
        attempt = cached._attempt if cached is not None and cached._attempt.record.run_id == run_id else None
        observed = self.run_history.find(document_id, run_id, self.codec.dataset_id)
        # This one read transaction includes every durable operation of this run.
        saved = self.history.read_run_operations(document_id, run_id)
        local_result = attempt.result if attempt is not None else None
        if observed is None:
            if saved:
                raise AiRuntimeError("run_recovery_required")
            if local_result is not None:
                if local_result.input_saved or local_result.status != "failed":
                    raise AiRuntimeError("run_recovery_required")
                return AiRunSnapshot(document_id, run_id, "failed", "not_saved", None, None, True, ())
            if attempt is None:
                return AiRunSnapshot(document_id, run_id, "not_found", "unconfirmed", None, None, False, ())
            status, stopped = self._active_status(attempt)
            return AiRunSnapshot(document_id, run_id, status, "unconfirmed", None, stopped, False, ())
        if attempt is not None and observed.record.request_digest != attempt.record.request_digest:
            raise AiRuntimeError("operation_conflict")
        bindings = decode_ai_bindings(observed.bindings, dataset_id=self.codec.dataset_id,
            document_id=document_id, run_id=run_id)
        if len(bindings) > 96:
            raise AiRuntimeError("run_recovery_required")
        by_id = {row.operation_id: row for row in saved}
        if len(by_id) != len(saved):
            raise AiRuntimeError("run_recovery_required")
        receipts = {}
        for binding in bindings:
            verify_binding_message(binding, observed.messages)
            identity = binding.identity
            row = by_id.get(identity.operation_id)
            if row is not None and (row.document_id != document_id or row.origin != "ai"
                    or row.ai_run_id != run_id or row.request_digest != identity.request_digest
                    or row.base_revision_id != identity.base_revision_id
                    or row.body.command_kind != identity.command_kind):
                raise AiRuntimeError("invalid_saved_tool_result")
            receipts[identity.operation_id] = WriteObservation(document_id, identity.operation_id,
                row, "unknown" if row is None else None)
        terminal = observed.record.status != "running"
        if terminal:
            if (not observed.closed or _pending_calls(observed.messages)
                    or set(by_id) != set(receipts) or any(not r.confirmed for r in receipts.values())):
                raise AiRuntimeError("run_recovery_required")
            repairs = self._repair_evidence(observed)
            _verify_saved_results(observed.messages, bindings, receipts, self.codec,
                run_id=run_id, verified_repair_calls=repairs)
        response = self._public_response(observed)
        if terminal and (attempt is None or local_result is not None):
            if local_result is not None and (not local_result.input_saved or local_result.status != observed.record.status):
                raise AiRuntimeError("run_recovery_required")
            return AiRunSnapshot(document_id, run_id, observed.record.status, "saved", response,
                                 None, True, tuple(receipts.values()))
        status, stopped = self._active_status(attempt)
        return AiRunSnapshot(document_id, run_id, status, "saved", response, stopped, False, tuple(receipts.values()))

    @staticmethod
    def _active_status(attempt):
        if attempt is None or attempt.handle is None:
            return "recovery_required", None
        stopped = attempt.handle.permit.stop_event.is_set()
        if attempt.handle.execution_running:
            return "running", stopped
        return ("recovery_required" if attempt.closure_error else "closing"), stopped

    @staticmethod
    def _public_response(observed):
        from .chat_history import public_chat_text
        positions = [i for i, m in enumerate(observed.messages)
                     if isinstance(m, HumanMessage) and m.id == observed.record.run_id]
        if len(positions) != 1:
            raise AiRuntimeError("invalid_saved_conversation")
        responses = [m for m in observed.messages[positions[0] + 1:]
                     if isinstance(m, AIMessage) and public_chat_text(m) is not None]
        return responses[-1].id if responses else None

    def _finish_automatically(self, attempt):
        # Completion is App work, independent of an HTTP observer staying open.
        # A failed reconciliation is retained for an explicit recover(), not a
        # repeated model/tool call or an unbounded background retry loop.
        with attempt.settling:
            try:
                attempt.result = self._settle(attempt)
            except Exception:
                attempt.closure_error = "run_recovery_required"
            finally:
                attempt.settled.set()

    def _run(self, attempt, permit):
        record = attempt.record
        current = self.owner.storage.read_current(record.document_id)
        if current.archived:
            raise AiRuntimeError("document_archived")
        if str(current.revision_id) != record.start_revision_id:
            raise AiRuntimeError("stale_view")
        config = {"configurable": {"thread_id": record.document_id},
            "callbacks": [_StopOnToken(permit.stop_event, attempt.tool_started)], "max_concurrency": 1,
            "recursion_limit": 96}
        before = self.graph.get_state({"configurable": {"thread_id": record.document_id}}, subgraphs=True)
        attempt.before_config = before.config
        attempt.before_state = deepcopy(before)
        previous = checked_model_view(before.values.get("jd_model_view"),
            dataset_id=record.dataset_id, document_id=record.document_id)
        notice = self.notices.read(record.document_id, previous.boundary if previous else None)
        if str(notice.head.revision_id) != record.start_revision_id:
            raise AiRuntimeError("stale_view")
        session = AiToolSession(self.owner, permit, self.history, self.reads, self.changes,
            self.codec, source_resolver=self.source_resolver)
        memory = MemoryReadSession.open(store=self.graph.store, engine=self.memory_engine,
            sources=self.conversation_sources, dataset_id=record.dataset_id,
            document_id=record.document_id, run_id=record.run_id) if self.memory_engine is not None else None
        if memory is not None:
            from caliburn_memory import PublicationStore
            memory_repair = MemoryRepairSession(memory, PublicationStore(self.memory_engine, memory.artifacts))
        else:
            memory_repair = None
        context = ConsultantContext(record.dataset_id, record.document_id, record.run_id,
            self.notices, self.codec, notice, tool_session=session, stop_event=permit.stop_event,
            source_notice=self.conversation_sources.for_turn(record.document_id, record.run_id)
                if self.conversation_sources is not None else None, memory_session=memory,
            memory_repair_session=memory_repair,
            background_availability=self._background_availability)
        # Disable remote traces even if the parent shell enabled them. Safe App
        # diagnostics and the native local Saver remain their separate owners.
        with tracing_context(enabled=False):
            attempt.invoked = True
            self.graph.invoke({"messages": [attempt.human], "jd_ai_run": record.model_dump(mode="json"),
                "jd_ai_bindings": [], "jd_ai_read": None,
                "jd_memory_view": memory.view if memory else None,
                "jd_memory_repair_bindings": []}, config, context=context, durability="sync")

    @staticmethod
    def _result(observed):
        messages = observed.messages
        positions = [i for i, m in enumerate(messages)
                     if isinstance(m, HumanMessage) and m.id == observed.record.run_id]
        if len(positions) != 1:
            raise AiRuntimeError("invalid_saved_conversation")
        responses = [m for m in messages[positions[0] + 1:]
                     if isinstance(m, AIMessage) and not m.tool_calls]
        return AiRunResult(observed.record.document_id, observed.record.run_id,
            observed.record.status, True, responses[-1].id if responses else None)

    def _confirm_input_not_saved(self, attempt):
        """Only the known local invocation with an unchanged idle root can release.

        A missing run alone is insufficient. Native sync ordering, no tool entry,
        actual Future completion and exact before/after state must all agree.
        """
        document = attempt.record.document_id
        if self.owner.status(document).identity is not None or attempt.tool_started.is_set():
            raise AiRuntimeError("run_recovery_required")
        if attempt.invoked:
            before = attempt.before_state
            current = self.graph.get_state({"configurable": {"thread_id": document}}, subgraphs=True)
            def position(state):
                if not isinstance(state, StateSnapshot) or state.next or state.tasks or state.interrupts:
                    raise AiRuntimeError("run_recovery_required")
                config = (state.config or {}).get("configurable", {})
                if config.get("thread_id") != document or config.get("checkpoint_ns", ""):
                    raise AiRuntimeError("run_recovery_required")
                return config.get("checkpoint_id")
            before_id, current_id = position(before), position(current)
            if before_id != current_id:
                raise AiRuntimeError("run_recovery_required")
            if current_id is not None:
                current = self.graph.get_state({"configurable": {"thread_id": document,
                    "checkpoint_ns": "", "checkpoint_id": current_id}}, subgraphs=True)
                if position(current) != before_id:
                    raise AiRuntimeError("run_recovery_required")
            if (current.values != before.values or any(isinstance(m, HumanMessage) and m.id == attempt.record.run_id
                    for m in current.values.get("messages", []))):
                raise AiRuntimeError("run_recovery_required")
        if self.owner.checkpoints.read(document) is not None:
            raise AiRuntimeError("run_recovery_required")

    def _binding_receipts(self, observed, *, include_active=True):
        record = observed.record
        bindings = decode_ai_bindings(observed.bindings, dataset_id=record.dataset_id,
            document_id=record.document_id, run_id=record.run_id)
        receipts, missing = {}, []
        active = self.owner.status(record.document_id).identity if include_active else None
        if active is not None and all(b.identity != active for b in bindings):
            raise AiRuntimeError("invalid_ai_binding")
        for binding in bindings:
            verify_binding_message(binding, observed.messages)
            found = self.owner.storage.lookup(binding.identity)
            if found is not None and found.confirmed:
                receipts[binding.identity.operation_id] = found
            # A now-readable receipt does not clear an earlier uncertain SQL
            # attempt in this host. Reconcile that original attempt too.
            if binding.identity == active or found is None or not found.confirmed:
                missing.append(binding)
        missing.sort(key=lambda binding: binding.identity != active)
        return bindings, receipts, missing

    def _settle(self, attempt, *, timeout=10):
        try:
            permit = attempt.handle.permit
            execution = attempt.handle.wait(0)  # Actual run Future and callback have finished.
            record = attempt.record
            try:
                observed = self.checkpoints.observe(record.document_id, record.run_id, record.dataset_id)
            except AiCheckpointError as error:
                if error.code != "run_not_found" or attempt.previous_host:
                    raise
                self.owner.finish_foreground(permit, lambda: self._confirm_input_not_saved(attempt))
                return AiRunResult(record.document_id, record.run_id, "failed", False, None)
            if observed.record.request_digest != record.request_digest:
                raise AiRuntimeError("operation_conflict")
            bindings, receipts, missing = self._binding_receipts(observed)
            for binding in missing:
                def confirm(identity, expected=binding.identity):
                    if identity != expected:
                        raise AiRuntimeError("invalid_ai_binding")
                    latest = self.checkpoints.observe(record.document_id, record.run_id, record.dataset_id)
                    if latest.bindings != observed.bindings:
                        raise AiRuntimeError("run_recovery_required")
                completion = self.owner.recover_foreground(permit, binding.identity, confirm, timeout=timeout)
                if completion.observation is None or not completion.observation.confirmed:
                    raise AiRuntimeError("run_recovery_required")
                receipts[binding.identity.operation_id] = completion.observation
            messages = list(observed.messages)
            pending = _pending_calls(messages)
            by_call = {(b.message_id, b.tool_call_id): b for b in bindings}
            recovered_repair = self._recover_pending_repair(observed, messages, pending)
            if recovered_repair is not None:
                messages.append(recovered_repair)
                pending = _pending_calls(messages)
            for key, call in pending.items():
                binding = by_call.get(key)
                if binding is not None:
                    value = project_observation(receipts[binding.identity.operation_id], self.codec)
                    failed = value["status"] not in {"committed", "no_change"}
                else:
                    value = ({"error": "memory_read_not_completed", "next_action": "stop"}
                        if call["name"] in MEMORY_READ_NAMES
                        else _request_not_executed() if call["name"] == REQUEST_TOOL_NAME
                        else read_failure("read_failed")
                        if call["name"] in {"jd_read", "jd_change_read"} else _not_executed())
                    failed = True
                messages.append(ToolMessage(id=str(uuid4()), tool_call_id=call["id"], name=call["name"],
                    content=read_json(value), status="error" if failed else "success"))
            if _pending_calls(messages):
                raise AiRuntimeError("invalid_saved_conversation")
            repairs = self._repair_evidence(observed, messages=messages)
            _verify_saved_results(messages, bindings, receipts, self.codec, run_id=record.run_id,
                verified_repair_calls=repairs)
            if observed.record.status != "running":
                status = observed.record.status
            else:
                status = "cancelled" if permit.stop_event.is_set() else "failed" if execution.error or pending or not observed.closed else "completed"
            closed = self.checkpoints.close(observed, status=status, messages=messages,
                bindings=observed.bindings, model_view=observed.model_view, read_binding=observed.read_binding)
            def confirm_closed():
                latest = self.checkpoints.observe(record.document_id, record.run_id, record.dataset_id)
                if latest.record != closed.record or latest.messages != closed.messages:
                    raise AiRuntimeError("run_recovery_required")
                if self.owner.checkpoints.read(record.document_id) is not None:
                    raise AiRuntimeError("run_recovery_required")
            self.owner.finish_foreground(permit, confirm_closed)
            result = self._result(closed)
            if not attempt.previous_host:
                self._wake_background(record.document_id)
            return result
        except AiRuntimeError:
            raise
        except Exception:
            raise AiRuntimeError("run_recovery_required") from None
