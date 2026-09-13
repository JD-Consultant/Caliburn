"""Bounded, read-only lookup on the current native checkpoint ancestry.

LangGraph history includes side branches. Only public Saver.parent_config links
select an older run here; message equality is a consistency check, not lineage.
No invoke, update, receipt reconstruction, or permission to repeat an operation.
"""

from copy import deepcopy
from uuid import UUID

from langchain_core.messages import HumanMessage
from langgraph.types import StateSnapshot

from .ai_checkpoints import AiCheckpointError, AiRunCheckpoints, AiRunObservation
from .ai_records import parse_run_record


# A bounded application lookup, not a claim about a native database query limit.
MAX_PARENT_LOOKUPS = 256


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError()


def _position(config, document_id):
    if type(config) is not dict or type(config.get("configurable")) is not dict:
        raise ValueError()
    scope = config["configurable"]
    checkpoint_id = scope.get("checkpoint_id")
    if (scope.get("thread_id") != document_id or scope.get("checkpoint_ns") != ""
            or type(checkpoint_id) is not str or not checkpoint_id.strip() or "\0" in checkpoint_id):
        raise ValueError()
    return {"configurable": {"thread_id": document_id, "checkpoint_ns": "",
                              "checkpoint_id": checkpoint_id}}


class AiRunHistory:
    def __init__(self, checkpoints: AiRunCheckpoints):
        if not isinstance(checkpoints, AiRunCheckpoints):
            raise AiCheckpointError("invalid_input")
        self._checkpoints = checkpoints

    def find(self, document_id: str, run_id: str, dataset_id: str) -> AiRunObservation | None:
        """Return the original observation, or verified absence from full messages.

        The caller must hold its existing document admission when using absence
        to admit a new run. The current full, append-only messages contract is
        required; this method does not authorize deletion or compaction.
        """
        try:
            _uuid(document_id); _uuid(run_id); _uuid(dataset_id)
        except Exception:
            raise AiCheckpointError("invalid_input") from None

        # One latest discovery only. All subsequent reads remain pinned to it.
        current = self._checkpoints.discover(document_id, dataset_id)
        if current is None:
            return None
        try:
            messages = current.messages
            humans = [index for index, message in enumerate(messages) if isinstance(message, HumanMessage)]
            if not humans or messages[humans[-1]].id != current.record.run_id:
                raise ValueError()
            matches = [index for index, message in enumerate(messages) if message.id == run_id]
            if not matches:
                return None
            if len(matches) != 1 or not isinstance(messages[matches[0]], HumanMessage):
                # An AI/Tool ID collision is not an unused native add_messages ID.
                raise AiCheckpointError("original_run_lookup_required")
            if current.record.run_id == run_id:
                return current
            next_human = next(index for index in humans if index > matches[0])
            expected_messages = messages[:next_human]
            position = _position(current.root_config, document_id)
        except AiCheckpointError:
            raise
        except Exception:
            raise AiCheckpointError("invalid_checkpoint") from None

        visited = set()
        graph = self._checkpoints.graph
        for _ in range(MAX_PARENT_LOOKUPS):
            checkpoint_id = position["configurable"]["checkpoint_id"]
            if checkpoint_id in visited:
                raise AiCheckpointError("original_run_lookup_required")
            visited.add(checkpoint_id)
            try:
                saved = graph.checkpointer.get_tuple(deepcopy(position))
            except Exception:
                raise AiCheckpointError("checkpoint_unavailable") from None
            if saved is None:
                raise AiCheckpointError("original_run_lookup_required")
            try:
                if (_position(saved.config, document_id) != position
                        or saved.checkpoint["id"] != checkpoint_id):
                    raise ValueError()
            except Exception:
                raise AiCheckpointError("invalid_checkpoint") from None
            try:
                snapshot = graph.get_state(deepcopy(position), subgraphs=True)
            except Exception:
                raise AiCheckpointError("checkpoint_unavailable") from None
            try:
                if (not isinstance(snapshot, StateSnapshot) or type(snapshot.values) is not dict
                        or _position(snapshot.config, document_id) != position):
                    raise ValueError()
                raw_record = snapshot.values.get("jd_ai_run")
                record = parse_run_record(raw_record) if raw_record is not None else None
                if record is not None and (record.document_id != document_id or record.dataset_id != dataset_id):
                    raise ValueError()
                # START may still project the prior record: it is not terminal.
                if (record is not None and record.run_id == run_id and record.status != "running"
                        and not snapshot.next and not snapshot.tasks and not snapshot.interrupts):
                    candidate = self._checkpoints.observe_at(document_id, run_id, dataset_id, position)
                    if (not candidate.closed or candidate.record.status == "running"
                            or candidate.messages != expected_messages):
                        raise ValueError()
                    return candidate
                if saved.parent_config is None:
                    raise AiCheckpointError("original_run_lookup_required")
                position = _position(saved.parent_config, document_id)
            except AiCheckpointError:
                raise
            except Exception:
                raise AiCheckpointError("invalid_checkpoint") from None
        raise AiCheckpointError("original_run_lookup_required")
