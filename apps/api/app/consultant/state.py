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
    JsonValue,
    StringConstraints,
    model_validator,
)
from typing_extensions import Annotated


NonEmptyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
ActionHandle = Annotated[
    str,
    StringConstraints(pattern=r"^action-[0-9]{3,}$"),
]
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
    blocked_by_decision_ids: tuple[UUID, ...] = ()
    resume_status: InterviewWorkStatus | None = None
    last_changed_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def blocking_metadata_matches_status(self) -> InterviewWorkItem:
        if len(self.blocked_by_decision_ids) != len(
            set(self.blocked_by_decision_ids)
        ):
            raise ValueError("duplicate blocked_by_decision_ids")
        if self.blocked_by_decision_ids:
            if self.status is not InterviewWorkStatus.BLOCKED:
                raise ValueError("decision-dependent work must be blocked")
            if self.resume_status in {None, InterviewWorkStatus.BLOCKED}:
                raise ValueError("blocked interview work requires a resumable status")
        elif self.status is not InterviewWorkStatus.BLOCKED and self.resume_status is not None:
            raise ValueError("unblocked interview work cannot retain blocking metadata")
        return self


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


class DocumentPatchOperation(StrEnum):
    ADD = "add"
    REVISE = "revise"
    WITHDRAW = "withdraw"
    MERGE = "merge"
    SPLIT = "split"
    REASSIGN = "reassign"
    REORDER = "reorder"


class DocumentPathRead(DurableModel):
    path: NonEmptyText
    value_sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]


class DocumentPatchAction(DurableModel):
    """One application-identified review action, not a model authority write."""

    action_id: UUID
    operation: DocumentPatchOperation
    path: NonEmptyText
    target_key: NonEmptyText
    before: JsonValue | None = None
    after: JsonValue | None = None
    source_ids: tuple[UUID, ...] = Field(min_length=1)
    quote_anchors: tuple[QuoteAnchor, ...] = ()
    read_set: tuple[DocumentPathRead, ...] = Field(min_length=1)
    target_ids: tuple[UUID, ...] = ()
    depends_on_action_ids: tuple[UUID, ...] = ()
    supersedes_action_ids: tuple[UUID, ...] = ()
    atomic_subgroup_id: UUID | None = None
    affected_work_ids: tuple[UUID, ...] = ()
    blocks_dependent_analysis: bool = False
    status: DocumentChangeStatus = DocumentChangeStatus.PENDING
    employee_after: JsonValue | None = None
    rejection_reason: NonEmptyText | None = None
    stale_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def review_metadata_is_consistent(self) -> DocumentPatchAction:
        for label, values in (
            ("source_ids", self.source_ids),
            ("target_ids", self.target_ids),
            ("depends_on_action_ids", self.depends_on_action_ids),
            ("supersedes_action_ids", self.supersedes_action_ids),
            ("affected_work_ids", self.affected_work_ids),
        ):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label}")
        read_paths = [item.path for item in self.read_set]
        if len(read_paths) != len(set(read_paths)):
            raise ValueError("duplicate document read-set path")
        if self.operation is DocumentPatchOperation.WITHDRAW:
            if self.after is not None:
                raise ValueError("withdraw patch must not carry an after value")
        elif self.after is None:
            raise ValueError("non-withdraw patch requires an after value")
        if self.status is DocumentChangeStatus.REJECTED and not self.rejection_reason:
            raise ValueError("rejected patch requires an employee reason")
        if self.status is DocumentChangeStatus.STALE and not self.stale_reason:
            raise ValueError("stale patch requires a presentable reason")
        if (
            self.status is DocumentChangeStatus.EDIT_ACCEPTED
            and self.employee_after is None
        ):
            raise ValueError("edit-accepted patch requires the employee value")
        if self.action_id in self.depends_on_action_ids:
            raise ValueError("a patch action cannot depend on itself")
        if self.action_id in self.supersedes_action_ids:
            raise ValueError("a patch action cannot supersede itself")
        return self


class DocumentChangeSet(DurableModel):
    changeset_id: UUID
    summary: NonEmptyText
    actions: tuple[DocumentPatchAction, ...] = Field(min_length=1)
    source_ids: tuple[UUID, ...] = Field(min_length=1)
    created_revision: int = Field(ge=0)
    external_dependency_action_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def action_identity_and_evidence_are_consistent(self) -> DocumentChangeSet:
        action_ids = [item.action_id for item in self.actions]
        if len(action_ids) != len(set(action_ids)):
            raise ValueError("duplicate patch action_id")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("duplicate changeset source_id")
        if len(self.external_dependency_action_ids) != len(
            set(self.external_dependency_action_ids)
        ):
            raise ValueError("duplicate external dependency action_id")
        if set(self.source_ids) != {
            source_id for action in self.actions for source_id in action.source_ids
        }:
            raise ValueError("changeset evidence must equal its action evidence")
        known_actions = set(action_ids)
        external_actions = set(self.external_dependency_action_ids)
        referenced_external: set[UUID] = set()
        for action in self.actions:
            dependencies = set(action.depends_on_action_ids)
            if not dependencies <= known_actions | external_actions:
                raise ValueError("undeclared patch dependency crosses its changeset")
            referenced_external.update(dependencies - known_actions)
        if referenced_external != external_actions:
            raise ValueError(
                "declared external dependency closure does not match patch dependencies"
            )
        return self


ConsultantSkillId = Literal[
    "work-discovery",
    "story-interview",
    "task-boundary",
    "duty-grouping",
    "output",
    "performance-indicator",
    "knowledge",
    "skill",
    "completion-red-team",
]


class CheckedCandidateReceipt(DurableModel):
    """The exact candidate check accepted by the authority graph.

    Candidate resource files are transient model state.  This receipt is the
    only durable hand-off between a successful check and final publication.
    """

    run_id: UUID
    baseline_revision: int = Field(ge=0)
    candidate_revision: int = Field(ge=1)
    resource_digest: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    check_call_id: NonEmptyText
    used_skill_ids: tuple[ConsultantSkillId, ...]
    action_handles: tuple[ActionHandle, ...] = Field(min_length=1)
    changeset: DocumentChangeSet

    @model_validator(mode="after")
    def used_skills_are_unique(self) -> CheckedCandidateReceipt:
        if len(self.used_skill_ids) != len(set(self.used_skill_ids)):
            raise ValueError("duplicate checked candidate used_skill_ids")
        if len(self.action_handles) != len(set(self.action_handles)):
            raise ValueError("duplicate checked candidate action handle")
        if len(self.action_handles) != len(self.changeset.actions):
            raise ValueError(
                "checked candidate action handles must match receipt actions"
            )
        return self


class RequiredClarification(DurableModel):
    clarification_id: UUID
    question: NonEmptyText
    reason: NonEmptyText
    current_understanding: NonEmptyText
    choices: tuple[NonEmptyText, ...] = Field(min_length=2, max_length=3)
    affected_work_ids: tuple[UUID, ...] = ()
    affected_branch: NonEmptyText
    source_ids: tuple[UUID, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def choices_and_dependencies_are_unique(self) -> RequiredClarification:
        if len(self.choices) != len(set(self.choices)):
            raise ValueError("duplicate clarification choices")
        if len(self.affected_work_ids) != len(set(self.affected_work_ids)):
            raise ValueError("duplicate clarification affected_work_ids")
        if len(self.source_ids) != len(set(self.source_ids)):
            raise ValueError("duplicate clarification source_ids")
        return self


class RunStatus(StrEnum):
    IDLE = "idle"
    SOURCE_SAVED = "source_saved"
    COMPLETED = "completed"
    FAILED = "failed"


class RunExecutionEvidence(DurableModel):
    """Payload-free resolved route, Context and model-attempt evidence."""

    resolved_execution: dict[str, JsonValue]
    context_selection_receipts: tuple[dict[str, JsonValue], ...] = ()
    attempt_receipts: tuple[dict[str, JsonValue], ...] = ()


class RunReceipt(DurableModel):
    run_id: UUID
    status: RunStatus
    source_id: UUID | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = None
    execution_evidence: RunExecutionEvidence | None = None

    @model_validator(mode="after")
    def lifecycle_fields_match_status(self) -> RunReceipt:
        if self.status is RunStatus.SOURCE_SAVED:
            if (
                self.source_id is None
                or self.completed_at is not None
                or self.error_code
                or self.execution_evidence is not None
            ):
                raise ValueError("source-saved run requires only its source and start time")
        elif self.status is RunStatus.COMPLETED:
            if self.source_id is None or self.completed_at is None or self.error_code:
                raise ValueError("completed run requires source and completion time")
        elif self.status is RunStatus.FAILED:
            if self.source_id is None or self.completed_at is None or not self.error_code:
                raise ValueError("failed run requires source, completion time and error code")
        return self


class CommandReceipt(DurableModel):
    """Durable identity for one employee command and its canonical payload."""

    command_id: UUID
    command_kind: NonEmptyText
    payload_sha256: Annotated[
        str,
        StringConstraints(pattern=r"^[0-9a-f]{64}$"),
    ]


class CommandReceiptConflict(ValueError):
    """A durable command identity was reused for another semantic payload."""


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
    command_receipts: dict[str, dict[str, Any]]
    checked_candidate: dict[str, Any] | None


class ConsultantCommandContext(TypedDict, total=False):
    action: Literal[
        "initialize",
        "register_source",
        "restart_consultant_run",
        "mark_consultant_run_failed",
        "direct_edit",
        "commit_consultant_result",
        "decide_understanding_calibration",
        "accept_changes",
        "edit_and_accept_changes",
        "reject_changes",
        "defer_changes",
        "workspace_authority_commit",
        "check_candidate_document",
        "publish_checked_candidate",
    ]
    document_id: str
    expected_revision: int
    source_reference: dict[str, Any] | None
    approved_document: dict[str, Any]
    semantic_commit: dict[str, Any]
    calibration_id: str
    calibration_decision: Literal["confirm", "later"]
    changeset_id: str
    action_ids: list[str]
    edited_after_by_action_id: dict[str, Any]
    rejection_reason: str
    run_receipt: dict[str, Any]
    command_receipt: dict[str, Any]
    checked_candidate: dict[str, Any]
    run_id: str


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
        "command_receipts": {},
        "checked_candidate": None,
    }


def inspect_command_receipt(
    state: ConsultantThreadState,
    requested: CommandReceipt,
) -> Literal["new", "replay"]:
    """Classify a command before revision checks so exact retries stay safe."""

    existing_payload = state.get("command_receipts", {}).get(
        str(requested.command_id)
    )
    if existing_payload is None:
        return "new"
    existing = CommandReceipt.model_validate(existing_payload)
    if existing != requested:
        raise CommandReceiptConflict(
            f"command {requested.command_id} was reused with another payload"
        )
    return "replay"


def attach_command_receipt(
    state: ConsultantThreadState,
    requested: CommandReceipt,
) -> dict[str, dict[str, Any]]:
    receipts = dict(state.get("command_receipts", {}))
    receipts[str(requested.command_id)] = requested.model_dump(mode="json")
    return receipts
