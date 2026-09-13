"""Fixed native root/child AI observation and explicitly owned stopped-run closure.

The caller must prove its run Future stopped and all SQL outcomes are confirmed
before close. This adapter cannot supply writer authority or death evidence. It
never invokes/resumes a graph, initializes a saver or rebuilds a tool candidate.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from hashlib import sha256
import json
from typing import Literal
from uuid import UUID

from langchain_core.messages import (
    AIMessage, BaseMessage, BaseMessageChunk, HumanMessage, RemoveMessage,
    ToolMessage, message_to_dict, messages_from_dict,
)
from langgraph.graph.message import add_messages
from langgraph.graph import START
from langgraph.types import StateSnapshot
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .consultant_context import checked_model_view


MAX_HUMAN_BYTES = 128 * 1024


class AiCheckpointError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError()
    return value


def _text(value):
    if (type(value) is not str or not value.strip() or "\0" in value
            or len(value.encode("utf-8")) > MAX_HUMAN_BYTES):
        raise ValueError()
    return value


def _request_digest(dataset_id, document_id, text):
    return sha256(_canonical({"dataset_id": dataset_id, "document_id": document_id,
                              "text": text}).encode("utf-8")).hexdigest()


class AiRunRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    format_version: int = Field(ge=1, le=1)
    dataset_id: str
    document_id: str
    run_id: str
    request_digest: str = Field(pattern="^[0-9a-f]{64}$")
    status: Literal["running", "completed", "cancelled", "failed"]

    @field_validator("dataset_id", "document_id", "run_id")
    @classmethod
    def validate_uuid(cls, value):
        return _uuid(value)


def new_run_record(dataset_id: str, document_id: str, run_id: str,
                   text: str) -> tuple[AiRunRecord, HumanMessage]:
    try:
        _uuid(dataset_id); _uuid(document_id); _uuid(run_id); _text(text)
        record = AiRunRecord(format_version=1, dataset_id=dataset_id,
            document_id=document_id, run_id=run_id,
            request_digest=_request_digest(dataset_id, document_id, text), status="running")
        return record, HumanMessage(id=run_id, content=text)
    except Exception:
        raise AiCheckpointError("invalid_input") from None


def _config(snapshot, document_id, namespace, *, empty=False):
    if not isinstance(snapshot, StateSnapshot):
        raise ValueError()
    config = snapshot.config.get("configurable", {}) if snapshot.config else {}
    if (config.get("thread_id") != document_id or config.get("checkpoint_ns", "") != namespace):
        raise ValueError()
    checkpoint_id = config.get("checkpoint_id")
    if not checkpoint_id:
        if empty and not snapshot.values and not snapshot.next and not snapshot.tasks and not snapshot.interrupts:
            return None
        raise ValueError()
    if type(checkpoint_id) is not str:
        raise ValueError()
    return {"configurable": {"thread_id": document_id, "checkpoint_ns": namespace,
                              "checkpoint_id": checkpoint_id}}


def _messages(value):
    if not isinstance(value, (tuple, list)):
        raise ValueError()
    result = deepcopy(list(value))
    if any(not isinstance(m, BaseMessage) or isinstance(m, (BaseMessageChunk, RemoveMessage))
           or type(m.id) is not str or not m.id for m in result):
        raise ValueError()
    if len({m.id for m in result}) != len(result):
        raise ValueError()
    return result


def _messages_json(messages):
    return _canonical([message_to_dict(message) for message in messages])


def _paired_view(value, messages, dataset_id, document_id):
    view = checked_model_view(value, dataset_id=dataset_id, document_id=document_id)
    if view is None:
        return None
    matching = [m for m in messages if isinstance(m, AIMessage) and m.type == "ai"
                and m.id == view.response_message_id]
    if (len(matching) != 1 or sha256(_canonical(matching[0].model_dump(mode="json")).encode()).hexdigest()
            != view.response_digest):
        raise ValueError()
    # A previous run's complete view remains valid when this run has no reply.
    return view.model_dump(mode="json")


def _material(snapshot, document_id, run_id, dataset_id):
    if type(snapshot.values) is not dict:
        raise ValueError()
    values = snapshot.values
    record = AiRunRecord.model_validate(values.get("jd_ai_run"), strict=True)
    if record.document_id != document_id or record.dataset_id != dataset_id or record.run_id != run_id:
        raise ValueError()
    if record.status == "running" and values.get("jd_manual_pending") is not None:
        raise ValueError()  # Mutually exclusive admissions; do not partially repair either.
    messages = _messages(values.get("messages", []))
    humans = [m for m in messages if m.id == run_id]
    if len(humans) != 1 or not isinstance(humans[0], HumanMessage):
        raise ValueError()
    text = _text(humans[0].content)
    if _request_digest(dataset_id, document_id, text) != record.request_digest:
        raise ValueError()
    bindings = values.get("jd_ai_bindings")
    read = values.get("jd_ai_read")
    if type(bindings) is not list or (read is not None and type(read) is not dict):
        raise ValueError()
    # Ownership and receipt validity of these opaque values belong to AiRuntime.
    _canonical(bindings); _canonical(read)
    view = _paired_view(values.get("jd_model_view"), messages, dataset_id, document_id)
    return record, messages, deepcopy(bindings), view, deepcopy(read)


@dataclass(frozen=True, slots=True)
class AiRunObservation:
    """Detached copies of one fixed position; fields do not grant admission."""
    _record_json: str = field(repr=False)
    _messages_json: str = field(repr=False)
    _bindings_json: str = field(repr=False)
    _view_json: str = field(repr=False)
    _read_json: str = field(repr=False)
    _root_config_json: str = field(repr=False)
    _source_config_json: str = field(repr=False)
    closed: bool

    @property
    def record(self): return AiRunRecord.model_validate_json(self._record_json, strict=True)
    @property
    def messages(self): return messages_from_dict(json.loads(self._messages_json))
    @property
    def bindings(self): return json.loads(self._bindings_json)
    @property
    def model_view(self): return json.loads(self._view_json)
    @property
    def read_binding(self): return json.loads(self._read_json)
    @property
    def root_config(self): return json.loads(self._root_config_json)
    @property
    def source_config(self): return json.loads(self._source_config_json)


class AiRunCheckpoints:
    def __init__(self, graph):
        self._graph = graph

    def _get(self, config):
        try:
            return self._graph.get_state(config, subgraphs=True)
        except Exception:
            raise AiCheckpointError("checkpoint_unavailable") from None

    def _initial_material(self, root, root_config, document_id, run_id, dataset_id):
        """Read this version's native input checkpoint, never pending overlay.

        LangGraph 1.2.11 stores the original input on START before the root loop
        checkpoint. Public Saver.get_tuple preserves that exact input even when
        the later loop put failed. This is observation, not execution permission.
        """
        if (root.next != (START,) or len(root.tasks) != 1 or root.tasks[0].name != START
                or root.tasks[0].state is not None or root.interrupts
                or (root.metadata or {}).get("source") != "input"):
            raise ValueError()
        try:
            saved = self._graph.checkpointer.get_tuple(root_config)
        except Exception:
            raise AiCheckpointError("checkpoint_unavailable") from None
        if (saved is None or _config(root._replace(config=saved.config), document_id, "") != root_config
                or saved.checkpoint["id"] != root_config["configurable"]["checkpoint_id"]
                or saved.metadata.get("source") != "input"):
            raise ValueError()
        payload = saved.checkpoint["channel_values"].get(START)
        if (type(payload) is not dict or set(payload) != {
                "jd_ai_run", "messages", "jd_ai_bindings", "jd_ai_read"}
                or type(payload["jd_ai_bindings"]) is not list or payload["jd_ai_bindings"]
                or payload["jd_ai_read"] is not None):
            raise ValueError()
        record = AiRunRecord.model_validate(payload["jd_ai_run"], strict=True)
        # Discovery selects the ID only from this exact saved START payload;
        # root.values may still contain the previous terminal run here.
        if run_id is None:
            run_id = record.run_id
        incoming = _messages(payload["messages"])
        previous = _messages(root.values.get("messages", []))
        if (record.status != "running" or len(incoming) != 1
                or not isinstance(incoming[0], HumanMessage) or incoming[0].id != run_id
                or any(message.id == run_id for message in previous)
                or root.values.get("jd_manual_pending") is not None):
            raise ValueError()
        prior_record = root.values.get("jd_ai_run")
        if prior_record is not None:
            prior = AiRunRecord.model_validate(prior_record, strict=True)
            if (prior.status == "running" or prior.run_id == run_id
                    or prior.document_id != document_id or prior.dataset_id != dataset_id):
                raise ValueError()
        # Native add_messages retains the prior complete conversation. Resetting
        # bindings/read comes from the original new-run input, not recovery edits.
        values = {**root.values, **payload, "messages": add_messages(previous, incoming)}
        return _material(root._replace(values=values), document_id, run_id, dataset_id)

    def observe(self, document_id: str, run_id: str, dataset_id: str) -> AiRunObservation:
        try:
            _uuid(document_id); _uuid(run_id); _uuid(dataset_id)
        except Exception:
            raise AiCheckpointError("invalid_input") from None
        return self._observe_current(document_id, run_id, dataset_id)

    def discover(self, document_id: str, dataset_id: str) -> AiRunObservation | None:
        """Read one fixed current position without a caller-supplied run ID.

        None means no AI material exists, not that a manual writer is absent or
        another host has stopped. Unknown pending work and damaged prior AI
        material block. This method never invokes/resumes or updates a graph.
        """
        try:
            _uuid(document_id); _uuid(dataset_id)
        except Exception:
            raise AiCheckpointError("invalid_input") from None
        return self._observe_current(document_id, None, dataset_id)

    def _observe_current(self, document_id, run_id, dataset_id):
        # Shared fixed-root decoder: discover never calls observe with a second
        # latest read, which could select a different run during publication.
        latest = self._get({"configurable": {"thread_id": document_id}})
        try:
            if not isinstance(latest, StateSnapshot) or type(latest.values) is not dict:
                raise ValueError()
            # An absent initial checkpoint is not evidence of admission.
            root_config = _config(latest, document_id, "", empty=True)
            if root_config is None:
                if run_id is None:
                    return None
                raise AiCheckpointError("run_not_found")
            root = self._get(root_config)
            if _config(root, document_id, "") != root_config:
                raise ValueError()
            if type(root.values) is not dict:
                raise ValueError()
            if root.next == (START,):
                record, messages, bindings, view, read = self._initial_material(
                    root, root_config, document_id, run_id, dataset_id)
                return AiRunObservation(_canonical(record.model_dump(mode="json")), _messages_json(messages),
                    _canonical(bindings), _canonical(view), _canonical(read), _canonical(root_config),
                    _canonical(root_config), False)
            if root.next not in ((), ("consultant",)):
                raise ValueError()
            raw_record = root.values.get("jd_ai_run")
            if raw_record is None:
                if (root.next or root.tasks or root.interrupts
                        or _messages(root.values.get("messages", []))
                        or root.values.get("jd_model_view") is not None
                        or root.values.get("jd_ai_read") is not None
                        or ("jd_ai_bindings" in root.values and root.values["jd_ai_bindings"] != [])):
                    raise ValueError()
                if run_id is None:
                    return None
                raise AiCheckpointError("run_not_found")
            root_record = AiRunRecord.model_validate(raw_record, strict=True)
            if root_record.document_id != document_id or root_record.dataset_id != dataset_id:
                raise ValueError()
            if run_id is None:
                run_id = root_record.run_id
            if root_record.run_id != run_id:
                raise AiCheckpointError("run_not_found")
            material = _material(root, document_id, run_id, dataset_id)
            source_config = root_config
            if root.tasks:
                if len(root.tasks) != 1 or root.tasks[0].name != "consultant":
                    raise ValueError()
                task = root.tasks[0]
                if type(task.id) is not str or not task.id:
                    raise ValueError()
                child_latest = task.state
                if not isinstance(child_latest, StateSnapshot):
                    raise ValueError()
                namespace = f"consultant:{task.id}"
                child_config = _config(child_latest, document_id, namespace, empty=True)
                if child_config is not None:
                    child = self._get(child_config)
                    if _config(child, document_id, namespace) != child_config:
                        raise ValueError()
                    if any(t.state is not None for t in child.tasks):
                        raise ValueError()  # This root has exactly one child layer.
                    child_material = _material(child, document_id, run_id, dataset_id)
                    if child_material[0] != material[0]:
                        raise ValueError()
                    root_messages, child_messages = material[1], child_material[1]
                    if _messages_json(child_messages[:len(root_messages)]) != _messages_json(root_messages):
                        raise ValueError()
                    material, source_config = child_material, child_config
            elif root.next or root.interrupts:
                raise ValueError()
            record, messages, bindings, view, read = material
            return AiRunObservation(_canonical(record.model_dump(mode="json")), _messages_json(messages),
                _canonical(bindings), _canonical(view), _canonical(read), _canonical(root_config),
                _canonical(source_config), not (root.next or root.tasks or root.interrupts))
        except AiCheckpointError:
            raise
        except Exception:
            raise AiCheckpointError("invalid_checkpoint") from None

    def close(self, observed: AiRunObservation, *, status: Literal["completed", "cancelled", "failed"],
              messages, bindings, model_view, read_binding) -> AiRunObservation:
        """One stopped-owner update, then exact readback even when ACK is lost.

        Caller has already waited for the actual run Future and verified SQL
        receipts. This method does not test those facts or resume child work.
        """
        try:
            if not isinstance(observed, AiRunObservation) or status not in {"completed", "cancelled", "failed"}:
                raise ValueError()
            record = observed.record
            original = observed.messages
            if not isinstance(messages, (tuple, list)):
                raise ValueError()
            proposed = deepcopy(list(messages))
            if (len(proposed) < len(original)
                    or _messages_json(proposed[:len(original)]) != _messages_json(original)):
                raise ValueError()
            pending_calls = {}
            answered = set()
            for message in original:
                if isinstance(message, AIMessage):
                    for call in message.tool_calls:
                        if call["id"] in pending_calls:
                            raise ValueError()
                        pending_calls[call["id"]] = call
                elif isinstance(message, ToolMessage):
                    answered.add(message.tool_call_id)
            for message in proposed[len(original):]:
                if (not isinstance(message, ToolMessage) or isinstance(message, BaseMessageChunk)
                        or message.tool_call_id not in pending_calls or message.tool_call_id in answered):
                    raise ValueError()
                answered.add(message.tool_call_id)
            proposed = _messages(add_messages([], proposed))
            if (len(proposed) != len(messages) or bindings != observed.bindings
                    or model_view != observed.model_view or read_binding != observed.read_binding):
                raise ValueError()
            _paired_view(model_view, proposed, record.dataset_id, record.document_id)
            target_record = record.model_copy(update={"status": status})
            desired = {"jd_ai_run": target_record.model_dump(mode="json"), "messages": proposed,
                "jd_ai_bindings": deepcopy(bindings), "jd_model_view": deepcopy(model_view),
                "jd_ai_read": deepcopy(read_binding)}
        except Exception:
            raise AiCheckpointError("invalid_closure") from None
        current = self.observe(record.document_id, record.run_id, record.dataset_id)

        def exact(result):
            return (result.closed and result.record == target_record
                and _messages_json(result.messages) == _messages_json(proposed)
                and result.bindings == bindings and result.model_view == model_view
                and result.read_binding == read_binding)

        if exact(current):
            return current
        if current != observed or record.status != "running":
            raise AiCheckpointError("checkpoint_changed")
        try:
            self._graph.update_state(observed.root_config, desired, as_node="consultant")
        except Exception:
            pass  # Uncertain ACK: never retry this update; inspect exact root.
        try:
            actual = self.observe(record.document_id, record.run_id, record.dataset_id)
            if exact(actual):
                return actual
        except Exception:
            pass
        raise AiCheckpointError("closure_unconfirmed") from None
