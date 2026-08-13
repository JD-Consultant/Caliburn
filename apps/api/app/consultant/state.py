"""Typed durable facts for the purpose-first consultant runtime.

Pydantic models validate commands and projections at the boundary.  The
LangGraph checkpoint itself contains only JSON-safe dictionaries, stable IDs,
and source lineage; employee verbatim text belongs exclusively to the Store.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Any, Literal, TypedDict
from uuid import UUID

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)
from typing_extensions import Annotated


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
VerbatimText = Annotated[str, StringConstraints(min_length=1)]


class DurableModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class EmployeeSourceKind(StrEnum):
    EMPLOYEE_TURN = "employee_turn"
    DIRECT_EDIT = "direct_edit"


class SourceProcessingStatus(StrEnum):
    PENDING = "pending"
    COMMITTED = "committed"


class SourceValidity(StrEnum):
    CURRENT = "current"
    SUPERSEDED = "superseded"


class SourcePositionAnchor(DurableModel):
    """Where employee-authored text came from inside its input surface."""

    document_path: NonEmptyText
    start: int = Field(ge=0)
    end: int = Field(gt=0)

    @model_validator(mode="after")
    def end_follows_start(self) -> SourcePositionAnchor:
        if self.end <= self.start:
            raise ValueError("source position end must be greater than start")
        return self


class EmployeeSource(DurableModel):
    """The only first-release source kinds that can support work facts."""

    schema_version: Literal[1] = 1
    source_id: UUID
    document_id: UUID
    kind: EmployeeSourceKind
    speaker: Literal["employee"] = "employee"
    text: VerbatimText
    text_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processing_status: SourceProcessingStatus = SourceProcessingStatus.PENDING
    validity: SourceValidity = SourceValidity.CURRENT
    supersedes_source_id: UUID | None = None
    superseded_by_source_id: UUID | None = None
    positions: tuple[SourcePositionAnchor, ...]

    @classmethod
    def pending(
        cls,
        *,
        source_id: UUID,
        document_id: UUID,
        kind: EmployeeSourceKind,
        text: str,
        supersedes_source_id: UUID | None = None,
        created_at: datetime | None = None,
        positions: tuple[SourcePositionAnchor, ...] | None = None,
    ) -> EmployeeSource:
        resolved_positions = (
            positions
            if positions is not None
            else (
                SourcePositionAnchor(
                    document_path="/conversation/employee",
                    start=0,
                    end=len(text),
                ),
            )
        )
        return cls(
            source_id=source_id,
            document_id=document_id,
            kind=kind,
            text=text,
            text_sha256=sha256(text.encode("utf-8")).hexdigest(),
            supersedes_source_id=supersedes_source_id,
            created_at=created_at or datetime.now(UTC),
            positions=resolved_positions,
        )

    @model_validator(mode="after")
    def immutable_payload_hash_matches(self) -> EmployeeSource:
        if not self.text.strip():
            raise ValueError("employee source text must not be blank")
        actual = sha256(self.text.encode("utf-8")).hexdigest()
        if actual != self.text_sha256:
            raise ValueError("text_sha256 does not match employee source text")
        if self.source_id == self.supersedes_source_id:
            raise ValueError("an employee source cannot supersede itself")
        if self.source_id == self.superseded_by_source_id:
            raise ValueError("an employee source cannot be superseded by itself")
        if self.validity is SourceValidity.CURRENT and self.superseded_by_source_id:
            raise ValueError("a current source cannot carry superseded_by_source_id")
        if (
            self.validity is SourceValidity.SUPERSEDED
            and self.superseded_by_source_id is None
        ):
            raise ValueError("a superseded source requires superseded_by_source_id")
        if not self.positions:
            raise ValueError("employee source requires at least one position anchor")
        for position in self.positions:
            if position.end > len(self.text):
                raise ValueError("source position exceeds employee source text")
        return self


class SourceReference(DurableModel):
    source_id: UUID
    kind: EmployeeSourceKind
    created_at: datetime
    supersedes_source_id: UUID | None = None


class QuoteAnchor(DurableModel):
    source_id: UUID
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: VerbatimText

    @model_validator(mode="after")
    def end_follows_start(self) -> QuoteAnchor:
        if self.end <= self.start:
            raise ValueError("quote anchor end must be greater than start")
        if not self.quote.strip():
            raise ValueError("quote anchor must not be blank")
        return self


class ApprovedDuty(DurableModel):
    duty_id: UUID
    statement: NonEmptyText
    display_order: int = Field(ge=0)


class ApprovedEnablerKind(StrEnum):
    TOOL_SYSTEM = "tool_system"
    METHOD = "method"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    OTHER = "other"


class ApprovedEnabler(DurableModel):
    kind: ApprovedEnablerKind
    name: NonEmptyText


class ApprovedResponsibilityRole(StrEnum):
    PRIMARY = "primary"
    SHARED = "shared"
    ASSIST = "assist"


class ApprovedTask(DurableModel):
    task_id: UUID
    duty_id: UUID | None = None
    statement: NonEmptyText
    action: NonEmptyText
    object: NonEmptyText
    purpose_result: NonEmptyText | None = None
    context: NonEmptyText | None = None
    frequency_text: NonEmptyText | None = None
    responsibility_role: ApprovedResponsibilityRole | None = None
    enablers: tuple[ApprovedEnabler, ...] = ()
    display_order: int = Field(ge=0)
    competency_level: int | None = Field(default=None, ge=1, le=6)


class ApprovedOpksKind(StrEnum):
    OUTPUT = "output"
    PERFORMANCE_INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ATTITUDE = "attitude"


class ApprovedOpksItem(DurableModel):
    item_id: UUID
    kind: ApprovedOpksKind
    text: NonEmptyText
    display_order: int = Field(ge=0)
    task_ids: tuple[UUID, ...] = ()
    indicator_ids: tuple[UUID, ...] = ()
    evidence_source_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def references_are_unique_and_match_the_axis(self) -> ApprovedOpksItem:
        for label, values in (
            ("task_ids", self.task_ids),
            ("indicator_ids", self.indicator_ids),
            ("evidence_source_ids", self.evidence_source_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        if self.kind in {
            ApprovedOpksKind.OUTPUT,
            ApprovedOpksKind.PERFORMANCE_INDICATOR,
        }:
            if len(self.task_ids) != 1:
                raise ValueError(f"{self.kind.value} must reference exactly one task")
            if self.indicator_ids:
                raise ValueError(
                    f"{self.kind.value} must not reference performance indicators"
                )
        if self.kind is ApprovedOpksKind.ATTITUDE and (
            self.task_ids or self.indicator_ids
        ):
            raise ValueError("attitude must not carry task or indicator references")
        if not self.evidence_source_ids:
            raise ValueError("approved OPKS item requires employee evidence")
        return self


class ApprovedJobDocument(DurableModel):
    """Employee-authoritative document content kept in one checkpoint channel."""

    schema_version: Literal[1] = 1
    document_id: UUID
    job_title: NonEmptyText | None = None
    occupation_category_name: NonEmptyText | None = None
    occupation_name: NonEmptyText | None = None
    occupation_code: NonEmptyText | None = None
    industry_name: NonEmptyText | None = None
    industry_code: NonEmptyText | None = None
    work_description: NonEmptyText | None = None
    competency_level: int | None = Field(default=None, ge=1, le=6)
    notes: NonEmptyText | None = None
    duties: tuple[ApprovedDuty, ...] = ()
    tasks: tuple[ApprovedTask, ...] = ()
    opks: tuple[ApprovedOpksItem, ...] = ()

    @model_validator(mode="after")
    def stable_ids_and_orders_are_consistent(self) -> ApprovedJobDocument:
        duty_ids = [item.duty_id for item in self.duties]
        task_ids = [item.task_id for item in self.tasks]
        opks_ids = [item.item_id for item in self.opks]
        for label, values in (
            ("duty_id", duty_ids),
            ("task_id", task_ids),
            ("opks item_id", opks_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        for label, values in (
            ("duty display_order", [item.display_order for item in self.duties]),
            ("task display_order", [item.display_order for item in self.tasks]),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        known_duties = set(duty_ids)
        for task in self.tasks:
            if task.duty_id is not None and task.duty_id not in known_duties:
                raise ValueError(f"unknown duty_id {task.duty_id}")
        known_tasks = set(task_ids)
        opks_by_id = {item.item_id: item for item in self.opks}
        for item in self.opks:
            if not set(item.task_ids) <= known_tasks:
                raise ValueError("OPKS item references an unknown task")
            for indicator_id in item.indicator_ids:
                indicator = opks_by_id.get(indicator_id)
                if (
                    indicator is None
                    or indicator.kind is not ApprovedOpksKind.PERFORMANCE_INDICATOR
                ):
                    raise ValueError(
                        "OPKS indicator_ids must identify performance indicators"
                    )
        seen_opks_orders: set[tuple[ApprovedOpksKind, int]] = set()
        for item in self.opks:
            order_key = (item.kind, item.display_order)
            if order_key in seen_opks_orders:
                raise ValueError("duplicate OPKS display_order within one axis")
            seen_opks_orders.add(order_key)
        return self


class InterviewWorkStatus(StrEnum):
    AVAILABLE = "available"
    ACTIVE = "active"
    PARKED = "parked"
    BLOCKED = "blocked"
    SUFFICIENT_FOR_NOW = "sufficient_for_now"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"
    RETIRED = "retired"


class InterviewPriority(StrEnum):
    EMPLOYEE_REQUEST = "employee_request"
    CORRECTION = "correction"
    CONTRADICTION_OR_RESPONSIBILITY = "contradiction_or_responsibility"
    TASK_BOUNDARY = "task_boundary"
    HIGH_IMPACT = "high_impact"
    DESCRIPTION = "description"
    DUTY_GROUPING = "duty_grouping"
    OPKS = "opks"
    COVERAGE = "coverage"
    OTHER = "other"


class InterviewWorkItem(DurableModel):
    work_id: UUID
    kind: NonEmptyText
    title: NonEmptyText
    subject_id: UUID | None = None
    status: InterviewWorkStatus
    priority: InterviewPriority = InterviewPriority.OTHER
    priority_reason: NonEmptyText
    missing_before_enough: NonEmptyText | None = None
    recommended_next_step: NonEmptyText | None = None
    source_ids: tuple[UUID, ...] = ()
    last_changed_revision: int = Field(ge=0)


class UnderstandingStatus(StrEnum):
    ACTIVE = "active"
    CHALLENGED = "challenged"
    EMPLOYEE_CONFIRMED = "employee_confirmed"
    SUPERSEDED = "superseded"
    RETIRED = "retired"


class UnderstandingImpact(StrEnum):
    ROUTINE = "routine"
    MEANINGFUL_SHIFT = "meaningful_shift"
    STRUCTURAL_PREMISE = "structural_premise"
    HIGH_RISK_RESPONSIBILITY = "high_risk_responsibility"
    CONTRADICTION = "contradiction"
    EMPLOYEE_REQUEST = "employee_request"


class UnderstandingItem(DurableModel):
    understanding_id: UUID
    version_id: UUID
    kind: NonEmptyText
    text: NonEmptyText
    status: UnderstandingStatus = UnderstandingStatus.ACTIVE
    impact: UnderstandingImpact = UnderstandingImpact.ROUTINE
    source_ids: tuple[UUID, ...]
    work_ids: tuple[UUID, ...] = ()
    created_revision: int = Field(ge=0)
    supersedes_version_id: UUID | None = None
    superseded_by_version_id: UUID | None = None


class GapStatus(StrEnum):
    ACTIVE = "active"
    HELD_WITH_REASON = "held_with_reason"
    RESOLVED = "resolved"


class GapItem(DurableModel):
    gap_id: UUID
    reason: NonEmptyText
    description: NonEmptyText
    subject_kind: NonEmptyText
    subject_id: UUID | None = None
    blocks_dependent_analysis: bool = False
    status: GapStatus = GapStatus.ACTIVE
    source_ids: tuple[UUID, ...]
    last_changed_revision: int = Field(ge=0)


class CalibrationKind(StrEnum):
    SOFT = "soft"
    BRANCH_BLOCKING = "branch_blocking"


class CalibrationTrigger(StrEnum):
    FOCUS_TRANSITION = "focus_transition"
    MEANINGFUL_SHIFT = "meaningful_shift"
    LONG_RETURN = "long_return"
    STRUCTURAL_PREMISE = "structural_premise"
    HIGH_RISK_RESPONSIBILITY = "high_risk_responsibility"
    CONTRADICTION = "contradiction"
    EMPLOYEE_REQUEST = "employee_request"


class CalibrationStatus(StrEnum):
    PENDING = "pending"
    LATER = "later"
    CONFIRMED = "confirmed"
    SUPERSEDED = "superseded"


class CalibrationDecision(StrEnum):
    CONFIRM = "confirm"
    LATER = "later"


class UnderstandingCalibration(DurableModel):
    calibration_id: UUID
    kind: CalibrationKind
    trigger: CalibrationTrigger
    status: CalibrationStatus = CalibrationStatus.PENDING
    understanding_ids: tuple[UUID, ...]
    affected_work_ids: tuple[UUID, ...] = ()
    source_ids: tuple[UUID, ...]
    decision_source_id: UUID | None = None
    content_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    created_revision: int = Field(ge=0)


class DocumentChangeStatus(StrEnum):
    PENDING = "pending"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"
    EDIT_ACCEPTED = "edit_accepted"
    REJECTED = "rejected"
    STALE = "stale"


class DocumentChangeSet(DurableModel):
    changeset_id: UUID
    status: DocumentChangeStatus = DocumentChangeStatus.PENDING
    actions: tuple[dict[str, Any], ...]
    source_ids: tuple[UUID, ...]
    read_revision: int = Field(ge=0)
    blocked_work_ids: tuple[UUID, ...] = ()


class RequiredClarification(DurableModel):
    clarification_id: UUID
    question: NonEmptyText
    reason: NonEmptyText
    affected_work_ids: tuple[UUID, ...] = ()


class RunStatus(StrEnum):
    IDLE = "idle"
    SOURCE_SAVED = "source_saved"
    COMPLETED = "completed"
    FAILED = "failed"


class RunReceipt(DurableModel):
    run_id: UUID
    status: RunStatus
    source_id: UUID | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None


class ConsultantThreadState(TypedDict, total=False):
    """LangGraph-owned state; employee source text still lives only in Store."""

    schema_version: int
    document_id: str
    revision: int
    source_count: int
    latest_source_id: str | None
    source_supersessions: dict[str, str]
    messages: Annotated[list[AnyMessage], add_messages]
    current_work_id: str | None
    interview_work: dict[str, dict[str, Any]]
    understanding: dict[str, dict[str, Any]]
    understanding_calibrations: dict[str, dict[str, Any]]
    latest_calibration_id: str | None
    gaps: dict[str, dict[str, Any]]
    review_queue: dict[str, dict[str, Any]]
    approved_document: dict[str, Any]
    required_clarification: dict[str, Any] | None
    sufficiency: dict[str, Any] | None
    latest_run: dict[str, Any] | None


class ConsultantCommandContext(TypedDict, total=False):
    action: Literal[
        "initialize",
        "register_source",
        "direct_edit",
        "commit_consultant_result",
        "decide_understanding_calibration",
    ]
    document_id: str
    expected_revision: int
    source_reference: dict[str, Any] | None
    approved_document: dict[str, Any]
    semantic_commit: dict[str, Any]
    calibration_id: str
    calibration_decision: Literal["confirm", "later"]


def initial_thread_state(document_id: UUID) -> ConsultantThreadState:
    return {
        "schema_version": 1,
        "document_id": str(document_id),
        "revision": 0,
        "source_count": 0,
        "latest_source_id": None,
        "source_supersessions": {},
        "messages": [],
        "current_work_id": None,
        "interview_work": {},
        "understanding": {},
        "understanding_calibrations": {},
        "latest_calibration_id": None,
        "gaps": {},
        "review_queue": {},
        "approved_document": ApprovedJobDocument(
            document_id=document_id
        ).model_dump(mode="json"),
        "required_clarification": None,
        "sufficiency": None,
        "latest_run": None,
    }
