from __future__ import annotations

import asyncio
from copy import deepcopy
from typing import Annotated, Any, TypedDict

from langgraph.config import get_store
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class SimulatedAnalysisCrash(RuntimeError):
    pass


class SimulatedAcceptanceCrash(RuntimeError):
    pass


class SimulatedCompletionCrash(RuntimeError):
    pass


class StaleRevision(RuntimeError):
    pass


class SourceConflict(RuntimeError):
    pass


class DocumentRuntime:
    """Single-process run admission for the current local-only deployment."""

    def __init__(self, graph: Any) -> None:
        self.graph = graph
        self._thread_locks: dict[str, asyncio.Lock] = {}

    async def ainvoke(self, input_value: Any, config: dict[str, Any]) -> Any:
        thread_id = config["configurable"]["thread_id"]
        lock = self._thread_locks.setdefault(thread_id, asyncio.Lock())
        async with lock:
            return await self.graph.ainvoke(input_value, config)

    async def aget_state(self, config: dict[str, Any]) -> Any:
        return await self.graph.aget_state(config)


def merge_source_events(
    current: list[dict[str, str]], updates: list[dict[str, str]]
) -> list[dict[str, str]]:
    merged = list(current)
    by_id = {event["input_event_id"]: event for event in merged}
    for event in updates:
        existing = by_id.get(event["input_event_id"])
        if existing is None:
            merged.append(event)
            by_id[event["input_event_id"]] = event
        elif existing != event:
            raise ValueError(f"conflicting source event: {event['input_event_id']}")
    return merged


class DocumentState(TypedDict, total=False):
    action: str
    document_id: str
    payload: dict[str, Any]
    source_events: Annotated[list[dict[str, str]], merge_source_events]
    processing_status: str
    work_model: dict[str, Any]
    focus_plan: dict[str, Any]
    progress_and_gaps: dict[str, Any]
    pending_proposals: dict[str, Any]
    current_jd: dict[str, Any]
    visible_turn: dict[str, Any]
    revision: int
    last_source_id: str
    source_disposition: str


class StoreBackedDocumentState(TypedDict, total=False):
    action: str
    document_id: str
    payload: dict[str, Any]
    processing_status: str
    work_model: dict[str, Any]
    focus_plan: dict[str, Any]
    progress_and_gaps: dict[str, Any]
    pending_proposals: dict[str, Any]
    current_jd: dict[str, Any]
    visible_turn: dict[str, Any]
    revision: int
    last_source_id: str
    source_disposition: str


def submit_source(
    *,
    document_id: str,
    input_event_id: str,
    text: str,
    fail_after_source: bool = False,
    fail_before_source_checkpoint: bool = False,
    fail_before_mark_complete: bool = False,
    analysis_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "action": "submit_source",
        "document_id": document_id,
        "payload": {
            "input_event_id": input_event_id,
            "text": text,
            "fail_after_source": fail_after_source,
            "fail_before_source_checkpoint": fail_before_source_checkpoint,
            "fail_before_mark_complete": fail_before_mark_complete,
            "analysis_result": analysis_result or {},
        },
    }


def direct_edit(
    *,
    document_id: str,
    expected_revision: int,
    current_jd: dict[str, Any],
) -> dict[str, Any]:
    return {
        "action": "direct_edit",
        "document_id": document_id,
        "payload": {
            "expected_revision": expected_revision,
            "current_jd": current_jd,
        },
    }


def export_current_jd(state: DocumentState) -> dict[str, Any]:
    return deepcopy(state["current_jd"])


async def delete_store_backed_document(
    *,
    checkpointer: Any,
    store: Any,
    thread_id: str,
    document_id: str,
) -> None:
    """Idempotent cleanup after a product catalog has tombstoned the document."""
    await checkpointer.adelete_thread(thread_id)
    namespace = ("job-analysis", document_id, "sources")
    while items := await store.asearch(namespace, limit=100):
        await asyncio.gather(*(store.adelete(namespace, item.key) for item in items))


def build_document_graph(checkpointer: Any) -> Any:
    def accept_source(state: DocumentState) -> DocumentState:
        payload = state["payload"]
        return {
            "source_events": [
                {
                    "input_event_id": payload["input_event_id"],
                    "speaker": "employee",
                    "text": payload["text"],
                }
            ],
            "processing_status": "source_saved",
            "current_jd": state.get("current_jd", {}),
            "revision": state.get("revision", 0) + 1,
        }

    def analyze(state: DocumentState) -> DocumentState:
        if state["payload"].get("fail_after_source"):
            raise SimulatedAnalysisCrash("simulated crash after source checkpoint")
        return {
            **state["payload"].get("analysis_result", {}),
            "processing_status": "complete",
            "revision": state["revision"] + 1,
        }

    def review_proposal(state: DocumentState) -> DocumentState:
        proposal_id = state["payload"]["proposal_id"]
        proposal = state["pending_proposals"][proposal_id]
        response = interrupt(
            {
                "kind": "proposal_review",
                "proposal_id": proposal_id,
                "proposal": proposal,
                "allowed_decisions": ["approve", "edit", "reject", "defer"],
            }
        )
        decision = response.get("decision")
        proposals = deepcopy(state["pending_proposals"])
        if decision == "defer":
            proposals[proposal_id]["status"] = "deferred"
            return {
                "pending_proposals": proposals,
                "revision": state["revision"] + 1,
            }
        if decision != "approve":
            raise ValueError("this spike currently implements approve only")

        proposals[proposal_id]["status"] = "accepted"
        return {
            "pending_proposals": proposals,
            "current_jd": deepcopy(proposal["after"]),
            "revision": state["revision"] + 1,
        }

    def apply_direct_edit(state: DocumentState) -> DocumentState:
        expected_revision = state["payload"]["expected_revision"]
        if state["revision"] != expected_revision:
            raise StaleRevision(
                f"expected revision {expected_revision}, found {state['revision']}"
            )
        return {
            "current_jd": deepcopy(state["payload"]["current_jd"]),
            "revision": state["revision"] + 1,
        }

    def route_action(state: DocumentState) -> str:
        return state["action"]

    builder = StateGraph(DocumentState)
    builder.add_node("accept_source", accept_source)
    builder.add_node("analyze", analyze)
    builder.add_node("review_proposal", review_proposal)
    builder.add_node("direct_edit", apply_direct_edit)
    builder.add_conditional_edges(
        START,
        route_action,
        {
            "submit_source": "accept_source",
            "review_proposal": "review_proposal",
            "direct_edit": "direct_edit",
        },
    )
    builder.add_edge("accept_source", "analyze")
    builder.add_edge("analyze", END)
    builder.add_edge("review_proposal", END)
    builder.add_edge("direct_edit", END)
    return builder.compile(checkpointer=checkpointer)


def build_store_backed_document_graph(checkpointer: Any, store: Any) -> Any:
    """Probe design: Store owns immutable Source; checkpoints own derived state."""

    async def accept_source(
        state: StoreBackedDocumentState,
    ) -> StoreBackedDocumentState:
        payload = state["payload"]
        immutable_source = {
            "document_id": state["document_id"],
            "input_event_id": payload["input_event_id"],
            "speaker": "employee",
            "text": payload["text"],
        }
        namespace = ("job-analysis", state["document_id"], "sources")
        source_store = get_store()
        existing = await source_store.aget(namespace, payload["input_event_id"])
        if existing is not None:
            existing_source = {
                key: existing.value[key]
                for key in ("document_id", "input_event_id", "speaker", "text")
            }
            if existing_source != immutable_source:
                raise SourceConflict(
                    f"conflicting source event: {payload['input_event_id']}"
                )
            if existing.value["processing_status"] == "complete":
                disposition = "replay"
            elif (
                state.get("last_source_id") == payload["input_event_id"]
                and state.get("processing_status") == "analysis_complete"
            ):
                disposition = "mark_only"
            elif (
                state.get("last_source_id") == payload["input_event_id"]
                and state.get("processing_status") == "source_saved"
            ):
                disposition = "resume"
            else:
                disposition = "recover"
            result: StoreBackedDocumentState = {
                "last_source_id": payload["input_event_id"],
                "source_disposition": disposition,
            }
            if disposition == "recover":
                result.update(
                    {
                        "processing_status": "source_saved",
                        "current_jd": state.get("current_jd", {}),
                        "revision": state.get("revision", 0) + 1,
                    }
                )
            return result

        source_record = {**immutable_source, "processing_status": "pending"}
        await source_store.aput(
            namespace,
            payload["input_event_id"],
            source_record,
            index=False,
        )
        if payload.get("fail_before_source_checkpoint"):
            raise SimulatedAcceptanceCrash(
                "simulated crash after Store put and before source checkpoint"
            )
        return {
            "last_source_id": payload["input_event_id"],
            "source_disposition": "new",
            "processing_status": "source_saved",
            "current_jd": state.get("current_jd", {}),
            "revision": state.get("revision", 0) + 1,
        }

    def analyze(state: StoreBackedDocumentState) -> StoreBackedDocumentState:
        if state["payload"].get("fail_after_source"):
            raise SimulatedAnalysisCrash("simulated crash after source checkpoint")
        return {
            **state["payload"].get("analysis_result", {}),
            "processing_status": "analysis_complete",
            "revision": state["revision"] + 1,
        }

    async def mark_source_complete(
        state: StoreBackedDocumentState,
    ) -> StoreBackedDocumentState:
        if state["payload"].get("fail_before_mark_complete"):
            raise SimulatedCompletionCrash(
                "simulated crash after analysis checkpoint and before Store completion"
            )
        payload = state["payload"]
        namespace = ("job-analysis", state["document_id"], "sources")
        source_store = get_store()
        existing = await source_store.aget(namespace, payload["input_event_id"])
        if existing is None:
            raise RuntimeError("source disappeared before completion")
        completed = dict(existing.value)
        completed["processing_status"] = "complete"
        await source_store.aput(
            namespace,
            payload["input_event_id"],
            completed,
            index=False,
        )
        return {"processing_status": "complete"}

    def route_after_source(state: StoreBackedDocumentState) -> str:
        if state["source_disposition"] == "replay":
            return "done"
        if state["source_disposition"] == "mark_only":
            return "mark_source_complete"
        return "analyze"

    builder = StateGraph(StoreBackedDocumentState)
    builder.add_node("accept_source", accept_source)
    builder.add_node("analyze", analyze)
    builder.add_node("mark_source_complete", mark_source_complete)
    builder.add_edge(START, "accept_source")
    builder.add_conditional_edges(
        "accept_source",
        route_after_source,
        {
            "analyze": "analyze",
            "mark_source_complete": "mark_source_complete",
            "done": END,
        },
    )
    builder.add_edge("analyze", "mark_source_complete")
    builder.add_edge("mark_source_complete", END)
    return builder.compile(checkpointer=checkpointer, store=store)
