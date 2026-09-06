"""C: durable exact edits with public StateBackend; no model of its own."""
from dataclasses import asdict, replace
import re

from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemState
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict

from analysis_agent.consolidation_tools import PATHS, staged_texts
from analysis_agent.memory import MemoryVersion
from analysis_agent.publication import PublicationUncertain, PublishRequest, StalePublication
from sqlalchemy.exc import DBAPIError


class MemoryEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    old_text: str
    new_text: str


class RepairState(FilesystemState):
    operation_id: str
    base: dict
    source_reference: str
    edits: list[dict]
    index: int
    material: dict
    version: dict
    request: dict
    outcome: dict | None


class RepairWorkflow:
    def __init__(self, artifacts, publication, source):
        self.artifacts, self.publication, self.source = artifacts, publication, source
        if len({artifacts.document_id, publication.document_id, source.document_id}) != 1:
            raise ValueError("Repair components belong to different documents")
        builder = StateGraph(RepairState)
        for name in ("seed", "edit", "validate", "save", "prepare", "publish"):
            builder.add_node(name, getattr(self, "_" + name))
        builder.add_edge(START, "seed")
        builder.add_conditional_edges("seed", lambda s: END if s["outcome"] else "edit")
        builder.add_conditional_edges("edit", lambda s: END if s["outcome"] else
            ("edit" if s["index"] < len(s["edits"]) else "validate"))
        builder.add_conditional_edges("validate", lambda s: END if s["outcome"] else "save")
        builder.add_edge("save", "prepare")
        builder.add_edge("prepare", "publish")
        builder.add_edge("publish", END)
        # Per-invocation subgraph inherits A's Saver and durable pending work.
        self.graph = builder.compile()

    def _feedback(self, status, head, detail, **extra):
        return {"status": status, "head": asdict(head) if head else None,
            "guide": self.artifacts.guide(head.memory) if head else "",
            "detail": detail, "read_paths": list(PATHS.values()), **extra}

    def _seed(self, state):
        edits = state["edits"]
        if not 1 <= len(edits) <= 8 or sum(len(e["old_text"]) + len(e["new_text"]) for e in edits) > 12000:
            return {"outcome": {"status": "invalid_edit", "detail": "Use 1–8 edits, at most 12000 combined old/new characters", "read_paths": list(PATHS.values())}}
        for index, edit in enumerate(edits):
            if edit["path"] not in PATHS.values() or not edit["old_text"]:
                return {"outcome": {"status": "invalid_edit", "detail": f"Edit {index + 1}: only the two existing memory files and nonempty exact old_text are allowed", "read_paths": list(PATHS.values())}}
        head = self.publication.current()
        if not state["base"]:
            return {"outcome": self._feedback("no_memory", head, "No memory was loaded. Background extraction/consolidation initializes memory; C does not.")}
        if not head or asdict(head) != state["base"]:
            return {"outcome": self._feedback("stale", head, "Read the refreshed memory, then reconsider the edits. Do not just repeat them.")}
        self.source.read(state["source_reference"])
        StateBackend().upload_files([(path, self.artifacts.read_text(path, head.memory).encode()) for path in PATHS.values()])
        return {"index": 0, "outcome": None}

    def _edit(self, state):
        index = state["index"]
        edit = state["edits"][index]
        result = StateBackend().edit(edit["path"], edit["old_text"], edit["new_text"], replace_all=False)
        if result.error:
            return {"outcome": {"status": "invalid_edit", "detail": f"Edit {index + 1}: {result.error}", "read_paths": [edit["path"]]}}
        # Backend writes become visible at the next graph step, not guessed
        # read-your-writes behavior inside a loop over one node's snapshot.
        return {"index": index + 1}

    def _validate(self, state):
        try:
            material = staged_texts(self.artifacts)
            for reference in set(re.findall(r"conversation:[A-Za-z0-9_=-]+", "\n".join(material.values()))):
                self.source.read(reference)
        except ValueError as error:
            return {"outcome": {"status": "invalid_edit", "detail": str(error), "read_paths": list(PATHS.values())}}
        return {"material": material}

    def _save(self, state):
        return {"version": asdict(self.artifacts.save_memory(**state["material"]))}

    def _prepare(self, state):
        request = self.publication.prepare(MemoryVersion(**state["version"]),
            expected_revision=state["base"]["revision"], kind="repair",
            repair_sources=(state["source_reference"],))
        return {"request": asdict(replace(request, operation_id=state['operation_id']))}

    def reconcile(self, operation_id, source_reference, edits):
        """Receipt absence is unknown, not permission to run _publish on cancel."""
        try:
            receipt = self.publication.receipt(operation_id)
            if receipt is None:
                raise PublicationUncertain('Repair result is unknown; explicitly resume or reconcile later')
            if receipt.kind != 'repair' or receipt.repair_sources != (source_reference,):
                raise PublicationUncertain('Repair receipt does not match the saved source')
            current = self.publication.current()
            if current is None or current.revision < receipt.result.revision:
                raise PublicationUncertain('Current Memory head is not confirmed')
            return self._feedback('applied', current,
                'Edits were published; cancellation did not publish or revert Memory.',
                applied_head=asdict(receipt.result), changes=edits, source_reference=source_reference)
        except DBAPIError as error:
            raise PublicationUncertain('Repair reconciliation is unavailable') from error

    def _publish(self, state):
        data = dict(state["request"])
        data["memory"] = MemoryVersion(**data["memory"])
        data["repair_sources"] = tuple(data["repair_sources"])
        try:
            applied = self.publication.publish(PublishRequest(**data))
        except StalePublication as error:
            return {"outcome": self._feedback("stale", error.current, "Read refreshed memory and reconsider edits; nothing from this attempt was published.")}
        # Receipt reconciliation may happen after a later B publication. Never
        # regress A to a historical receipt; report both applied and read heads.
        current = self.publication.current()
        return {"outcome": self._feedback("applied", current,
            "Edits published. Subsequent reads use this head; initial guide remains historical.",
            applied_head=asdict(applied), changes=state["edits"],
            source_reference=state["source_reference"])}
