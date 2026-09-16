"""B1 case-layer staging and semantic tools; never publishes Memory.

The language model selects semantic case operations.  Runtime owns document
scope, the base publication, canonical source, stable identities, paths and
checkpoint state.  B2 and the outer background job consume the completed
stage later; this module cannot make staged cases current.
"""

from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from typing import Annotated, Any, Callable, Literal
from uuid import uuid4

from langchain.agents.middleware import AgentState
from langchain.tools import ToolRuntime, tool
from langchain_core.messages import AIMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from .bundle import CaseArtifact, Supersession
from .memory import MemoryArtifacts, MemoryVersion, _case_path, _prepare_text, _stable_id
from .patch import MemoryPatchError, apply_text_patch
from .references import controlled_references


STAGE_FORMAT_VERSION = 1
MAX_ROUTE_NOTE_CHARACTERS = 800
MAX_REPLACEMENTS = 8


class CaseMaintenanceError(ValueError):
    """A safe, model-correctable B1 staging error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class CaseChange:
    kind: Literal["create", "revise", "split", "merge", "retire", "route"]
    previous_case_ids: tuple[str, ...]
    current_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseMaintenanceStage:
    """JSON-safe checkpoint state for one B1 attempt on one fixed base."""

    format_version: int
    document_id: str
    base_publication_revision: int
    base_memory_version_id: str | None
    source_reference: str
    base_case_ids: tuple[str, ...]
    base_case_guide_digest: str
    case_guide: str
    read_case_ids: tuple[str, ...] = ()
    upserts: tuple[CaseArtifact, ...] = ()
    supersessions: tuple[Supersession, ...] = ()
    changes: tuple[CaseChange, ...] = ()
    completed: bool = False
    outcome: Literal["changed", "no_op"] | None = None

    @property
    def current_case_ids(self) -> tuple[str, ...]:
        retired = {item.retired_id for item in self.supersessions}
        current = (set(self.base_case_ids) - retired) | {item.case_id for item in self.upserts}
        return tuple(sorted(current))

    @property
    def changed(self) -> bool:
        guide_changed = sha256(self.case_guide.encode("utf-8")).hexdigest() != self.base_case_guide_digest
        return bool(self.upserts or self.supersessions or guide_changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "document_id": self.document_id,
            "base_publication_revision": self.base_publication_revision,
            "base_memory_version_id": self.base_memory_version_id,
            "source_reference": self.source_reference,
            "base_case_ids": list(self.base_case_ids),
            "base_case_guide_digest": self.base_case_guide_digest,
            "case_guide": self.case_guide,
            "read_case_ids": list(self.read_case_ids),
            "upserts": [{**asdict(item), "source_references": list(item.source_references)}
                        for item in self.upserts],
            "supersessions": [{**asdict(item), "current_ids": list(item.current_ids)}
                              for item in self.supersessions],
            "changes": [{**asdict(item), "previous_case_ids": list(item.previous_case_ids),
                         "current_case_ids": list(item.current_case_ids)} for item in self.changes],
            "completed": self.completed,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, value: object) -> "CaseMaintenanceStage":
        expected = {
            "format_version", "document_id", "base_publication_revision", "base_memory_version_id",
            "source_reference", "base_case_ids", "base_case_guide_digest", "case_guide",
            "upserts", "supersessions",
            "read_case_ids", "changes", "completed", "outcome",
        }
        try:
            if type(value) is not dict or set(value) != expected:
                raise TypeError("stage fields do not match the supported format")
            return cls(
                format_version=value["format_version"],
                document_id=value["document_id"],
                base_publication_revision=value["base_publication_revision"],
                base_memory_version_id=value["base_memory_version_id"],
                source_reference=value["source_reference"],
                base_case_ids=tuple(value["base_case_ids"]),
                base_case_guide_digest=value["base_case_guide_digest"],
                case_guide=value["case_guide"],
                read_case_ids=tuple(value["read_case_ids"]),
                upserts=tuple(CaseArtifact(
                    case_id=item["case_id"], content=item["content"],
                    source_references=tuple(item["source_references"]),
                ) for item in value["upserts"]),
                supersessions=tuple(Supersession(
                    kind=item["kind"], retired_id=item["retired_id"],
                    current_ids=tuple(item["current_ids"]),
                ) for item in value["supersessions"]),
                changes=tuple(CaseChange(
                    kind=item["kind"], previous_case_ids=tuple(item["previous_case_ids"]),
                    current_case_ids=tuple(item["current_case_ids"]),
                ) for item in value["changes"]),
                completed=value["completed"],
                outcome=value["outcome"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise CaseMaintenanceError("invalid_case_stage", "B1 staged state is invalid") from error


class CaseMaintenanceAgentState(AgentState):
    case_stage: dict[str, Any]


class ReplacementInput(BaseModel):
    """One complete current case produced by a split operation."""

    model_config = ConfigDict(extra="forbid")
    content: str = Field(description="Complete case prose; preserve concrete actions, conditions and exceptions")
    route_note: str = Field(description="One-line guide wording; do not provide IDs, paths or source references")


def _route_note(value: str) -> str:
    if type(value) is not str:
        raise CaseMaintenanceError("invalid_route", "Route note must be text")
    value = value.strip()
    if not value or len(value) > MAX_ROUTE_NOTE_CHARACTERS or "\n" in value or "\r" in value:
        raise CaseMaintenanceError(
            "invalid_route", f"Route note must be one nonempty line of at most {MAX_ROUTE_NOTE_CHARACTERS} characters")
    if controlled_references(value):
        raise CaseMaintenanceError("invalid_route", "Route note contains a Runtime-owned address")
    return value


def _route_line(case_id: str, note: str) -> str:
    return f"- [案例 {case_id}]({_case_path(case_id)}) — {note}"


def _route_indexes(guide: str, case_id: str) -> list[int]:
    path = _case_path(case_id)
    return [index for index, line in enumerate(guide.splitlines()) if path in controlled_references(line)]


def _replace_route(guide: str, case_id: str, note: str) -> str:
    note = _route_note(note)
    lines = guide.splitlines()
    indexes = _route_indexes(guide, case_id)
    if len(indexes) > 1:
        raise CaseMaintenanceError("ambiguous_case_route", "Case guide contains duplicate routes for this case")
    if indexes:
        references = controlled_references(lines[indexes[0]])
        if references != {_case_path(case_id)}:
            raise CaseMaintenanceError(
                "ambiguous_case_route", "Case route shares a line with another controlled address")
        lines[indexes[0]] = _route_line(case_id, note)
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(_route_line(case_id, note))
    return _prepare_text("\n".join(lines), guide=True)


def _remove_route(guide: str, case_id: str) -> str:
    lines = guide.splitlines()
    indexes = _route_indexes(guide, case_id)
    if len(indexes) != 1:
        raise CaseMaintenanceError(
            "ambiguous_case_route", "Current case must have exactly one independent guide route before supersession")
    references = controlled_references(lines[indexes[0]])
    if references != {_case_path(case_id)}:
        raise CaseMaintenanceError(
            "ambiguous_case_route", "Case route shares a line with another controlled address")
    del lines[indexes[0]]
    while lines and not lines[-1].strip():
        lines.pop()
    return _prepare_text("\n".join(lines), guide=True)


def _normalized_case(content: str) -> str:
    try:
        content = _prepare_text(content)
    except (TypeError, ValueError) as error:
        raise CaseMaintenanceError("invalid_case_content", str(error)) from error
    if not content.strip():
        raise CaseMaintenanceError("invalid_case_content", "Case content cannot be empty")
    return content


class CaseMaintenanceSession:
    """Runtime authority for one document's B1 checkpoint state."""

    def __init__(self, artifacts: MemoryArtifacts, *, id_factory: Callable[[], str] | None = None):
        self.artifacts = artifacts
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def open(self, *, base_publication_revision: int, base_version: MemoryVersion | None,
             source_reference: str) -> CaseMaintenanceStage:
        if type(base_publication_revision) is not int or base_publication_revision < 0:
            raise ValueError("Expected a non-negative base publication revision")
        if (base_publication_revision == 0) != (base_version is None):
            raise ValueError("A nonzero base revision requires its exact Memory bundle version")
        self.artifacts.validate_source(source_reference)
        if base_version is None:
            case_ids, guide = (), ""
        else:
            if base_version.document_id != self.artifacts.document_id:
                raise ValueError("Base Memory belongs to another document")
            manifest = self.artifacts.bundle_manifest(base_version)
            case_ids = tuple(sorted(item.case_id for item in manifest.cases))
            guide = self.artifacts.case_guide(base_version)
        stage = CaseMaintenanceStage(
            format_version=STAGE_FORMAT_VERSION,
            document_id=self.artifacts.document_id,
            base_publication_revision=base_publication_revision,
            base_memory_version_id=base_version.version_id if base_version is not None else None,
            source_reference=source_reference,
            base_case_ids=case_ids,
            base_case_guide_digest=sha256(guide.encode("utf-8")).hexdigest(),
            case_guide=guide,
        )
        self._validate(stage)
        return stage

    def load(self, value: object) -> CaseMaintenanceStage:
        stage = CaseMaintenanceStage.from_dict(value)
        self._validate(stage)
        return stage

    def _validate(self, stage: CaseMaintenanceStage) -> None:
        if (type(stage.format_version) is not int or stage.format_version != STAGE_FORMAT_VERSION
                or stage.document_id != self.artifacts.document_id
                or type(stage.base_publication_revision) is not int or stage.base_publication_revision < 0
                or type(stage.completed) is not bool
                or stage.outcome not in {None, "changed", "no_op"}):
            raise CaseMaintenanceError("invalid_case_stage", "B1 staged state is invalid")
        if (stage.base_publication_revision == 0) != (stage.base_memory_version_id is None):
            raise CaseMaintenanceError("invalid_case_stage", "B1 base revision and version do not match")
        self.artifacts.validate_source(stage.source_reference)
        base_ids: tuple[str, ...]
        base_guide: str
        if stage.base_memory_version_id is None:
            base_ids, base_guide = (), ""
        else:
            version = MemoryVersion(stage.document_id, stage.base_memory_version_id)
            manifest = self.artifacts.bundle_manifest(version)
            base_ids = tuple(sorted(item.case_id for item in manifest.cases))
            base_guide = self.artifacts.case_guide(version)
        if stage.base_case_ids != base_ids or len(set(base_ids)) != len(base_ids):
            raise CaseMaintenanceError("invalid_case_stage", "B1 base case identities changed")
        if (type(stage.base_case_guide_digest) is not str
                or stage.base_case_guide_digest != sha256(base_guide.encode("utf-8")).hexdigest()):
            raise CaseMaintenanceError("invalid_case_stage", "B1 base case guide changed")
        for case_id in stage.base_case_ids:
            _stable_id(case_id, field="case_id")
        upsert_ids: set[str] = set()
        for item in stage.upserts:
            _stable_id(item.case_id, field="case_id")
            if item.case_id in upsert_ids:
                raise CaseMaintenanceError("invalid_case_stage", "Duplicate staged case identity")
            upsert_ids.add(item.case_id)
            _normalized_case(item.content)
            if stage.source_reference not in item.source_references:
                raise CaseMaintenanceError("invalid_case_stage", "Changed case does not retain the current source")
            for reference in item.source_references:
                self.artifacts.validate_source(reference)
        retired: set[str] = set()
        for item in stage.supersessions:
            if item.kind != "case" or item.retired_id not in stage.base_case_ids or item.retired_id in retired:
                raise CaseMaintenanceError("invalid_case_stage", "Invalid staged case supersession")
            retired.add(item.retired_id)
        if retired & ({item.case_id for item in stage.upserts}):
            raise CaseMaintenanceError("invalid_case_stage", "A retired case remains staged as current")
        current = set(stage.current_case_ids)
        readable = set(stage.base_case_ids) | upsert_ids
        if len(set(stage.read_case_ids)) != len(stage.read_case_ids):
            raise CaseMaintenanceError("invalid_case_stage", "Duplicate B1 case read evidence")
        for case_id in stage.read_case_ids:
            _stable_id(case_id, field="read case_id")
            if case_id not in readable:
                raise CaseMaintenanceError("invalid_case_stage", "B1 read evidence points outside this attempt")
        for item in stage.supersessions:
            if any(current_id not in current for current_id in item.current_ids):
                raise CaseMaintenanceError("invalid_case_stage", "Case supersession points outside the staged current set")
        if stage.completed != (stage.outcome is not None):
            raise CaseMaintenanceError("invalid_case_stage", "B1 completion state is inconsistent")
        if bool(stage.changes) != stage.changed:
            raise CaseMaintenanceError("invalid_case_stage", "B1 change log does not match staged effects")
        allowed_change_kinds = {"create", "revise", "split", "merge", "retire", "route"}
        known_ids = set(stage.base_case_ids) | {item.case_id for item in stage.upserts}
        for item in stage.changes:
            if (item.kind not in allowed_change_kinds
                    or any(case_id not in known_ids for case_id in (*item.previous_case_ids,
                                                                     *item.current_case_ids))):
                raise CaseMaintenanceError("invalid_case_stage", "Invalid B1 case change record")
        if stage.outcome == "changed" and not stage.changed or stage.outcome == "no_op" and stage.changed:
            raise CaseMaintenanceError("invalid_case_stage", "B1 completion outcome does not match staged changes")

    def _open_stage(self, stage: CaseMaintenanceStage) -> None:
        self._validate(stage)
        if stage.completed:
            raise CaseMaintenanceError("case_stage_completed", "B1 staging is already complete")

    def _version(self, stage: CaseMaintenanceStage) -> MemoryVersion | None:
        return (MemoryVersion(stage.document_id, stage.base_memory_version_id)
                if stage.base_memory_version_id is not None else None)

    def read_case(self, stage: CaseMaintenanceStage, case_id: str) -> CaseArtifact:
        self._validate(stage)
        try:
            case_id = _stable_id(case_id, field="case_id")
        except ValueError as error:
            raise CaseMaintenanceError("invalid_case_id", "Case ID is invalid") from error
        if case_id not in stage.current_case_ids:
            raise CaseMaintenanceError("case_not_current", "Case is not current in this B1 stage")
        staged = next((item for item in stage.upserts if item.case_id == case_id), None)
        if staged is not None:
            return staged
        version = self._version(stage)
        if version is None:
            raise CaseMaintenanceError("case_not_current", "Case is not current in this B1 stage")
        read = self.artifacts.case(version, case_id)
        return CaseArtifact(read.case_id, read.content, read.source_references)

    def observe_case(self, stage: CaseMaintenanceStage, case_id: str
                     ) -> tuple[CaseMaintenanceStage, CaseArtifact]:
        """Read one current case and checkpoint proof that the Agent saw it."""
        self._open_stage(stage)
        item = self.read_case(stage, case_id)
        observed = replace(stage, read_case_ids=tuple(sorted({*stage.read_case_ids, item.case_id})))
        self._validate(observed)
        return observed, item

    def _require_observed(self, stage: CaseMaintenanceStage, case_id: str) -> str:
        try:
            case_id = _stable_id(case_id, field="case_id")
        except ValueError as error:
            raise CaseMaintenanceError("invalid_case_id", "Case ID is invalid") from error
        if case_id not in stage.current_case_ids:
            raise CaseMaintenanceError("case_not_current", "Case is not current in this B1 stage")
        if case_id not in stage.read_case_ids:
            raise CaseMaintenanceError(
                "case_read_required", "Read the current case before revising, splitting, merging or retiring it")
        return case_id

    def _new_id(self, stage: CaseMaintenanceStage, reserved: set[str] | None = None) -> str:
        try:
            case_id = _stable_id(self._id_factory(), field="case_id")
        except ValueError as error:
            raise RuntimeError("Runtime case ID generator returned an invalid identity") from error
        if case_id in set(stage.current_case_ids) | set(stage.base_case_ids) | (reserved or set()):
            raise RuntimeError("Runtime case ID generator returned a duplicate identity")
        return case_id

    @staticmethod
    def _with_upsert(stage: CaseMaintenanceStage, artifact: CaseArtifact) -> tuple[CaseArtifact, ...]:
        return tuple(sorted((*[item for item in stage.upserts if item.case_id != artifact.case_id], artifact),
                            key=lambda item: item.case_id))

    @staticmethod
    def _without_upserts(stage: CaseMaintenanceStage, case_ids: set[str]) -> tuple[CaseArtifact, ...]:
        return tuple(item for item in stage.upserts if item.case_id not in case_ids)

    @staticmethod
    def _change(stage: CaseMaintenanceStage,
                kind: Literal["create", "revise", "split", "merge", "retire", "route"],
                previous: tuple[str, ...],
                current: tuple[str, ...], **updates: Any) -> CaseMaintenanceStage:
        return replace(stage, changes=(*stage.changes, CaseChange(kind, previous, current)), **updates)

    def create_case(self, stage: CaseMaintenanceStage, *, content: str, route_note: str) -> CaseMaintenanceStage:
        self._open_stage(stage)
        case_id = self._new_id(stage)
        artifact = CaseArtifact(case_id, _normalized_case(content), (stage.source_reference,))
        guide = _replace_route(stage.case_guide, case_id, route_note)
        return self._change(stage, "create", (), (case_id,),
                            upserts=self._with_upsert(stage, artifact), case_guide=guide)

    def revise_case(self, stage: CaseMaintenanceStage, *, case_id: str, diff: str,
                    route_note: str | None) -> CaseMaintenanceStage:
        self._open_stage(stage)
        case_id = self._require_observed(stage, case_id)
        current = self.read_case(stage, case_id)
        try:
            content = apply_text_patch(current.content, diff, label=f"case {current.case_id}")
        except MemoryPatchError as error:
            raise CaseMaintenanceError("case_patch_failed", str(error)) from error
        content = _normalized_case(content)
        if content == current.content:
            raise CaseMaintenanceError("case_unchanged", "Case patch made no change; use no-op when nothing else changed")
        references = tuple(dict.fromkeys((*current.source_references, stage.source_reference)))
        artifact = CaseArtifact(current.case_id, content, references)
        guide = (stage.case_guide if route_note is None
                 else _replace_route(stage.case_guide, current.case_id, route_note))
        return self._change(stage, "revise", (current.case_id,), (current.case_id,),
                            upserts=self._with_upsert(stage, artifact), case_guide=guide)

    def split_case(self, stage: CaseMaintenanceStage, *, case_id: str,
                   replacements: list[ReplacementInput]) -> CaseMaintenanceStage:
        self._open_stage(stage)
        case_id = self._require_observed(stage, case_id)
        current = self.read_case(stage, case_id)
        if current.case_id not in stage.base_case_ids:
            raise CaseMaintenanceError("unstable_case_identity", "Revise a case created in this attempt instead of superseding it")
        if not 2 <= len(replacements) <= MAX_REPLACEMENTS:
            raise CaseMaintenanceError("invalid_split", f"Split requires 2 to {MAX_REPLACEMENTS} replacement cases")
        prepared = [(_normalized_case(item.content), _route_note(item.route_note)) for item in replacements]
        reserved: set[str] = set()
        new_ids: list[str] = []
        for _item in prepared:
            new_id = self._new_id(stage, reserved)
            reserved.add(new_id)
            new_ids.append(new_id)
        references = tuple(dict.fromkeys((*current.source_references, stage.source_reference)))
        upserts = list(self._without_upserts(stage, {current.case_id}))
        guide = _remove_route(stage.case_guide, current.case_id)
        for new_id, (content, note) in zip(new_ids, prepared, strict=True):
            upserts.append(CaseArtifact(new_id, content, references))
            guide = _replace_route(guide, new_id, note)
        supersessions = (*stage.supersessions, Supersession("case", current.case_id, tuple(new_ids)))
        return self._change(stage, "split", (current.case_id,), tuple(new_ids),
                            upserts=tuple(sorted(upserts, key=lambda item: item.case_id)),
                            supersessions=supersessions, case_guide=guide)

    def merge_cases(self, stage: CaseMaintenanceStage, *, case_ids: list[str], content: str,
                    route_note: str) -> CaseMaintenanceStage:
        self._open_stage(stage)
        if not 2 <= len(case_ids) <= MAX_REPLACEMENTS or len(set(case_ids)) != len(case_ids):
            raise CaseMaintenanceError("invalid_merge", f"Merge requires 2 to {MAX_REPLACEMENTS} distinct cases")
        case_ids = [self._require_observed(stage, case_id) for case_id in case_ids]
        current = [self.read_case(stage, case_id) for case_id in case_ids]
        if any(item.case_id not in stage.base_case_ids for item in current):
            raise CaseMaintenanceError("unstable_case_identity", "Revise cases created in this attempt instead of superseding them")
        new_id = self._new_id(stage)
        references = tuple(dict.fromkeys(reference for item in current
                                         for reference in (*item.source_references, stage.source_reference)))
        artifact = CaseArtifact(new_id, _normalized_case(content), references)
        retired = {item.case_id for item in current}
        guide = stage.case_guide
        for case_id in sorted(retired):
            guide = _remove_route(guide, case_id)
        guide = _replace_route(guide, new_id, route_note)
        supersessions = (*stage.supersessions,
                         *(Supersession("case", case_id, (new_id,)) for case_id in sorted(retired)))
        upserts = (*self._without_upserts(stage, retired), artifact)
        previous = tuple(sorted(retired))
        return self._change(stage, "merge", previous, (new_id,),
                            upserts=tuple(sorted(upserts, key=lambda item: item.case_id)),
                            supersessions=supersessions, case_guide=guide)

    def retire_case(self, stage: CaseMaintenanceStage, *, case_id: str) -> CaseMaintenanceStage:
        self._open_stage(stage)
        case_id = self._require_observed(stage, case_id)
        current = self.read_case(stage, case_id)
        if current.case_id not in stage.base_case_ids:
            raise CaseMaintenanceError("unstable_case_identity", "Revise a case created in this attempt instead of retiring it")
        guide = _remove_route(stage.case_guide, current.case_id)
        supersessions = (*stage.supersessions, Supersession("case", current.case_id, ()))
        return self._change(stage, "retire", (current.case_id,), (),
                            upserts=self._without_upserts(stage, {current.case_id}),
                            supersessions=supersessions, case_guide=guide)

    def set_case_route(self, stage: CaseMaintenanceStage, *, case_id: str,
                       route_note: str) -> CaseMaintenanceStage:
        self._open_stage(stage)
        current = self.read_case(stage, case_id)
        guide = _replace_route(stage.case_guide, current.case_id, route_note)
        if guide == stage.case_guide:
            raise CaseMaintenanceError("route_unchanged", "Case route did not change")
        return self._change(stage, "route", (current.case_id,), (current.case_id,), case_guide=guide)

    def finish(self, stage: CaseMaintenanceStage, *, outcome: Literal["changed", "no_op"]
               ) -> CaseMaintenanceStage:
        self._open_stage(stage)
        if (outcome == "changed") != stage.changed:
            raise CaseMaintenanceError(
                "incorrect_case_outcome", "Finish outcome must match whether this stage contains semantic changes")
        guide = _prepare_text(stage.case_guide, guide=True)
        expected = {_case_path(case_id) for case_id in stage.current_case_ids}
        actual = controlled_references(guide)
        if actual != expected or any(guide.count(path) != 1 for path in expected):
            raise CaseMaintenanceError(
                "incomplete_case_guide", "Case guide must contain exactly one Runtime-owned route for every current case")
        if expected and not guide.strip():
            raise CaseMaintenanceError("incomplete_case_guide", "Case guide cannot be empty while current cases exist")
        completed = replace(stage, case_guide=guide, completed=True, outcome=outcome)
        self._validate(completed)
        return completed

    def current_cases(self, stage: CaseMaintenanceStage) -> tuple[CaseArtifact, ...]:
        """Materialize the completed candidate case set for the later B2 slice."""
        self._validate(stage)
        if not stage.completed:
            raise CaseMaintenanceError("case_stage_incomplete", "B1 stage is not complete")
        return tuple(self.read_case(stage, case_id) for case_id in stage.current_case_ids)


def _payload(status: str, **values: Any) -> str:
    return json.dumps({"status": status, **values}, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"))


def _message(name: str, runtime: ToolRuntime, status: Literal["success", "error"],
             **values: Any) -> ToolMessage:
    if not runtime.tool_call_id:
        raise RuntimeError("B1 tool call identity is unavailable")
    return ToolMessage(_payload(status, **values), tool_call_id=runtime.tool_call_id,
                       name=name, status=status)


def _updated(name: str, runtime: ToolRuntime, stage: CaseMaintenanceStage, *,
             effect: str = "staged", **values: Any) -> Command:
    return Command(update={
        "messages": [_message(name, runtime, "success", effect=effect, **values)],
        "case_stage": stage.to_dict(),
    })


def case_maintenance_tools(session: CaseMaintenanceSession):
    """Build B1 tools whose model-visible schemas contain semantic inputs only."""

    def staged(runtime: ToolRuntime) -> CaseMaintenanceStage:
        messages = runtime.state.get("messages", ())
        current = messages[-1] if messages else None
        if (not isinstance(current, AIMessage) or current.invalid_tool_calls
                or len(current.tool_calls) != 1
                or current.tool_calls[0].get("id") != runtime.tool_call_id):
            raise CaseMaintenanceError(
                "multiple_case_tool_calls", "Use exactly one B1 case tool per model step")
        return session.load(runtime.state.get("case_stage"))

    def failure(name: str, runtime: ToolRuntime, error: CaseMaintenanceError) -> ToolMessage:
        return _message(name, runtime, "error", effect="unchanged", error=error.code,
                        next_action=str(error))

    @tool("read_case")
    def read_case(case_id: str, runtime: ToolRuntime) -> Command | ToolMessage:
        """Read one current case by an ID already shown by the Runtime guide; this has no staged effect."""
        try:
            updated, item = session.observe_case(staged(runtime), case_id)
            return _updated("read_case", runtime, updated, effect="unchanged",
                            case={"case_id": item.case_id, "content": item.content,
                                  "source_references": list(item.source_references)})
        except CaseMaintenanceError as error:
            return failure("read_case", runtime, error)

    @tool("create_case")
    def create_case(content: str, route_note: str, runtime: ToolRuntime) -> Command | ToolMessage:
        """Stage one genuinely new complete work case; Runtime assigns its ID and canonical source."""
        try:
            updated = session.create_case(staged(runtime), content=content, route_note=route_note)
            case_id = updated.changes[-1].current_case_ids[0]
            return _updated("create_case", runtime, updated, case_id=case_id)
        except CaseMaintenanceError as error:
            return failure("create_case", runtime, error)

    @tool("revise_case")
    def revise_case(case_id: str, diff: str, route_note: str | None,
                    runtime: ToolRuntime) -> Command | ToolMessage:
        """Patch one current case in place; send null route_note when its existing guide wording still applies."""
        try:
            updated = session.revise_case(staged(runtime), case_id=case_id, diff=diff,
                                          route_note=route_note)
            return _updated("revise_case", runtime, updated, case_id=case_id)
        except CaseMaintenanceError as error:
            return failure("revise_case", runtime, error)

    @tool("split_case")
    def split_case(case_id: str,
                   replacements: Annotated[list[ReplacementInput], Field(min_length=2, max_length=MAX_REPLACEMENTS)],
                   runtime: ToolRuntime) -> Command | ToolMessage:
        """Supersede one published case with two or more complete cases; Runtime assigns all replacement IDs."""
        try:
            updated = session.split_case(staged(runtime), case_id=case_id, replacements=replacements)
            return _updated("split_case", runtime, updated,
                            case_ids=list(updated.changes[-1].current_case_ids))
        except CaseMaintenanceError as error:
            return failure("split_case", runtime, error)

    @tool("merge_cases")
    def merge_cases(case_ids: Annotated[list[str], Field(min_length=2, max_length=MAX_REPLACEMENTS)],
                    content: str, route_note: str, runtime: ToolRuntime) -> Command | ToolMessage:
        """Supersede two or more published cases with one complete current case; Runtime assigns its ID."""
        try:
            updated = session.merge_cases(staged(runtime), case_ids=case_ids, content=content,
                                          route_note=route_note)
            return _updated("merge_cases", runtime, updated,
                            case_id=updated.changes[-1].current_case_ids[0])
        except CaseMaintenanceError as error:
            return failure("merge_cases", runtime, error)

    @tool("retire_case")
    def retire_case(case_id: str, runtime: ToolRuntime) -> Command | ToolMessage:
        """Remove one published case that current canonical evidence shows is invalid, duplicate or out of scope."""
        try:
            updated = session.retire_case(staged(runtime), case_id=case_id)
            return _updated("retire_case", runtime, updated, retired_case_id=case_id)
        except CaseMaintenanceError as error:
            return failure("retire_case", runtime, error)

    @tool("set_case_route")
    def set_case_route(case_id: str, route_note: str,
                       runtime: ToolRuntime) -> Command | ToolMessage:
        """Update only one current case's guide wording; Runtime keeps the ID and link target."""
        try:
            updated = session.set_case_route(staged(runtime), case_id=case_id, route_note=route_note)
            return _updated("set_case_route", runtime, updated, case_id=case_id)
        except CaseMaintenanceError as error:
            return failure("set_case_route", runtime, error)

    @tool("finish_case_maintenance")
    def finish_case_maintenance(outcome: Literal["changed", "no_op"],
                                runtime: ToolRuntime) -> Command | ToolMessage:
        """Finish B1 only after all case decisions and guide routes are complete; this does not publish Memory."""
        try:
            updated = session.finish(staged(runtime), outcome=outcome)
            return _updated("finish_case_maintenance", runtime, updated,
                            effect="stage_complete", outcome=outcome,
                            current_case_ids=list(updated.current_case_ids))
        except CaseMaintenanceError as error:
            return failure("finish_case_maintenance", runtime, error)

    return [read_case, create_case, revise_case, split_case, merge_cases,
            retire_case, set_case_route, finish_case_maintenance]
