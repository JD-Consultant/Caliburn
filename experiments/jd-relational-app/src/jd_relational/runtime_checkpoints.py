"""Identity-only manual recovery on the document's native LangGraph root.

The caller owns document serialization and writer admission. A checkpoint is
neither a lock nor proof that another process stopped. This adapter never invokes
the consultant, initializes Saver tables, or persists a second message history.
"""

from typing import Any, Protocol
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.store.base import BaseStore
from langgraph.types import StateSnapshot

from .intents import AdmittedIdentity


_FIELDS = frozenset({
    "format_version", "document_id", "operation_id", "base_revision_id",
    "origin", "ai_run_id", "request_digest", "command_kind",
})


class CheckpointError(ValueError):
    """Fixed public error code; contains no persisted input or driver details."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class DocumentState(MessagesState):
    jd_memory_view: dict[str, Any] | None
    jd_manual_pending: dict[str, Any] | None
    jd_model_view: dict[str, Any] | None
    jd_ai_run: dict[str, Any] | None
    jd_ai_bindings: list[dict[str, Any]]
    jd_ai_read: dict[str, Any] | None
    jd_memory_repair_bindings: list[dict[str, Any]]


class _CheckpointGraph(Protocol):
    def get_state(self, config: dict, *, subgraphs: bool = False) -> StateSnapshot: ...
    def update_state(self, config: dict, values: dict, *, as_node: str) -> dict: ...


def build_document_graph(
    consultant: CompiledStateGraph, checkpointer: BaseCheckpointSaver, *, store: BaseStore | None = None,
) -> CompiledStateGraph:
    """Mount a native child directly; its checkpoints inherit the root Saver."""
    if (not isinstance(consultant, CompiledStateGraph)
            or not isinstance(checkpointer, BaseCheckpointSaver)
            or store is not None and not isinstance(store, BaseStore)
            or (isinstance(consultant, CompiledStateGraph)
                and consultant.store is not None and consultant.store is not store)
            or (consultant.checkpointer is not None and consultant.checkpointer is not True
                and consultant.checkpointer is not checkpointer)):
        raise CheckpointError("invalid_input") from None
    builder = StateGraph(DocumentState)
    builder.add_node("consultant", consultant)
    from .memory_repair_session import build_repair_node
    builder.add_node("memory_repair", build_repair_node())
    builder.add_edge(START, "consultant")
    builder.add_edge("consultant", END)
    builder.add_edge("memory_repair", "consultant")
    return builder.compile(checkpointer=checkpointer, store=store)


def _uuid_text(value: object) -> bool:
    if type(value) is not str:
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _checked_identity(value: object, code: str) -> AdmittedIdentity:
    try:
        if not isinstance(value, AdmittedIdentity):
            raise ValueError
        AdmittedIdentity.validate(value)
        if value.origin != "manual" or not _uuid_text(value.document_id):
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise CheckpointError(code) from None
    return value


def _encode(identity: AdmittedIdentity) -> dict:
    return {
        "format_version": 1,
        "document_id": identity.document_id,
        "operation_id": str(identity.operation_id),
        "base_revision_id": str(identity.base_revision_id),
        "origin": identity.origin,
        "ai_run_id": identity.ai_run_id,
        "request_digest": identity.request_digest,
        "command_kind": identity.command_kind,
    }


def _decode(value: object, document_id: str) -> AdmittedIdentity | None:
    if value is None:
        return None
    try:
        if (type(value) is not dict or set(value) != _FIELDS
                or type(value["format_version"]) is not int or value["format_version"] != 1
                or value["document_id"] != document_id
                or not _uuid_text(value["operation_id"])
                or not _uuid_text(value["base_revision_id"])):
            raise ValueError
        identity = AdmittedIdentity(
            value["document_id"], UUID(value["operation_id"]), UUID(value["base_revision_id"]),
            value["origin"], value["ai_run_id"], value["request_digest"], value["command_kind"],
        )
        return _checked_identity(identity, "invalid_checkpoint")
    except (ValueError, TypeError, KeyError):
        raise CheckpointError("invalid_checkpoint") from None


class DocumentCheckpoints:
    """Latest-root recovery metadata; caller must serialize the whole operation."""

    def __init__(self, graph: _CheckpointGraph):
        self._graph = graph

    @property
    def graph(self):
        return self._graph

    @staticmethod
    def _config(document_id: str) -> dict:
        if not _uuid_text(document_id):
            raise CheckpointError("invalid_input") from None
        return {"configurable": {"thread_id": document_id}}

    def read(self, document_id: str) -> AdmittedIdentity | None:
        """Read one idle root, including native child work, without local guesses."""
        config = self._config(document_id)
        try:
            snapshot = self._graph.get_state(config, subgraphs=True)
        except Exception:
            raise CheckpointError("checkpoint_unavailable") from None
        if not isinstance(snapshot, StateSnapshot) or type(snapshot.values) is not dict:
            raise CheckpointError("invalid_checkpoint") from None
        if snapshot.next or snapshot.tasks or snapshot.interrupts:
            raise CheckpointError("document_busy") from None
        run = snapshot.values.get("jd_ai_run")
        if run is not None:
            # A finished graph is not necessarily a settled App run. The AI
            # owner must confirm all writes and persist terminal closure first.
            from .ai_records import parse_run_record
            try:
                record = parse_run_record(run)
                if record.document_id != document_id:
                    raise ValueError()
            except Exception:
                raise CheckpointError("invalid_checkpoint") from None
            if record.status == "running":
                raise CheckpointError("document_busy") from None
        return _decode(snapshot.values.get("jd_manual_pending"), document_id)

    def admit(self, identity: AdmittedIdentity) -> None:
        """Persist the supplied original identity; this does not grant admission."""
        identity = _checked_identity(identity, "invalid_input")
        current = self.read(identity.document_id)
        if current == identity:
            return
        if current is not None:
            raise CheckpointError("pending_conflict") from None
        self._update(identity, identity)

    def close(self, identity: AdmittedIdentity) -> None:
        """Clear only this identity after the caller's separate terminal proof."""
        identity = _checked_identity(identity, "invalid_input")
        current = self.read(identity.document_id)
        if current is None:
            return
        if current != identity:
            raise CheckpointError("pending_conflict") from None
        self._update(identity, None)

    def _update(self, identity: AdmittedIdentity, target: AdmittedIdentity | None) -> None:
        try:
            self._graph.update_state(
                self._config(identity.document_id),
                {"jd_manual_pending": _encode(target) if target is not None else None},
                as_node="consultant",
            )
        except Exception:
            # An acknowledgement can be lost after persistence. Do not retry the
            # update; exactly one latest-root read below decides confirmation.
            pass
        actual = self.read(identity.document_id)
        if actual == target:
            return
        if actual is not None and actual != identity:
            raise CheckpointError("pending_conflict") from None
        raise CheckpointError("checkpoint_unavailable") from None
