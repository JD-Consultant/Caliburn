"""C: six native staged repair nodes; no model or publication owner of its own.

Ported from the verified analysis-only repair workflow. Caller owns operation
admission, the original saved request and any stopped-worker proof. This core
does not resume itself or infer that an absent receipt permits another write.
"""
from dataclasses import asdict, replace
from collections.abc import Callable

from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemState
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.runtime import Runtime
from pydantic import BaseModel, ConfigDict, ValidationError

from caliburn_memory.staging import PATHS, staged_texts, StagedMemoryValidationError
from caliburn_memory.patch import MAX_PATCH_CHARACTERS, MemoryPatchError, apply_staged_patch
from caliburn_memory.memory import MemoryVersion
from caliburn_memory.publication import PublicationUncertain, PublishRequest, StalePublication


class MemoryEdit(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    path: str
    diff: str


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


def build_repair_graph(resolve_workflow: Callable[[Runtime], "RepairWorkflow"]) -> CompiledStateGraph:
    """Compile the six native steps without resolving resources during inspection.

    Each executing node resolves its workflow from the native run Runtime. The
    App owns context/scope/admission checks; this core checks the returned type.
    The per-invocation graph inherits its parent's Saver. No resolver, live
    resource or side effect is needed to build or inspect the compiled graph.
    """
    if not callable(resolve_workflow):
        raise TypeError("repair_workflow_resolver_required")

    def step(name):
        def execute(state: RepairState, runtime: Runtime):
            workflow = resolve_workflow(runtime)
            if not isinstance(workflow, RepairWorkflow):
                raise TypeError("repair_workflow_unavailable")
            return getattr(workflow, "_" + name)(state)
        return execute

    builder = StateGraph(RepairState)
    for name in ("seed", "edit", "validate", "save", "prepare", "publish"):
        builder.add_node(name, step(name))
    builder.add_edge(START, "seed")
    builder.add_conditional_edges("seed", lambda s: END if s["outcome"] else "edit")
    builder.add_conditional_edges("edit", lambda s: END if s["outcome"] else
        ("edit" if s["index"] < len(s["edits"]) else "validate"))
    builder.add_conditional_edges("validate", lambda s: END if s["outcome"] else "save")
    builder.add_edge("save", "prepare")
    builder.add_edge("prepare", "publish")
    builder.add_edge("publish", END)
    return builder.compile()


class RepairWorkflow:
    def __init__(self, artifacts, publication, source):
        self.artifacts, self.publication, self.source = artifacts, publication, source
        if len({artifacts.document_id, publication.document_id, source.document_id}) != 1:
            raise ValueError("Repair components belong to different documents")
        self.graph = build_repair_graph(lambda runtime: self)

    def _feedback(self, status, head, detail, **extra):
        return {"status": status, "head": asdict(head) if head else None,
            "guide": self.artifacts.guide(head.memory) if head else "",
            "detail": detail, "read_paths": list(PATHS.values()), **extra}

    def _seed(self, state):
        edits = state["edits"]
        try:
            # A saved old tool payload is not silently reinterpreted as a patch.
            patches = [MemoryEdit.model_validate(e) for e in edits]
        except ValidationError:
            return {"outcome": {"status": "invalid_edit", "detail": "Each edit needs path and diff. Read current Memory and provide a V4A patch, not old_text/new_text.", "read_paths": list(PATHS.values())}}
        if not 1 <= len(patches) <= 8 or sum(len(e.diff) for e in patches) > MAX_PATCH_CHARACTERS:
            return {"outcome": {"status": "invalid_edit", "detail": "Use 1–8 patches, at most 12000 combined diff characters", "read_paths": list(PATHS.values())}}
        for index, edit in enumerate(patches):
            if edit.path not in PATHS.values() or not edit.diff.strip():
                return {"outcome": {"status": "invalid_edit", "detail": f"Edit {index + 1}: only the two existing memory files and nonempty diffs are allowed", "read_paths": list(PATHS.values())}}
        head = self.publication.current()
        if not state["base"]:
            if head is not None:
                return {"outcome": self._feedback("stale", head,
                    "Memory became available after this turn began. Read it, then reconsider the edits.")}
            return {"outcome": self._feedback("no_memory", head, "No memory was loaded. Background extraction/consolidation initializes memory; C does not.")}
        if not head or asdict(head) != state["base"]:
            return {"outcome": self._feedback("stale", head, "Read the refreshed memory, then reconsider the edits. Do not just repeat them.")}
        self.source.read(state["source_reference"])
        StateBackend().upload_files([(path, self.artifacts.read_text(path, head.memory).encode()) for path in PATHS.values()])
        return {"index": 0, "outcome": None}

    def _edit(self, state):
        index = state["index"]
        edit = state["edits"][index]
        try:
            apply_staged_patch(edit["path"], edit["diff"])
        except MemoryPatchError as error:
            return {"outcome": {"status": "invalid_edit", "detail": f"Edit {index + 1}: {error}", "read_paths": [edit["path"]]}}
        # Preserve the existing per-edit graph checkpoint/resume boundary.
        return {"index": index + 1}

    def _validate(self, state):
        try:
            material = staged_texts(self.artifacts)
        except StagedMemoryValidationError as error:
            return {"outcome": {"status": "invalid_edit", "detail": str(error), "read_paths": list(PATHS.values())}}
        return {"material": material}

    def _save(self, state):
        return {"version": asdict(self.artifacts.save_memory(**state["material"]))}

    def _prepare(self, state):
        request = self.publication.prepare(MemoryVersion(**state["version"]),
            expected_revision=state["base"]["revision"], kind="repair",
            repair_sources=(state["source_reference"],))
        return {"request": asdict(replace(request, operation_id=state['operation_id']))}

    def _current_after(self, applied):
        current = self.publication.current()
        if (current is None
                or applied.memory.document_id != self.artifacts.document_id
                or current.memory.document_id != self.artifacts.document_id
                or current.revision < applied.revision):
            raise PublicationUncertain("Current Memory head is not confirmed")
        return current

    def reconcile(self, request: PublishRequest):
        """Read back only the original native-saved request, never caller edits.

        The receipt proves this publication, not its original patch text. The
        App must use its saved tool binding for that text. No source body read,
        save, publish, graph resume or reconstructed candidate occurs here.
        """
        try:
            if (type(request) is not PublishRequest or request.kind != "repair"
                    or request.memory.document_id != self.artifacts.document_id
                    or request.processed_source is not None
                    or type(request.repair_sources) is not tuple or len(request.repair_sources) != 1):
                raise PublicationUncertain("Saved repair request is not confirmed")
            receipt = self.publication.receipt(request.operation_id)
            if receipt is None:
                raise PublicationUncertain("Repair result is unknown; retain the original request")
            if (receipt.operation_id != request.operation_id
                    or receipt.request_digest != request.digest()
                    or receipt.kind != "repair"
                    or receipt.repair_sources != request.repair_sources
                    or receipt.base_revision != request.expected_revision
                    or receipt.result.memory != request.memory
                    or receipt.result.revision != receipt.base_revision + 1):
                raise PublicationUncertain("Repair receipt does not match the saved request")
            self._current_after(receipt.result)
            return self._feedback('applied', receipt.result,
                'Edits were published; cancellation did not publish or revert Memory.',
                applied_head=asdict(receipt.result), source_reference=receipt.repair_sources[0])
        except PublicationUncertain:
            raise
        except Exception:
            raise PublicationUncertain("Repair reconciliation is unavailable") from None

    def _publish(self, state):
        data = dict(state["request"])
        data["memory"] = MemoryVersion(**data["memory"])
        data["repair_sources"] = tuple(data["repair_sources"])
        try:
            applied = self.publication.publish(PublishRequest(**data))
        except StalePublication as error:
            return {"outcome": self._feedback("stale", error.current, "Read refreshed memory and reconsider edits; nothing from this attempt was published.")}
        # A later B publication may already be current by the time this receipt
        # is returned. Confirm that publication did not regress or cross scope,
        # but keep this foreground turn on the exact version C produced.
        self._current_after(applied)
        return {"outcome": self._feedback("applied", applied,
            "Edits published. For this input, subsequent reads use the version this repair produced.",
            applied_head=asdict(applied), changes=state["edits"],
            source_reference=state["source_reference"])}
