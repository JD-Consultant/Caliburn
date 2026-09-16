"""Runtime-owned B2 staging over one completed B1 case candidate set.

This module does not publish Memory. It fixes one completed B1 stage and its
exact base bundle, then records checkpoint-safe work-understanding operations
for a later background-job/publication slice.
"""

from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from hashlib import sha256
import json
from typing import Annotated, Any, Callable, Literal
from uuid import uuid4

from langchain.agents import AgentState
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field

from .bundle import CaseArtifact, Supersession, WorkUnderstandingArtifact
from .case_maintenance import CaseMaintenanceSession, CaseMaintenanceStage
from .memory import (
    MemoryArtifacts, MemoryVersion, _prepare_text, _stable_id, _understanding_path,
)
from .patch import MemoryPatchError, apply_text_patch
from .references import controlled_references


STAGE_FORMAT_VERSION = 2
MAX_ROUTE_NOTE_CHARACTERS = 500
MAX_REPLACEMENTS = 8
MAX_REWORK_ISSUES = 8
MAX_REWORK_REASON_CHARACTERS = 2000


class UnderstandingMaintenanceError(ValueError):
    """A safe, model-correctable B2 staging error."""

    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class UnderstandingSupportSelection:
    understanding_id: str
    supporting_case_ids: tuple[str, ...]


@dataclass(frozen=True)
class UnderstandingChange:
    kind: Literal["create", "revise", "revalidate", "split", "merge", "retire", "route"]
    previous_understanding_ids: tuple[str, ...]
    current_understanding_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseReworkIssue:
    """One source-grounded reason the fixed B1 candidate cannot be trusted."""

    case_id: str
    source_reference: str
    reason: str


@dataclass(frozen=True)
class CaseSourceRead:
    """Durable proof that B2 inspected one source through one observed case."""

    case_id: str
    source_reference: str


class CaseReworkIssueInput(BaseModel):
    """Model-visible B2 feedback; Runtime still validates case/source ownership."""

    model_config = ConfigDict(extra="forbid")
    case_id: str = Field(description="Runtime-provided case ID whose current content is wrong")
    source_reference: str = Field(
        description="Exact canonical source reference returned by read_case and read_case_source",
    )
    reason: str = Field(
        min_length=1, max_length=MAX_REWORK_REASON_CHARACTERS,
        description="Material discrepancy that B1 must reassess from canonical source",
    )


class UnderstandingReplacementInput(BaseModel):
    """One complete current work understanding produced by a split."""

    model_config = ConfigDict(extra="forbid")
    content: str = Field(
        description="Complete stable work-understanding prose; preserve scope and exceptions",
    )
    supporting_case_ids: list[str] = Field(
        min_length=1, max_length=MAX_REPLACEMENTS,
        description="Current case IDs that actually support this understanding",
    )
    route_note: str = Field(
        description="One-line guide wording; do not provide IDs, paths or digests",
    )


@dataclass(frozen=True)
class UnderstandingMaintenanceStage:
    """JSON-safe checkpoint state for one B2 attempt on one fixed B1 result."""

    format_version: int
    document_id: str
    base_publication_revision: int
    base_memory_version_id: str | None
    case_stage: dict[str, Any]
    base_understanding_ids: tuple[str, ...]
    base_understanding_guide_digest: str
    understanding_guide: str
    required_case_ids: tuple[str, ...]
    required_understanding_ids: tuple[str, ...]
    read_case_ids: tuple[str, ...] = ()
    read_understanding_ids: tuple[str, ...] = ()
    read_source_references: tuple[CaseSourceRead, ...] = ()
    binding_updates: tuple[UnderstandingSupportSelection, ...] = ()
    upserts: tuple[WorkUnderstandingArtifact, ...] = ()
    supersessions: tuple[Supersession, ...] = ()
    changes: tuple[UnderstandingChange, ...] = ()
    case_rework_issues: tuple[CaseReworkIssue, ...] = ()
    completed: bool = False
    outcome: Literal["changed", "no_op", "case_rework_required"] | None = None

    @property
    def current_understanding_ids(self) -> tuple[str, ...]:
        retired = {item.retired_id for item in self.supersessions}
        current = ((set(self.base_understanding_ids) - retired)
                   | {item.understanding_id for item in self.upserts})
        return tuple(sorted(current))

    @property
    def changed(self) -> bool:
        guide_changed = (
            sha256(self.understanding_guide.encode("utf-8")).hexdigest()
            != self.base_understanding_guide_digest
        )
        return bool(self.upserts or self.supersessions or guide_changed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "format_version": self.format_version,
            "document_id": self.document_id,
            "base_publication_revision": self.base_publication_revision,
            "base_memory_version_id": self.base_memory_version_id,
            "case_stage": deepcopy(self.case_stage),
            "base_understanding_ids": list(self.base_understanding_ids),
            "base_understanding_guide_digest": self.base_understanding_guide_digest,
            "understanding_guide": self.understanding_guide,
            "required_case_ids": list(self.required_case_ids),
            "required_understanding_ids": list(self.required_understanding_ids),
            "read_case_ids": list(self.read_case_ids),
            "read_understanding_ids": list(self.read_understanding_ids),
            "read_source_references": [
                asdict(item) for item in self.read_source_references
            ],
            "binding_updates": [
                {**asdict(item), "supporting_case_ids": list(item.supporting_case_ids)}
                for item in self.binding_updates
            ],
            "upserts": [
                {**asdict(item), "supporting_case_ids": list(item.supporting_case_ids)}
                for item in self.upserts
            ],
            "supersessions": [
                {**asdict(item), "current_ids": list(item.current_ids)}
                for item in self.supersessions
            ],
            "changes": [
                {
                    **asdict(item),
                    "previous_understanding_ids": list(item.previous_understanding_ids),
                    "current_understanding_ids": list(item.current_understanding_ids),
                }
                for item in self.changes
            ],
            "case_rework_issues": [asdict(item) for item in self.case_rework_issues],
            "completed": self.completed,
            "outcome": self.outcome,
        }

    @classmethod
    def from_dict(cls, value: object) -> "UnderstandingMaintenanceStage":
        expected = {
            "format_version", "document_id", "base_publication_revision",
            "base_memory_version_id", "case_stage", "base_understanding_ids",
            "base_understanding_guide_digest", "understanding_guide",
            "required_case_ids", "required_understanding_ids", "read_case_ids",
            "read_understanding_ids", "read_source_references", "binding_updates",
            "upserts", "supersessions", "changes", "case_rework_issues",
            "completed", "outcome",
        }
        try:
            if type(value) is not dict or set(value) != expected:
                raise TypeError("stage fields do not match the supported format")
            return cls(
                format_version=value["format_version"],
                document_id=value["document_id"],
                base_publication_revision=value["base_publication_revision"],
                base_memory_version_id=value["base_memory_version_id"],
                case_stage=deepcopy(value["case_stage"]),
                base_understanding_ids=tuple(value["base_understanding_ids"]),
                base_understanding_guide_digest=value["base_understanding_guide_digest"],
                understanding_guide=value["understanding_guide"],
                required_case_ids=tuple(value["required_case_ids"]),
                required_understanding_ids=tuple(value["required_understanding_ids"]),
                read_case_ids=tuple(value["read_case_ids"]),
                read_understanding_ids=tuple(value["read_understanding_ids"]),
                read_source_references=tuple(CaseSourceRead(
                    case_id=item["case_id"],
                    source_reference=item["source_reference"],
                ) for item in value["read_source_references"]),
                binding_updates=tuple(UnderstandingSupportSelection(
                    understanding_id=item["understanding_id"],
                    supporting_case_ids=tuple(item["supporting_case_ids"]),
                ) for item in value["binding_updates"]),
                upserts=tuple(WorkUnderstandingArtifact(
                    understanding_id=item["understanding_id"],
                    content=item["content"],
                    supporting_case_ids=tuple(item["supporting_case_ids"]),
                ) for item in value["upserts"]),
                supersessions=tuple(Supersession(
                    kind=item["kind"], retired_id=item["retired_id"],
                    current_ids=tuple(item["current_ids"]),
                ) for item in value["supersessions"]),
                changes=tuple(UnderstandingChange(
                    kind=item["kind"],
                    previous_understanding_ids=tuple(item["previous_understanding_ids"]),
                    current_understanding_ids=tuple(item["current_understanding_ids"]),
                ) for item in value["changes"]),
                case_rework_issues=tuple(CaseReworkIssue(
                    case_id=item["case_id"],
                    source_reference=item["source_reference"],
                    reason=item["reason"],
                ) for item in value["case_rework_issues"]),
                completed=value["completed"],
                outcome=value["outcome"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 staged state is invalid",
            ) from error


class UnderstandingMaintenanceAgentState(AgentState):
    understanding_stage: dict[str, Any]


class UnderstandingMaintenanceSession:
    """Runtime authority for one document's B2 checkpoint state."""

    def __init__(self, artifacts: MemoryArtifacts, case_session: CaseMaintenanceSession,
                 *, id_factory: Callable[[], str] | None = None):
        if artifacts.document_id != case_session.artifacts.document_id:
            raise ValueError("B1 and B2 components belong to different documents")
        self.artifacts = artifacts
        self.case_session = case_session
        self._id_factory = id_factory or (lambda: str(uuid4()))

    def open(self, case_stage: CaseMaintenanceStage) -> UnderstandingMaintenanceStage:
        case_stage = self.case_session.load(case_stage.to_dict())
        if not case_stage.completed:
            raise UnderstandingMaintenanceError(
                "case_stage_incomplete", "B1 must be complete before B2 staging starts",
            )
        version = self._version(case_stage)
        if version is None:
            understanding_ids, guide = (), ""
        else:
            manifest = self.artifacts.bundle_manifest(version)
            understanding_ids = tuple(sorted(
                item.understanding_id for item in manifest.understandings
            ))
            guide = self.artifacts.understanding_guide(version)
        required_cases, required_understandings = self._impact(case_stage)
        stage = UnderstandingMaintenanceStage(
            format_version=STAGE_FORMAT_VERSION,
            document_id=self.artifacts.document_id,
            base_publication_revision=case_stage.base_publication_revision,
            base_memory_version_id=case_stage.base_memory_version_id,
            case_stage=case_stage.to_dict(),
            base_understanding_ids=understanding_ids,
            base_understanding_guide_digest=sha256(guide.encode("utf-8")).hexdigest(),
            understanding_guide=guide,
            required_case_ids=required_cases,
            required_understanding_ids=required_understandings,
        )
        self._validate(stage)
        return stage

    def load(self, value: object) -> UnderstandingMaintenanceStage:
        stage = UnderstandingMaintenanceStage.from_dict(value)
        self._validate(stage)
        return stage

    @staticmethod
    def _version(case_stage: CaseMaintenanceStage) -> MemoryVersion | None:
        return (MemoryVersion(case_stage.document_id, case_stage.base_memory_version_id)
                if case_stage.base_memory_version_id is not None else None)

    def _impact(self, case_stage: CaseMaintenanceStage) -> tuple[tuple[str, ...], tuple[str, ...]]:
        semantic_changes = [item for item in case_stage.changes if item.kind != "route"]
        previous_or_current = {
            case_id
            for change in semantic_changes
            for case_id in (*change.previous_case_ids, *change.current_case_ids)
        }
        current_ids = set(case_stage.current_case_ids)
        required_cases = tuple(sorted(previous_or_current & current_ids))
        version = self._version(case_stage)
        if version is None or not previous_or_current:
            return required_cases, ()
        manifest = self.artifacts.bundle_manifest(version)
        required_understandings = tuple(sorted({
            item.understanding_id
            for item in manifest.understanding_case_bindings
            if item.case_id in previous_or_current
        }))
        return required_cases, required_understandings

    def _validate(self, stage: UnderstandingMaintenanceStage) -> None:
        if (type(stage.format_version) is not int
                or stage.format_version != STAGE_FORMAT_VERSION
                or stage.document_id != self.artifacts.document_id
                or type(stage.base_publication_revision) is not int
                or stage.base_publication_revision < 0
                or type(stage.completed) is not bool
                or stage.outcome not in {
                    None, "changed", "no_op", "case_rework_required",
                }):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 staged state is invalid",
            )
        try:
            case_stage = self.case_session.load(stage.case_stage)
        except (TypeError, ValueError) as error:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 staged B1 input is invalid",
            ) from error
        if not case_stage.completed:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 staged B1 input is not complete",
            )
        if (stage.base_publication_revision != case_stage.base_publication_revision
                or stage.base_memory_version_id != case_stage.base_memory_version_id):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 base changed after the B1 result was fixed",
            )
        version = self._version(case_stage)
        if version is None:
            base_ids, guide = (), ""
        else:
            manifest = self.artifacts.bundle_manifest(version)
            base_ids = tuple(sorted(item.understanding_id for item in manifest.understandings))
            guide = self.artifacts.understanding_guide(version)
        if (stage.base_understanding_ids != base_ids
                or stage.base_understanding_guide_digest
                != sha256(guide.encode("utf-8")).hexdigest()):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 base understanding set or guide changed",
            )
        required_cases, required_understandings = self._impact(case_stage)
        if (stage.required_case_ids != required_cases
                or stage.required_understanding_ids != required_understandings):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_impact", "B2 impact set changed after the attempt opened",
            )
        for identity in (*stage.base_understanding_ids, *stage.required_case_ids,
                         *stage.required_understanding_ids):
            try:
                _stable_id(identity, field="B2 identity")
            except ValueError as error:
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 staged identity is invalid",
                ) from error
        case_stage_ids = set(case_stage.base_case_ids) | set(case_stage.current_case_ids)
        if (len(set(stage.read_case_ids)) != len(stage.read_case_ids)
                or any(case_id not in case_stage_ids for case_id in stage.read_case_ids)):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 case read evidence is invalid",
            )
        seen_source_reads: set[tuple[str, str]] = set()
        for source_read in stage.read_source_references:
            key = (source_read.case_id, source_read.source_reference)
            if (key in seen_source_reads
                    or source_read.case_id not in stage.read_case_ids
                    or type(source_read.source_reference) is not str
                    or source_read.source_reference not in self._read_case_from_fixed_stage(
                        stage, source_read.case_id,
                    ).source_references):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 source read evidence is invalid",
                )
            seen_source_reads.add(key)
        known_understanding_ids = (
            set(stage.base_understanding_ids)
            | {item.understanding_id for item in stage.upserts}
        )
        if (len(set(stage.read_understanding_ids)) != len(stage.read_understanding_ids)
                or any(item not in known_understanding_ids
                       for item in stage.read_understanding_ids)):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 understanding read evidence is invalid",
            )
        current_case_ids = set(case_stage.current_case_ids)
        upsert_ids: set[str] = set()
        for item in stage.upserts:
            try:
                _stable_id(item.understanding_id, field="understanding_id")
                _normalized_understanding(item.content)
            except (ValueError, UnderstandingMaintenanceError) as error:
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 staged understanding is invalid",
                ) from error
            if item.understanding_id in upsert_ids:
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "Duplicate staged work-understanding identity",
                )
            upsert_ids.add(item.understanding_id)
            if (not item.supporting_case_ids
                    or len(set(item.supporting_case_ids)) != len(item.supporting_case_ids)
                    or any(case_id not in current_case_ids
                           or case_id not in stage.read_case_ids
                           for case_id in item.supporting_case_ids)):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 staged support selection is invalid",
                )
        retired: set[str] = set()
        for item in stage.supersessions:
            if (item.kind != "understanding"
                    or item.retired_id not in stage.base_understanding_ids
                    or item.retired_id in retired):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "Invalid staged understanding supersession",
                )
            retired.add(item.retired_id)
        if retired & upsert_ids:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "A retired understanding remains current",
            )
        current_understanding_ids = set(stage.current_understanding_ids)
        for item in stage.supersessions:
            if any(current_id not in current_understanding_ids for current_id in item.current_ids):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "Understanding supersession target is not current",
                )
        binding_ids: set[str] = set()
        for item in stage.binding_updates:
            if (item.understanding_id in binding_ids
                    or item.understanding_id not in current_understanding_ids
                    or not item.supporting_case_ids
                    or len(set(item.supporting_case_ids)) != len(item.supporting_case_ids)
                    or any(case_id not in current_case_ids
                           or case_id not in stage.read_case_ids
                           for case_id in item.supporting_case_ids)):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 binding refresh is invalid",
                )
            binding_ids.add(item.understanding_id)
        allowed_change_kinds = {
            "create", "revise", "revalidate", "split", "merge", "retire", "route",
        }
        for item in stage.changes:
            if (item.kind not in allowed_change_kinds
                    or any(identity not in known_understanding_ids
                           for identity in (*item.previous_understanding_ids,
                                            *item.current_understanding_ids))):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 change record is invalid",
                )
        seen_rework: set[tuple[str, str]] = set()
        if len(stage.case_rework_issues) > MAX_REWORK_ISSUES:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 case rework issue set is invalid",
            )
        for issue in stage.case_rework_issues:
            key = (issue.case_id, issue.source_reference)
            if (key in seen_rework
                    or issue.case_id not in stage.read_case_ids
                    or CaseSourceRead(issue.case_id, issue.source_reference)
                    not in stage.read_source_references
                    or issue.source_reference
                    not in self._read_case_from_fixed_stage(stage, issue.case_id).source_references
                    or _rework_reason(issue.reason) != issue.reason):
                raise UnderstandingMaintenanceError(
                    "invalid_understanding_stage", "B2 case rework issue is invalid",
                )
            seen_rework.add(key)
        if stage.completed != (stage.outcome is not None):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 completion state is inconsistent",
            )
        if (stage.outcome == "changed" and not stage.changed
                or stage.outcome == "no_op" and stage.changed
                or (stage.outcome == "case_rework_required")
                != bool(stage.case_rework_issues)):
            raise UnderstandingMaintenanceError(
                "invalid_understanding_stage", "B2 outcome does not match staged changes",
            )

    def _case_stage(self, stage: UnderstandingMaintenanceStage) -> CaseMaintenanceStage:
        return self.case_session.load(stage.case_stage)

    def _open_stage(self, stage: UnderstandingMaintenanceStage) -> None:
        self._validate(stage)
        if stage.completed:
            raise UnderstandingMaintenanceError(
                "understanding_stage_completed", "B2 staging is already complete",
            )

    def _read_case_from_fixed_stage(self, stage: UnderstandingMaintenanceStage,
                                    case_id: str) -> CaseArtifact:
        case_stage = self._case_stage(stage)
        if case_id in case_stage.current_case_ids:
            return self.case_session.read_case(case_stage, case_id)
        if case_id in case_stage.base_case_ids:
            version = self._version(case_stage)
            if version is not None:
                item = self.artifacts.case(version, case_id)
                return CaseArtifact(item.case_id, item.content, item.source_references)
        raise UnderstandingMaintenanceError(
            "case_not_available", "Case is outside this B2 candidate and its exact base",
        )

    def read_case(self, stage: UnderstandingMaintenanceStage, case_id: str) -> CaseArtifact:
        self._validate(stage)
        try:
            case_id = _stable_id(case_id, field="case_id")
        except ValueError as error:
            raise UnderstandingMaintenanceError("invalid_case_id", "Case ID is invalid") from error
        return self._read_case_from_fixed_stage(stage, case_id)

    def observe_case(self, stage: UnderstandingMaintenanceStage, case_id: str
                     ) -> tuple[UnderstandingMaintenanceStage, CaseArtifact]:
        self._open_stage(stage)
        item = self.read_case(stage, case_id)
        observed = replace(stage, read_case_ids=tuple(sorted({*stage.read_case_ids, item.case_id})))
        self._validate(observed)
        return observed, item

    def observe_source_reference(self, stage: UnderstandingMaintenanceStage, *,
                                 case_id: str, source_reference: str
                                 ) -> UnderstandingMaintenanceStage:
        """Checkpoint proof that B2 read one exact source exposed by an observed case."""
        self._open_stage(stage)
        try:
            case_id = _stable_id(case_id, field="case_id")
        except ValueError as error:
            raise UnderstandingMaintenanceError("invalid_case_id", "Case ID is invalid") from error
        if case_id not in stage.read_case_ids:
            raise UnderstandingMaintenanceError(
                "case_read_required", "Read the case before reading its canonical source",
            )
        item = self.read_case(stage, case_id)
        if source_reference not in item.source_references:
            raise UnderstandingMaintenanceError(
                "source_not_owned_by_case",
                "Canonical source reference does not belong to the observed case",
            )
        self.artifacts.validate_source(source_reference)
        evidence = CaseSourceRead(case_id, source_reference)
        observed = replace(stage, read_source_references=tuple(sorted(
            {*stage.read_source_references, evidence},
            key=lambda item: (item.case_id, item.source_reference),
        )))
        self._validate(observed)
        return observed

    def read_understanding(self, stage: UnderstandingMaintenanceStage,
                           understanding_id: str) -> WorkUnderstandingArtifact:
        self._validate(stage)
        try:
            understanding_id = _stable_id(understanding_id, field="understanding_id")
        except ValueError as error:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_id", "Work-understanding ID is invalid",
            ) from error
        if understanding_id not in stage.current_understanding_ids:
            raise UnderstandingMaintenanceError(
                "understanding_not_current", "Work understanding is not current in this B2 stage",
            )
        staged = next(
            (item for item in stage.upserts if item.understanding_id == understanding_id), None,
        )
        if staged is not None:
            return staged
        case_stage = self._case_stage(stage)
        version = self._version(case_stage)
        if version is None:
            raise UnderstandingMaintenanceError(
                "understanding_not_current", "Work understanding is not current in this B2 stage",
            )
        read = self.artifacts.understanding(version, understanding_id)
        update = next(
            (item for item in stage.binding_updates
             if item.understanding_id == understanding_id), None,
        )
        supporting = (update.supporting_case_ids if update is not None else tuple(
            item.case_id for item in read.case_bindings
        ))
        return WorkUnderstandingArtifact(read.understanding_id, read.content, supporting)

    def observe_understanding(self, stage: UnderstandingMaintenanceStage,
                              understanding_id: str
                              ) -> tuple[UnderstandingMaintenanceStage,
                                         WorkUnderstandingArtifact]:
        self._open_stage(stage)
        item = self.read_understanding(stage, understanding_id)
        observed = replace(
            stage,
            read_understanding_ids=tuple(sorted({
                *stage.read_understanding_ids, item.understanding_id,
            })),
        )
        self._validate(observed)
        return observed, item

    @staticmethod
    def _with_upsert(stage: UnderstandingMaintenanceStage,
                     artifact: WorkUnderstandingArtifact
                     ) -> tuple[WorkUnderstandingArtifact, ...]:
        return tuple(sorted((
            *[item for item in stage.upserts
              if item.understanding_id != artifact.understanding_id],
            artifact,
        ), key=lambda item: item.understanding_id))

    @staticmethod
    def _with_binding(stage: UnderstandingMaintenanceStage,
                      selection: UnderstandingSupportSelection
                      ) -> tuple[UnderstandingSupportSelection, ...]:
        return tuple(sorted((
            *[item for item in stage.binding_updates
              if item.understanding_id != selection.understanding_id],
            selection,
        ), key=lambda item: item.understanding_id))

    @staticmethod
    def _without_upserts(stage: UnderstandingMaintenanceStage,
                         understanding_ids: set[str]
                         ) -> tuple[WorkUnderstandingArtifact, ...]:
        return tuple(
            item for item in stage.upserts
            if item.understanding_id not in understanding_ids
        )

    @staticmethod
    def _without_bindings(stage: UnderstandingMaintenanceStage,
                          understanding_ids: set[str]
                          ) -> tuple[UnderstandingSupportSelection, ...]:
        return tuple(
            item for item in stage.binding_updates
            if item.understanding_id not in understanding_ids
        )

    @staticmethod
    def _change(stage: UnderstandingMaintenanceStage,
                kind: Literal["create", "revise", "revalidate", "split", "merge",
                              "retire", "route"],
                previous: tuple[str, ...], current: tuple[str, ...],
                **updates: Any) -> UnderstandingMaintenanceStage:
        return replace(
            stage,
            changes=(*stage.changes, UnderstandingChange(kind, previous, current)),
            **updates,
        )

    def _new_id(self, stage: UnderstandingMaintenanceStage,
                reserved: set[str] | None = None) -> str:
        try:
            understanding_id = _stable_id(
                self._id_factory(), field="understanding_id",
            )
        except ValueError as error:
            raise RuntimeError(
                "Runtime work-understanding ID generator returned an invalid identity",
            ) from error
        known = set(stage.current_understanding_ids) | set(stage.base_understanding_ids)
        if understanding_id in known | (reserved or set()):
            raise RuntimeError(
                "Runtime work-understanding ID generator returned a duplicate identity",
            )
        return understanding_id

    def _supporting_cases(self, stage: UnderstandingMaintenanceStage,
                          case_ids: list[str]) -> tuple[str, ...]:
        if type(case_ids) is not list or not case_ids or len(case_ids) != len(set(case_ids)):
            raise UnderstandingMaintenanceError(
                "invalid_supporting_cases",
                "Choose one or more distinct current supporting cases",
            )
        case_stage = self._case_stage(stage)
        current = set(case_stage.current_case_ids)
        result: list[str] = []
        for value in case_ids:
            try:
                case_id = _stable_id(value, field="supporting_case_id")
            except ValueError as error:
                raise UnderstandingMaintenanceError(
                    "invalid_supporting_cases", "Supporting case ID is invalid",
                ) from error
            if case_id not in current:
                raise UnderstandingMaintenanceError(
                    "case_not_current", "A supporting case is not current in the B1 candidate",
                )
            if case_id not in stage.read_case_ids:
                raise UnderstandingMaintenanceError(
                    "case_read_required", "Read every supporting case before selecting it",
                )
            result.append(case_id)
        return tuple(sorted(result))

    def _require_observed_understanding(self, stage: UnderstandingMaintenanceStage,
                                        understanding_id: str) -> str:
        try:
            understanding_id = _stable_id(understanding_id, field="understanding_id")
        except ValueError as error:
            raise UnderstandingMaintenanceError(
                "invalid_understanding_id", "Work-understanding ID is invalid",
            ) from error
        if understanding_id not in stage.current_understanding_ids:
            raise UnderstandingMaintenanceError(
                "understanding_not_current", "Work understanding is not current in this B2 stage",
            )
        if understanding_id not in stage.read_understanding_ids:
            raise UnderstandingMaintenanceError(
                "understanding_read_required",
                "Read the current work understanding before revising or revalidating it",
            )
        return understanding_id

    def create_understanding(self, stage: UnderstandingMaintenanceStage, *, content: str,
                             supporting_case_ids: list[str], route_note: str
                             ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        supporting = self._supporting_cases(stage, supporting_case_ids)
        understanding_id = self._new_id(stage)
        artifact = WorkUnderstandingArtifact(
            understanding_id, _normalized_understanding(content), supporting,
        )
        guide = _replace_route(stage.understanding_guide, understanding_id, route_note)
        changed = self._change(
            stage, "create", (), (understanding_id,),
            upserts=self._with_upsert(stage, artifact), understanding_guide=guide,
        )
        self._validate(changed)
        return changed

    def revise_understanding(self, stage: UnderstandingMaintenanceStage, *,
                             understanding_id: str, diff: str,
                             supporting_case_ids: list[str], route_note: str | None
                             ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        understanding_id = self._require_observed_understanding(stage, understanding_id)
        current = self.read_understanding(stage, understanding_id)
        supporting = self._supporting_cases(stage, supporting_case_ids)
        try:
            content = apply_text_patch(
                current.content, diff, label=f"work understanding {current.understanding_id}",
            )
        except MemoryPatchError as error:
            raise UnderstandingMaintenanceError("understanding_patch_failed", str(error)) from error
        content = _normalized_understanding(content)
        if content == current.content:
            raise UnderstandingMaintenanceError(
                "understanding_unchanged",
                "Work-understanding patch made no change; revalidate bindings instead",
            )
        artifact = WorkUnderstandingArtifact(current.understanding_id, content, supporting)
        guide = (stage.understanding_guide if route_note is None else
                 _replace_route(stage.understanding_guide, understanding_id, route_note))
        changed = self._change(
            stage, "revise", (understanding_id,), (understanding_id,),
            upserts=self._with_upsert(stage, artifact),
            binding_updates=self._without_bindings(stage, {understanding_id}),
            understanding_guide=guide,
        )
        self._validate(changed)
        return changed

    def split_understanding(self, stage: UnderstandingMaintenanceStage, *,
                            understanding_id: str,
                            replacements: list[UnderstandingReplacementInput]
                            ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        understanding_id = self._require_observed_understanding(stage, understanding_id)
        if understanding_id not in stage.base_understanding_ids:
            raise UnderstandingMaintenanceError(
                "unstable_understanding_identity",
                "Revise an understanding created in this attempt instead of superseding it",
            )
        if not 2 <= len(replacements) <= MAX_REPLACEMENTS:
            raise UnderstandingMaintenanceError(
                "invalid_split", f"Split requires 2 to {MAX_REPLACEMENTS} replacements",
            )
        prepared = [
            (
                _normalized_understanding(item.content),
                self._supporting_cases(stage, item.supporting_case_ids),
                _route_note(item.route_note),
            )
            for item in replacements
        ]
        reserved: set[str] = set()
        new_ids: list[str] = []
        for _item in prepared:
            new_id = self._new_id(stage, reserved)
            reserved.add(new_id)
            new_ids.append(new_id)
        guide = _remove_route(stage.understanding_guide, understanding_id)
        upserts = list(self._without_upserts(stage, {understanding_id}))
        for new_id, (content, supporting, note) in zip(new_ids, prepared, strict=True):
            upserts.append(WorkUnderstandingArtifact(new_id, content, supporting))
            guide = _replace_route(guide, new_id, note)
        supersessions = (
            *stage.supersessions,
            Supersession("understanding", understanding_id, tuple(new_ids)),
        )
        changed = self._change(
            stage, "split", (understanding_id,), tuple(new_ids),
            upserts=tuple(sorted(upserts, key=lambda item: item.understanding_id)),
            binding_updates=self._without_bindings(stage, {understanding_id}),
            supersessions=supersessions,
            understanding_guide=guide,
        )
        self._validate(changed)
        return changed

    def merge_understandings(self, stage: UnderstandingMaintenanceStage, *,
                             understanding_ids: list[str], content: str,
                             supporting_case_ids: list[str], route_note: str
                             ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        if (not 2 <= len(understanding_ids) <= MAX_REPLACEMENTS
                or len(set(understanding_ids)) != len(understanding_ids)):
            raise UnderstandingMaintenanceError(
                "invalid_merge",
                f"Merge requires 2 to {MAX_REPLACEMENTS} distinct understandings",
            )
        understanding_ids = [
            self._require_observed_understanding(stage, item)
            for item in understanding_ids
        ]
        if any(item not in stage.base_understanding_ids for item in understanding_ids):
            raise UnderstandingMaintenanceError(
                "unstable_understanding_identity",
                "Revise understandings created in this attempt instead of superseding them",
            )
        supporting = self._supporting_cases(stage, supporting_case_ids)
        new_id = self._new_id(stage)
        retired = set(understanding_ids)
        artifact = WorkUnderstandingArtifact(
            new_id, _normalized_understanding(content), supporting,
        )
        guide = stage.understanding_guide
        for understanding_id in sorted(retired):
            guide = _remove_route(guide, understanding_id)
        guide = _replace_route(guide, new_id, route_note)
        supersessions = (
            *stage.supersessions,
            *(Supersession("understanding", item, (new_id,)) for item in sorted(retired)),
        )
        upserts = (*self._without_upserts(stage, retired), artifact)
        previous = tuple(sorted(retired))
        changed = self._change(
            stage, "merge", previous, (new_id,),
            upserts=tuple(sorted(upserts, key=lambda item: item.understanding_id)),
            binding_updates=self._without_bindings(stage, retired),
            supersessions=supersessions,
            understanding_guide=guide,
        )
        self._validate(changed)
        return changed

    def retire_understanding(self, stage: UnderstandingMaintenanceStage, *,
                             understanding_id: str) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        understanding_id = self._require_observed_understanding(stage, understanding_id)
        if understanding_id not in stage.base_understanding_ids:
            raise UnderstandingMaintenanceError(
                "unstable_understanding_identity",
                "Revise an understanding created in this attempt instead of retiring it",
            )
        guide = _remove_route(stage.understanding_guide, understanding_id)
        supersessions = (
            *stage.supersessions,
            Supersession("understanding", understanding_id, ()),
        )
        changed = self._change(
            stage, "retire", (understanding_id,), (),
            upserts=self._without_upserts(stage, {understanding_id}),
            binding_updates=self._without_bindings(stage, {understanding_id}),
            supersessions=supersessions,
            understanding_guide=guide,
        )
        self._validate(changed)
        return changed

    def set_understanding_route(self, stage: UnderstandingMaintenanceStage, *,
                                understanding_id: str, route_note: str
                                ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        understanding_id = self._require_observed_understanding(stage, understanding_id)
        current = self.read_understanding(stage, understanding_id)
        guide = _replace_route(
            stage.understanding_guide, current.understanding_id, route_note,
        )
        if guide == stage.understanding_guide:
            raise UnderstandingMaintenanceError(
                "route_unchanged", "Understanding route did not change",
            )
        changed = self._change(
            stage, "route", (current.understanding_id,), (current.understanding_id,),
            understanding_guide=guide,
        )
        self._validate(changed)
        return changed

    def finish(self, stage: UnderstandingMaintenanceStage, *,
               outcome: Literal["changed", "no_op"]
               ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        missing_cases = set(stage.required_case_ids) - set(stage.read_case_ids)
        if missing_cases:
            raise UnderstandingMaintenanceError(
                "required_cases_unread", "Read all changed B1 cases before completing B2",
            )
        handled = {
            understanding_id
            for item in stage.changes if item.kind != "route"
            for understanding_id in item.previous_understanding_ids
        }
        missing_understandings = set(stage.required_understanding_ids) - handled
        if missing_understandings:
            raise UnderstandingMaintenanceError(
                "required_understandings_unhandled",
                "Handle all directly affected work understandings before completing B2",
            )
        if (outcome == "changed") != stage.changed:
            raise UnderstandingMaintenanceError(
                "incorrect_understanding_outcome",
                "Finish outcome must match whether B2 contains semantic changes",
            )
        guide = _prepare_text(stage.understanding_guide, guide=True)
        expected = {
            _understanding_path(item) for item in stage.current_understanding_ids
        }
        actual = controlled_references(guide)
        if actual != expected or any(guide.count(path) != 1 for path in expected):
            raise UnderstandingMaintenanceError(
                "incomplete_understanding_guide",
                "Understanding guide must contain exactly one Runtime route for every current item",
            )
        if expected and not guide.strip():
            raise UnderstandingMaintenanceError(
                "incomplete_understanding_guide",
                "Understanding guide cannot be empty while current items exist",
            )
        completed = replace(stage, understanding_guide=guide, completed=True, outcome=outcome)
        self._validate(completed)
        return completed

    def request_case_rework(self, stage: UnderstandingMaintenanceStage, *,
                            issues: list[CaseReworkIssueInput]
                            ) -> UnderstandingMaintenanceStage:
        """End this B2 attempt without a publishable result; B1 owns the repair."""
        self._open_stage(stage)
        if (type(issues) is not list or not 1 <= len(issues) <= MAX_REWORK_ISSUES
                or len({(item.case_id, item.source_reference) for item in issues})
                != len(issues)):
            raise UnderstandingMaintenanceError(
                "invalid_case_rework",
                f"Choose 1 to {MAX_REWORK_ISSUES} distinct case/source issues",
            )
        prepared: list[CaseReworkIssue] = []
        for item in issues:
            try:
                case_id = _stable_id(item.case_id, field="case_id")
            except ValueError as error:
                raise UnderstandingMaintenanceError(
                    "invalid_case_rework", "Case rework ID is invalid",
                ) from error
            if case_id not in stage.read_case_ids:
                raise UnderstandingMaintenanceError(
                    "case_read_required", "Read the case before requesting B1 rework",
                )
            if CaseSourceRead(case_id, item.source_reference) not in stage.read_source_references:
                raise UnderstandingMaintenanceError(
                    "source_read_required",
                    "Read the cited canonical source before requesting B1 rework",
                )
            if item.source_reference not in self.read_case(stage, case_id).source_references:
                raise UnderstandingMaintenanceError(
                    "source_not_owned_by_case",
                    "Canonical source reference does not belong to the cited case",
                )
            prepared.append(CaseReworkIssue(
                case_id=case_id,
                source_reference=item.source_reference,
                reason=_rework_reason(item.reason),
            ))
        completed = replace(
            stage,
            case_rework_issues=tuple(prepared),
            completed=True,
            outcome="case_rework_required",
        )
        self._validate(completed)
        return completed

    def current_understandings(self, stage: UnderstandingMaintenanceStage
                               ) -> tuple[WorkUnderstandingArtifact, ...]:
        self._validate(stage)
        if not stage.completed:
            raise UnderstandingMaintenanceError(
                "understanding_stage_incomplete", "B2 stage is not complete",
            )
        if stage.outcome not in {"changed", "no_op"}:
            raise UnderstandingMaintenanceError(
                "understanding_stage_not_publishable",
                "B2 stage is complete but not publishable",
            )
        return tuple(
            self.read_understanding(stage, understanding_id)
            for understanding_id in stage.current_understanding_ids
        )

    def revalidate_understanding(self, stage: UnderstandingMaintenanceStage, *,
                                 understanding_id: str,
                                 supporting_case_ids: list[str]
                                 ) -> UnderstandingMaintenanceStage:
        self._open_stage(stage)
        understanding_id = self._require_observed_understanding(stage, understanding_id)
        if understanding_id not in stage.base_understanding_ids:
            raise UnderstandingMaintenanceError(
                "unstable_understanding_identity",
                "A work understanding created in this attempt does not need revalidation",
            )
        supporting = self._supporting_cases(stage, supporting_case_ids)
        selection = UnderstandingSupportSelection(understanding_id, supporting)
        changed = self._change(
            stage, "revalidate", (understanding_id,), (understanding_id,),
            binding_updates=self._with_binding(stage, selection),
        )
        self._validate(changed)
        return changed


def _normalized_understanding(content: str) -> str:
    try:
        content = _prepare_text(content)
    except (TypeError, ValueError) as error:
        raise UnderstandingMaintenanceError(
            "invalid_understanding_content", str(error),
        ) from error
    if not content.strip():
        raise UnderstandingMaintenanceError(
            "invalid_understanding_content", "Work-understanding content cannot be empty",
        )
    return content


def _rework_reason(value: str) -> str:
    if type(value) is not str:
        raise UnderstandingMaintenanceError(
            "invalid_case_rework", "Case rework reason must be text",
        )
    value = value.strip()
    if not value or len(value) > MAX_REWORK_REASON_CHARACTERS:
        raise UnderstandingMaintenanceError(
            "invalid_case_rework",
            f"Case rework reason must contain at most {MAX_REWORK_REASON_CHARACTERS} characters",
        )
    return value


def _route_note(value: str) -> str:
    if type(value) is not str:
        raise UnderstandingMaintenanceError("invalid_route", "Route note must be text")
    value = value.strip()
    if (not value or len(value) > MAX_ROUTE_NOTE_CHARACTERS
            or "\n" in value or "\r" in value):
        raise UnderstandingMaintenanceError(
            "invalid_route",
            f"Route note must be one nonempty line of at most {MAX_ROUTE_NOTE_CHARACTERS} characters",
        )
    if controlled_references(value):
        raise UnderstandingMaintenanceError(
            "invalid_route", "Route note contains a Runtime-owned address",
        )
    return value


def _route_line(understanding_id: str, note: str) -> str:
    return (
        f"- [工作理解 {understanding_id}]({_understanding_path(understanding_id)}) — {note}"
    )


def _route_indexes(guide: str, understanding_id: str) -> list[int]:
    path = _understanding_path(understanding_id)
    return [
        index for index, line in enumerate(guide.splitlines())
        if path in controlled_references(line)
    ]


def _replace_route(guide: str, understanding_id: str, note: str) -> str:
    note = _route_note(note)
    lines = guide.splitlines()
    indexes = _route_indexes(guide, understanding_id)
    if len(indexes) > 1:
        raise UnderstandingMaintenanceError(
            "ambiguous_understanding_route",
            "Understanding guide contains duplicate routes for this item",
        )
    if indexes:
        references = controlled_references(lines[indexes[0]])
        if references != {_understanding_path(understanding_id)}:
            raise UnderstandingMaintenanceError(
                "ambiguous_understanding_route",
                "Understanding route shares a line with another controlled address",
            )
        lines[indexes[0]] = _route_line(understanding_id, note)
    else:
        if lines and lines[-1].strip():
            lines.append("")
        lines.append(_route_line(understanding_id, note))
    return _prepare_text("\n".join(lines), guide=True)


def _remove_route(guide: str, understanding_id: str) -> str:
    lines = guide.splitlines()
    indexes = _route_indexes(guide, understanding_id)
    if len(indexes) != 1:
        raise UnderstandingMaintenanceError(
            "ambiguous_understanding_route",
            "Current work understanding must have exactly one independent guide route",
        )
    references = controlled_references(lines[indexes[0]])
    if references != {_understanding_path(understanding_id)}:
        raise UnderstandingMaintenanceError(
            "ambiguous_understanding_route",
            "Understanding route shares a line with another controlled address",
        )
    del lines[indexes[0]]
    while lines and not lines[-1].strip():
        lines.pop()
    return _prepare_text("\n".join(lines), guide=True)


def _payload(status: str, **values: Any) -> str:
    return json.dumps(
        {"status": status, **values}, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"),
    )


def _message(name: str, runtime: ToolRuntime, status: Literal["success", "error"],
             **values: Any) -> ToolMessage:
    if not runtime.tool_call_id:
        raise RuntimeError("B2 tool call identity is unavailable")
    return ToolMessage(
        _payload(status, **values), tool_call_id=runtime.tool_call_id,
        name=name, status=status,
    )


def _updated(name: str, runtime: ToolRuntime, stage: UnderstandingMaintenanceStage,
             *, effect: str = "staged", **values: Any) -> Command:
    return Command(update={
        "messages": [_message(name, runtime, "success", effect=effect, **values)],
        "understanding_stage": stage.to_dict(),
    })


def understanding_maintenance_tools(session: UnderstandingMaintenanceSession):
    """Build B2 tools whose model-visible schemas contain semantic inputs only."""

    def staged(runtime: ToolRuntime) -> UnderstandingMaintenanceStage:
        messages = runtime.state.get("messages", ())
        current = messages[-1] if messages else None
        if (not isinstance(current, AIMessage) or current.invalid_tool_calls
                or len(current.tool_calls) != 1
                or current.tool_calls[0].get("id") != runtime.tool_call_id):
            raise UnderstandingMaintenanceError(
                "multiple_understanding_tool_calls",
                "Use exactly one B2 work-understanding tool per model step",
            )
        return session.load(runtime.state.get("understanding_stage"))

    def failure(name: str, runtime: ToolRuntime,
                error: UnderstandingMaintenanceError) -> ToolMessage:
        return _message(
            name, runtime, "error", effect="unchanged", error=error.code,
            next_action=str(error),
        )

    @tool("read_case")
    def read_case(case_id: str, runtime: ToolRuntime) -> Command | ToolMessage:
        """Read one candidate or replaced base case by a Runtime-provided ID; this stages only read evidence."""
        try:
            stage = staged(runtime)
            updated, item = session.observe_case(stage, case_id)
            current = case_id in session._case_stage(updated).current_case_ids
            return _updated(
                "read_case", runtime, updated, effect="unchanged",
                case={
                    "case_id": item.case_id,
                    "content": item.content,
                    "source_references": list(item.source_references),
                    "current": current,
                },
            )
        except UnderstandingMaintenanceError as error:
            return failure("read_case", runtime, error)

    @tool("read_work_understanding")
    def read_work_understanding(understanding_id: str,
                                runtime: ToolRuntime) -> Command | ToolMessage:
        """Read one current work understanding and its exact supporting case IDs."""
        try:
            updated, item = session.observe_understanding(staged(runtime), understanding_id)
            return _updated(
                "read_work_understanding", runtime, updated, effect="unchanged",
                understanding={
                    "understanding_id": item.understanding_id,
                    "content": item.content,
                    "supporting_case_ids": list(item.supporting_case_ids),
                },
            )
        except UnderstandingMaintenanceError as error:
            return failure("read_work_understanding", runtime, error)

    @tool("create_work_understanding")
    def create_work_understanding(content: str, supporting_case_ids: list[str],
                                  route_note: str,
                                  runtime: ToolRuntime) -> Command | ToolMessage:
        """Stage one genuinely new stable work understanding supported by cases already read."""
        try:
            updated = session.create_understanding(
                staged(runtime), content=content,
                supporting_case_ids=supporting_case_ids, route_note=route_note,
            )
            identity = updated.changes[-1].current_understanding_ids[0]
            return _updated(
                "create_work_understanding", runtime, updated,
                understanding_id=identity,
            )
        except UnderstandingMaintenanceError as error:
            return failure("create_work_understanding", runtime, error)

    @tool("revise_work_understanding")
    def revise_work_understanding(understanding_id: str, diff: str,
                                  supporting_case_ids: list[str],
                                  route_note: str | None,
                                  runtime: ToolRuntime) -> Command | ToolMessage:
        """Patch one current understanding and set its complete current case support; use null route_note to keep routing."""
        try:
            updated = session.revise_understanding(
                staged(runtime), understanding_id=understanding_id, diff=diff,
                supporting_case_ids=supporting_case_ids, route_note=route_note,
            )
            return _updated(
                "revise_work_understanding", runtime, updated,
                understanding_id=understanding_id,
            )
        except UnderstandingMaintenanceError as error:
            return failure("revise_work_understanding", runtime, error)

    @tool("revalidate_work_understanding")
    def revalidate_work_understanding(understanding_id: str,
                                      supporting_case_ids: list[str],
                                      runtime: ToolRuntime) -> Command | ToolMessage:
        """Confirm unchanged prose against cases actually read and refresh its complete support without a semantic edit."""
        try:
            updated = session.revalidate_understanding(
                staged(runtime), understanding_id=understanding_id,
                supporting_case_ids=supporting_case_ids,
            )
            return _updated(
                "revalidate_work_understanding", runtime, updated,
                effect="binding_revalidated", understanding_id=understanding_id,
            )
        except UnderstandingMaintenanceError as error:
            return failure("revalidate_work_understanding", runtime, error)

    @tool("split_work_understanding")
    def split_work_understanding(
        understanding_id: str,
        replacements: Annotated[
            list[UnderstandingReplacementInput],
            Field(min_length=2, max_length=MAX_REPLACEMENTS),
        ],
        runtime: ToolRuntime,
    ) -> Command | ToolMessage:
        """Supersede one published understanding with two or more complete supported understandings."""
        try:
            updated = session.split_understanding(
                staged(runtime), understanding_id=understanding_id,
                replacements=replacements,
            )
            return _updated(
                "split_work_understanding", runtime, updated,
                understanding_ids=list(updated.changes[-1].current_understanding_ids),
            )
        except UnderstandingMaintenanceError as error:
            return failure("split_work_understanding", runtime, error)

    @tool("merge_work_understandings")
    def merge_work_understandings(
        understanding_ids: Annotated[
            list[str], Field(min_length=2, max_length=MAX_REPLACEMENTS),
        ],
        content: str,
        supporting_case_ids: list[str],
        route_note: str,
        runtime: ToolRuntime,
    ) -> Command | ToolMessage:
        """Supersede published understandings with one complete supported current understanding."""
        try:
            updated = session.merge_understandings(
                staged(runtime), understanding_ids=understanding_ids, content=content,
                supporting_case_ids=supporting_case_ids, route_note=route_note,
            )
            identity = updated.changes[-1].current_understanding_ids[0]
            return _updated(
                "merge_work_understandings", runtime, updated,
                understanding_id=identity,
            )
        except UnderstandingMaintenanceError as error:
            return failure("merge_work_understandings", runtime, error)

    @tool("retire_work_understanding")
    def retire_work_understanding(understanding_id: str,
                                  runtime: ToolRuntime) -> Command | ToolMessage:
        """Retire one published understanding whose current case support no longer establishes it."""
        try:
            updated = session.retire_understanding(
                staged(runtime), understanding_id=understanding_id,
            )
            return _updated(
                "retire_work_understanding", runtime, updated,
                retired_understanding_id=understanding_id,
            )
        except UnderstandingMaintenanceError as error:
            return failure("retire_work_understanding", runtime, error)

    @tool("set_work_understanding_route")
    def set_work_understanding_route(understanding_id: str, route_note: str,
                                     runtime: ToolRuntime) -> Command | ToolMessage:
        """Update only one current understanding's guide wording; Runtime keeps its ID and route target."""
        try:
            updated = session.set_understanding_route(
                staged(runtime), understanding_id=understanding_id,
                route_note=route_note,
            )
            return _updated(
                "set_work_understanding_route", runtime, updated,
                understanding_id=understanding_id,
            )
        except UnderstandingMaintenanceError as error:
            return failure("set_work_understanding_route", runtime, error)

    @tool("finish_understanding_maintenance")
    def finish_understanding_maintenance(outcome: Literal["changed", "no_op"],
                                         runtime: ToolRuntime) -> Command | ToolMessage:
        """Finish B2 after affected cases and understandings are handled; this does not publish Memory."""
        try:
            updated = session.finish(staged(runtime), outcome=outcome)
            return _updated(
                "finish_understanding_maintenance", runtime, updated,
                effect="stage_complete", outcome=outcome,
                current_understanding_ids=list(updated.current_understanding_ids),
            )
        except UnderstandingMaintenanceError as error:
            return failure("finish_understanding_maintenance", runtime, error)

    return [
        read_case, read_work_understanding, create_work_understanding,
        revise_work_understanding, revalidate_work_understanding,
        split_work_understanding, merge_work_understandings,
        retire_work_understanding, set_work_understanding_route,
        finish_understanding_maintenance,
    ]
