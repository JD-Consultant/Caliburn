"""C: narrow layered-bundle repair using existing B1/B2 invariants.

The App owns admission and resolves model evidence keys before this graph is
started.  This module owns deterministic staging, immutable bundle creation,
the native saved publication request, CAS publication and receipt recovery.
"""
from collections.abc import Callable
from dataclasses import asdict, replace
from typing import Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, ConfigDict, Field, model_validator

from caliburn_memory.bundle import CaseArtifact, WorkUnderstandingArtifact
from caliburn_memory.case_maintenance import (
    HISTORY_ORDER_SCOPE, CaseMaintenanceError, CaseMaintenanceSession,
)
from caliburn_memory.memory import MemoryArtifacts, MemoryVersion
from caliburn_memory.patch import MAX_PATCH_CHARACTERS
from caliburn_memory.publication import (
    PublicationUncertain, PublishRequest, StalePublication,
)
from caliburn_memory.sources import (
    MAX_EVIDENCE_EXCHANGES, EvidenceExchangePage,
)
from caliburn_memory.understanding_maintenance import (
    UnderstandingMaintenanceError, UnderstandingMaintenanceSession,
)


class LayeredUnderstandingRepair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    understanding_id: str
    action: Literal["revise", "revalidate"]
    diff: str | None
    supporting_case_ids: list[str] = Field(min_length=1)
    route_note: str | None

    @model_validator(mode="after")
    def action_fields(self):
        if ((self.action == "revise" and (not isinstance(self.diff, str) or not self.diff.strip()))
                or (self.action == "revalidate"
                    and (self.diff is not None or self.route_note is not None))):
            raise ValueError("Invalid understanding repair action")
        return self


class LayeredRepair(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    case_id: str
    case_diff: str
    case_route_note: str | None
    remove_source_references: list[str]
    understanding_updates: list[LayeredUnderstandingRepair]

    @model_validator(mode="after")
    def bounded(self):
        if (not self.case_diff.strip()
                or len(self.case_diff) + sum(len(item.diff or "")
                                             for item in self.understanding_updates)
                    > MAX_PATCH_CHARACTERS
                or len(set(self.remove_source_references))
                    != len(self.remove_source_references)
                or len({item.understanding_id for item in self.understanding_updates})
                    != len(self.understanding_updates)):
            raise ValueError("Invalid layered repair")
        return self


class LayeredRepairState(TypedDict, total=False):
    operation_id: str
    base: dict
    source_reference: str
    repair: dict
    index: int
    case_stage: dict
    understanding_stage: dict
    material: dict
    version: dict
    request: dict
    outcome: dict | None


def build_layered_repair_graph(
    resolve_workflow: Callable[[Runtime], "LayeredRepairWorkflow"],
) -> CompiledStateGraph:
    """Compile durable deterministic repair steps without capturing resources."""
    if not callable(resolve_workflow):
        raise TypeError("layered_repair_workflow_resolver_required")

    def step(name):
        def execute(state: LayeredRepairState, runtime: Runtime):
            workflow = resolve_workflow(runtime)
            if not isinstance(workflow, LayeredRepairWorkflow):
                raise TypeError("layered_repair_workflow_unavailable")
            return getattr(workflow, "_" + name)(state)
        return execute

    builder = StateGraph(LayeredRepairState)
    for name in ("seed", "edit", "validate", "save", "prepare", "publish"):
        builder.add_node(name, step(name))
    builder.add_edge(START, "seed")
    builder.add_conditional_edges(
        "seed", lambda state: END if state.get("outcome") else
        ("edit" if state["repair"]["understanding_updates"] else "validate"),
    )
    builder.add_conditional_edges(
        "edit", lambda state: END if state.get("outcome") else
        ("edit" if state["index"] < len(state["repair"]["understanding_updates"])
         else "validate"),
    )
    builder.add_conditional_edges("validate", lambda state: END if state.get("outcome") else "save")
    builder.add_edge("save", "prepare")
    builder.add_edge("prepare", "publish")
    builder.add_edge("publish", END)
    return builder.compile()


class LayeredRepairWorkflow:
    """Prepare and atomically publish one complete layered repair bundle."""

    def __init__(self, artifacts: MemoryArtifacts, publication, source):
        self.artifacts, self.publication, self.source = artifacts, publication, source
        if len({artifacts.document_id, publication.document_id, source.document_id}) != 1:
            raise ValueError("Layered repair components belong to different documents")
        self.case_session = CaseMaintenanceSession(artifacts)
        self.understanding_session = UnderstandingMaintenanceSession(
            artifacts, self.case_session,
        )
        self.graph = build_layered_repair_graph(lambda runtime: self)

    def _guide(self, head) -> str:
        if head is None:
            return ""
        manifest = self.artifacts.bundle_manifest(head.memory)
        return (
            f"【案例導覽｜{manifest.case_guide.path}】\n"
            f"{self.artifacts.case_guide(head.memory)}\n\n"
            f"【工作理解導覽｜{manifest.understanding_guide.path}】\n"
            f"{self.artifacts.understanding_guide(head.memory)}"
        )

    def _feedback(self, status, head, detail, **extra):
        return {"status": status, "head": asdict(head) if head else None,
                "guide": self._guide(head), "detail": detail, **extra}

    def _history(self, through_reference: str):
        exchanges = []
        offset = 0
        while True:
            page = self.source.history_exchanges(
                through_reference, offset=offset, limit=MAX_EVIDENCE_EXCHANGES,
            )
            if not isinstance(page, EvidenceExchangePage) or page.order != "oldest_to_newest":
                raise ValueError("Canonical source order is unavailable")
            exchanges.extend(page.exchanges)
            if page.next_offset is None:
                return tuple(exchanges)
            if page.next_offset <= offset:
                raise ValueError("Canonical source history did not advance")
            offset = page.next_offset

    @staticmethod
    def _version(base: dict) -> MemoryVersion:
        return MemoryVersion(**base["memory"])

    def _seed(self, state: LayeredRepairState):
        try:
            repair = LayeredRepair.model_validate(state["repair"])
        except Exception:
            return {"outcome": {"status": "invalid_edit",
                "detail": "Layered repair input is invalid."}}
        current = self.publication.current()
        base = state.get("base")
        if not base:
            return {"outcome": self._feedback(
                "no_memory", current,
                "No layered Memory was loaded; background maintenance initializes it.",
            )}
        if current is None or asdict(current) != base:
            return {"outcome": self._feedback(
                "stale", current,
                "Read the refreshed layered Memory and reconsider the repair.",
            )}
        try:
            if self.artifacts.bundle_base(current.memory) is None:
                return {"outcome": self._feedback(
                    "no_memory", current, "The selected Memory is not a layered bundle.",
                )}
            self.source.read(state["source_reference"])
            case_stage = self.case_session.open(
                base_publication_revision=current.revision,
                base_version=current.memory,
                source_reference=state["source_reference"],
            )
            case_stage, case = self.case_session.observe_case(case_stage, repair.case_id)
            targets = {*case.source_references, state["source_reference"]}
            found = {}
            for ordinal, exchange in enumerate(self._history(state["source_reference"])):
                if exchange.source_reference not in targets:
                    continue
                case_stage, evidence = self.case_session.register_evidence(
                    case_stage, exchange,
                    order_key=(HISTORY_ORDER_SCOPE, ordinal, 0), next_offset=None,
                )
                found[exchange.source_reference] = evidence.evidence_key
            if set(found) != targets:
                raise ValueError("Canonical history does not contain every case source")
            removals = set(repair.remove_source_references)
            if state["source_reference"] in removals:
                raise ValueError("The explicit correction source cannot be removed")
            if not removals.issubset(case.source_references):
                raise ValueError("A removed source is not attached to the current case")
            additions = ([] if state["source_reference"] in case.source_references else
                         [found[state["source_reference"]]])
            case_stage = self.case_session.revise_case(
                case_stage, case_id=repair.case_id, diff=repair.case_diff,
                route_note=repair.case_route_note,
                add_evidence_keys=additions,
                remove_evidence_keys=[found[reference] for reference in removals],
            )
            case_stage = self.case_session.finish(case_stage)
            understanding_stage = self.understanding_session.open(case_stage)
            expected = set(understanding_stage.required_understanding_ids)
            supplied = {item.understanding_id for item in repair.understanding_updates}
            if supplied != expected:
                return {"outcome": self._feedback(
                    "scope_too_broad", current,
                    "Repair must handle every directly affected current work understanding.",
                )}
            understanding_stage, _ = self.understanding_session.observe_case(
                understanding_stage, repair.case_id,
            )
            return {"repair": repair.model_dump(mode="json"), "index": 0,
                    "case_stage": case_stage.to_dict(),
                    "understanding_stage": understanding_stage.to_dict(),
                    "outcome": None}
        except (CaseMaintenanceError, UnderstandingMaintenanceError, ValueError) as error:
            return {"outcome": self._feedback(
                "invalid_edit", current, str(error),
            )}

    def _edit(self, state: LayeredRepairState):
        current = self.publication.current()
        try:
            repair = LayeredRepair.model_validate(state["repair"])
            stage = self.understanding_session.load(state["understanding_stage"])
            update = repair.understanding_updates[state["index"]]
            for case_id in update.supporting_case_ids:
                if case_id not in stage.read_case_ids:
                    stage, _ = self.understanding_session.observe_case(stage, case_id)
            stage, _ = self.understanding_session.observe_understanding(
                stage, update.understanding_id,
            )
            if update.action == "revise":
                stage = self.understanding_session.revise_understanding(
                    stage, understanding_id=update.understanding_id,
                    diff=update.diff, supporting_case_ids=update.supporting_case_ids,
                    route_note=update.route_note,
                )
            else:
                stage = self.understanding_session.revalidate_understanding(
                    stage, understanding_id=update.understanding_id,
                    supporting_case_ids=update.supporting_case_ids,
                )
            return {"index": state["index"] + 1,
                    "understanding_stage": stage.to_dict()}
        except (CaseMaintenanceError, UnderstandingMaintenanceError,
                IndexError, ValueError) as error:
            return {"outcome": self._feedback("invalid_edit", current, str(error))}

    def _validate(self, state: LayeredRepairState):
        current = self.publication.current()
        try:
            case_stage = self.case_session.load(state["case_stage"])
            stage = self.understanding_session.finish(
                self.understanding_session.load(state["understanding_stage"]),
            )
            cases = self.case_session.current_cases(case_stage)
            understandings = self.understanding_session.current_understandings(stage)
            return {"understanding_stage": stage.to_dict(), "material": {
                "case_guide": case_stage.case_guide,
                "cases": [asdict(item) for item in cases],
                "understanding_guide": stage.understanding_guide,
                "understandings": [asdict(item) for item in understandings],
            }}
        except (CaseMaintenanceError, UnderstandingMaintenanceError,
                ValueError) as error:
            return {"outcome": self._feedback("invalid_edit", current, str(error))}

    def _save(self, state: LayeredRepairState):
        material = state["material"]
        version = self.artifacts.save_bundle(
            base_publication_revision=state["base"]["revision"],
            base_version=self._version(state["base"]),
            evidence_through_reference=state["source_reference"],
            case_guide=material["case_guide"],
            cases=tuple(CaseArtifact(**item) for item in material["cases"]),
            understanding_guide=material["understanding_guide"],
            understandings=tuple(WorkUnderstandingArtifact(**item)
                                 for item in material["understandings"]),
        )
        return {"version": asdict(version)}

    def _prepare(self, state: LayeredRepairState):
        request = self.publication.prepare(
            MemoryVersion(**state["version"]),
            expected_revision=state["base"]["revision"], kind="repair",
            repair_sources=(state["source_reference"],),
        )
        return {"request": asdict(replace(request, operation_id=state["operation_id"]))}

    def _current_after(self, applied):
        current = self.publication.current()
        if (current is None or current.memory.document_id != self.artifacts.document_id
                or applied.memory.document_id != self.artifacts.document_id
                or current.revision < applied.revision):
            raise PublicationUncertain("Current layered Memory head is not confirmed")
        return current

    def reconcile(self, request: PublishRequest):
        try:
            if (type(request) is not PublishRequest or request.kind != "repair"
                    or request.memory.document_id != self.artifacts.document_id
                    or request.processed_source is not None
                    or len(request.repair_sources) != 1
                    or request.bundle_base_revision != request.expected_revision
                    or request.bundle_base_version_id is None):
                raise PublicationUncertain("Saved layered repair request is not confirmed")
            receipt = self.publication.receipt(request.operation_id)
            if (receipt is None or receipt.request_digest != request.digest()
                    or receipt.kind != "repair"
                    or receipt.repair_sources != request.repair_sources
                    or receipt.base_revision != request.expected_revision
                    or receipt.result.memory != request.memory
                    or receipt.result.revision != receipt.base_revision + 1):
                raise PublicationUncertain("Layered repair receipt does not match the request")
            self._current_after(receipt.result)
            return self._feedback(
                "applied", receipt.result,
                "Layered repair was published; cancellation did not revert Memory.",
                applied_head=asdict(receipt.result),
                source_reference=receipt.repair_sources[0],
            )
        except PublicationUncertain:
            raise
        except Exception:
            raise PublicationUncertain("Layered repair reconciliation is unavailable") from None

    def _publish(self, state: LayeredRepairState):
        data = dict(state["request"])
        data["memory"] = MemoryVersion(**data["memory"])
        data["repair_sources"] = tuple(data["repair_sources"])
        request = PublishRequest(**data)
        try:
            applied = self.publication.publish(request)
        except StalePublication as error:
            return {"outcome": self._feedback(
                "stale", error.current,
                "Read refreshed layered Memory and reconsider the repair; nothing was published.",
            )}
        self._current_after(applied)
        return {"outcome": self._feedback(
            "applied", applied,
            "Layered repair published; this turn now reads the exact applied version.",
            applied_head=asdict(applied), source_reference=state["source_reference"],
        )}
