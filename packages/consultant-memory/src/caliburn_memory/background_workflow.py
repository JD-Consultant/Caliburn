"""Durable Runtime orchestration for one layered Memory background job.

The outer graph owns control flow and publication only.  B1 and B2 keep their
own semantic tools and durable checkpoints; this module never asks a third
model to orchestrate them or mutates their staged artifacts.
"""

from typing import Any, Literal, TypedDict
from uuid import NAMESPACE_URL, uuid4, uuid5

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from .case_maintenance import CaseMaintenanceWorkflow
from .memory import MemoryVersion
from .publication import PublishedHead, PublicationStore, PublishRequest
from .understanding_workflow import UnderstandingMaintenanceWorkflow


class BackgroundMemoryWorkflowState(TypedDict):
    source_reference: str
    base_publication_revision: int | None
    base_memory_version_id: str | None
    case_attempt_id: str
    case_stage: dict[str, Any] | None
    understanding_stage: dict[str, Any] | None
    case_rework_count: int
    stale_retry_count: int
    candidate_memory_version_id: str | None
    publish_request: dict[str, Any] | None
    status: Literal["pending", "completed", "blocked"]
    error_code: str | None
    result: dict[str, Any] | None


class BackgroundMemoryWorkflow:
    """Checkpointed B1 -> B2 -> complete bundle -> atomic publication chain."""

    def __init__(
        self,
        case_workflow: CaseMaintenanceWorkflow,
        understanding_workflow: UnderstandingMaintenanceWorkflow,
        publication: PublicationStore,
        checkpointer: BaseCheckpointSaver,
        *,
        max_stale_retries: int,
    ):
        case_session = case_workflow.session
        understanding_session = understanding_workflow.session
        if (understanding_session.case_session is not case_session
                or publication.artifacts is not case_session.artifacts
                or case_workflow.reader is not understanding_workflow.reader):
            raise ValueError("Background Memory components must share one document authority")
        if type(max_stale_retries) is not int or max_stale_retries < 1:
            raise ValueError("max_stale_retries must be a positive integer")
        self.case_workflow = case_workflow
        self.understanding_workflow = understanding_workflow
        self.publication = publication
        self.artifacts = publication.artifacts
        self.document_id = self.artifacts.document_id
        self.max_stale_retries = max_stale_retries
        route = str(uuid5(
            NAMESPACE_URL,
            "caliburn-layered-background-memory:" + self.document_id,
        ))
        self.config = {"configurable": {"thread_id": route}, "recursion_limit": 100}

        builder = StateGraph(BackgroundMemoryWorkflowState)
        builder.add_node("load_base", self._load_base)
        builder.add_node("run_b1", self._run_b1)
        builder.add_node("run_b2", self._run_b2)
        builder.add_node("route_b2", lambda _state: {})
        builder.add_node("block_rework", self._block_rework)
        builder.add_node("assemble_bundle", self._assemble_bundle)
        builder.add_node("prepare_publication", self._prepare_publication)
        builder.add_node("publish", self._publish)
        builder.add_edge(START, "load_base")
        builder.add_edge("load_base", "run_b1")
        builder.add_edge("run_b1", "run_b2")
        builder.add_edge("run_b2", "route_b2")
        builder.add_conditional_edges(
            "route_b2", self._after_b2,
            {"publishable": "assemble_bundle", "rework": "block_rework"},
        )
        builder.add_edge("block_rework", END)
        builder.add_edge("assemble_bundle", "prepare_publication")
        builder.add_edge("prepare_publication", "publish")
        builder.add_edge("publish", END)
        self.graph = builder.compile(checkpointer=checkpointer)

    def start(self, source_reference: str) -> dict[str, Any]:
        """Start one fixed source job, or return its already completed result."""
        self.case_workflow.reader.validate_reference(source_reference)
        snapshot = self.graph.get_state(self.config)
        if snapshot.values:
            previous = self._validate_state(snapshot.values)
            if previous["status"] == "pending":
                raise ValueError("Background Memory has a pending job; resume it instead")
            if previous["source_reference"] == source_reference:
                return dict(snapshot.values)
        initial: BackgroundMemoryWorkflowState = {
            "source_reference": source_reference,
            "base_publication_revision": None,
            "base_memory_version_id": None,
            "case_attempt_id": str(uuid4()),
            "case_stage": None,
            "understanding_stage": None,
            "case_rework_count": 0,
            "stale_retry_count": 0,
            "candidate_memory_version_id": None,
            "publish_request": None,
            "status": "pending",
            "error_code": None,
            "result": None,
        }
        return self.graph.invoke(initial, self.config, durability="sync")

    def resume(self) -> dict[str, Any]:
        """Resume the exact outer checkpoint; semantic sub-attempts remain fixed."""
        snapshot = self.graph.get_state(self.config)
        if not snapshot.values:
            raise ValueError("No background Memory job to resume")
        state = self._validate_state(snapshot.values)
        if state["status"] != "pending":
            return dict(snapshot.values)
        if not snapshot.next:
            raise ValueError("Pending background Memory checkpoint has no resumable node")
        return self.graph.invoke(None, self.config, durability="sync")

    def _validate_state(self, value: object) -> BackgroundMemoryWorkflowState:
        if type(value) is not dict:
            raise ValueError("Background Memory checkpoint is incompatible")
        required = set(BackgroundMemoryWorkflowState.__required_keys__)
        if not required <= set(value):
            raise ValueError("Background Memory checkpoint is incompatible")
        state = value
        if (type(state["source_reference"]) is not str
                or type(state["case_attempt_id"]) is not str
                or type(state["case_rework_count"]) is not int
                or state["case_rework_count"] < 0
                or type(state["stale_retry_count"]) is not int
                or state["stale_retry_count"] < 0
                or state["status"] not in {"pending", "completed", "blocked"}
                or (state["base_publication_revision"] is not None
                    and (type(state["base_publication_revision"]) is not int
                         or state["base_publication_revision"] < 0))
                or (state["base_memory_version_id"] is not None
                    and type(state["base_memory_version_id"]) is not str)
                or (state["case_stage"] is not None and type(state["case_stage"]) is not dict)
                or (state["understanding_stage"] is not None
                    and type(state["understanding_stage"]) is not dict)
                or (state["candidate_memory_version_id"] is not None
                    and type(state["candidate_memory_version_id"]) is not str)
                or (state["publish_request"] is not None
                    and type(state["publish_request"]) is not dict)
                or (state["error_code"] is not None and type(state["error_code"]) is not str)
                or (state["result"] is not None and type(state["result"]) is not dict)):
            raise ValueError("Background Memory checkpoint is incompatible")
        if ((state["base_publication_revision"] in (None, 0))
                != (state["base_memory_version_id"] is None)):
            raise ValueError("Background Memory base revision and version do not match")
        return state  # type: ignore[return-value]

    def _base_version(self, state: BackgroundMemoryWorkflowState) -> MemoryVersion | None:
        identifier = state["base_memory_version_id"]
        return MemoryVersion(self.document_id, identifier) if identifier is not None else None

    def _load_base(self, state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        self._validate_state(state)
        head = self.publication.current()
        return {
            "base_publication_revision": head.revision if head is not None else 0,
            "base_memory_version_id": head.memory.version_id if head is not None else None,
        }

    def _run_b1(self, state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        state = self._validate_state(state)
        revision = state["base_publication_revision"]
        if revision is None:
            raise ValueError("Background Memory base was not loaded")
        result = self.case_workflow.run_attempt(
            state["source_reference"],
            base_publication_revision=revision,
            base_version=self._base_version(state),
            case_attempt_id=state["case_attempt_id"],
        )
        stage = self.case_workflow.session.load(result.get("case_stage"))
        if not stage.completed:
            raise ValueError("B1 attempt returned without a completed stage")
        return {"case_stage": stage.to_dict()}

    def _run_b2(self, state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        state = self._validate_state(state)
        case_stage = self.case_workflow.session.load(state["case_stage"])
        result = self.understanding_workflow.run_attempt(
            case_stage, case_attempt_id=state["case_attempt_id"],
        )
        stage = self.understanding_workflow.session.load(result.get("understanding_stage"))
        if not stage.completed:
            raise ValueError("B2 attempt returned without a completed stage")
        return {"understanding_stage": stage.to_dict()}

    def _after_b2(self, state: BackgroundMemoryWorkflowState) -> Literal["publishable", "rework"]:
        state = self._validate_state(state)
        stage = self.understanding_workflow.session.load(state["understanding_stage"])
        return "publishable" if stage.outcome in {"changed", "no_op"} else "rework"

    @staticmethod
    def _block_rework(_state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        # Task 5 replaces this temporary fail-closed stop with one bounded B1 rework.
        return {"status": "blocked", "error_code": "case_rework_required"}

    def _assemble_bundle(self, state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        state = self._validate_state(state)
        revision = state["base_publication_revision"]
        if revision is None:
            raise ValueError("Background Memory base was not loaded")
        case_stage = self.case_workflow.session.load(state["case_stage"])
        understanding_stage = self.understanding_workflow.session.load(
            state["understanding_stage"])
        version = self.artifacts.save_bundle(
            base_publication_revision=revision,
            base_version=self._base_version(state),
            evidence_through_reference=state["source_reference"],
            case_guide=case_stage.case_guide,
            cases=self.case_workflow.session.current_cases(case_stage),
            understanding_guide=understanding_stage.understanding_guide,
            understandings=self.understanding_workflow.session.current_understandings(
                understanding_stage),
            supersessions=(*case_stage.supersessions, *understanding_stage.supersessions),
        )
        return {"candidate_memory_version_id": version.version_id}

    @staticmethod
    def _request_value(request: PublishRequest) -> dict[str, Any]:
        return {
            "operation_id": request.operation_id,
            "memory_version_id": request.memory.version_id,
            "expected_revision": request.expected_revision,
            "kind": request.kind,
            "artifact_digest": request.artifact_digest,
            "processed_source": request.processed_source,
            "repair_sources": list(request.repair_sources),
            "bundle_base_revision": request.bundle_base_revision,
            "bundle_base_version_id": request.bundle_base_version_id,
        }

    def _request(self, value: object) -> PublishRequest:
        if type(value) is not dict:
            raise ValueError("Background Memory publication request is unavailable")
        expected = {
            "operation_id", "memory_version_id", "expected_revision", "kind",
            "artifact_digest", "processed_source", "repair_sources",
            "bundle_base_revision", "bundle_base_version_id",
        }
        if set(value) != expected or type(value["repair_sources"]) is not list:
            raise ValueError("Background Memory publication request is invalid")
        return PublishRequest(
            operation_id=value["operation_id"],
            memory=MemoryVersion(self.document_id, value["memory_version_id"]),
            expected_revision=value["expected_revision"],
            kind=value["kind"],
            artifact_digest=value["artifact_digest"],
            processed_source=value["processed_source"],
            repair_sources=tuple(value["repair_sources"]),
            bundle_base_revision=value["bundle_base_revision"],
            bundle_base_version_id=value["bundle_base_version_id"],
        )

    def _prepare_publication(self, state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        state = self._validate_state(state)
        revision = state["base_publication_revision"]
        identifier = state["candidate_memory_version_id"]
        if revision is None or identifier is None:
            raise ValueError("Background Memory candidate is unavailable")
        request = self.publication.prepare(
            MemoryVersion(self.document_id, identifier),
            expected_revision=revision,
            kind="consolidation",
            processed_source=state["source_reference"],
        )
        return {"publish_request": self._request_value(request)}

    @staticmethod
    def _head_value(head: PublishedHead) -> dict[str, Any]:
        return {
            "revision": head.revision,
            "memory_version_id": head.memory.version_id,
            "processed_source": head.processed_source,
        }

    def _publish(self, state: BackgroundMemoryWorkflowState) -> dict[str, Any]:
        state = self._validate_state(state)
        head = self.publication.publish(self._request(state["publish_request"]))
        return {"status": "completed", "error_code": None, "result": self._head_value(head)}
