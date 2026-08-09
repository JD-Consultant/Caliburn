"""Pure persistence ports for the greenfield job-analysis engine.

SQLAlchemy rows and JSON dictionaries stop at the adapter boundary. Application
services exchange only these immutable records and domain contracts.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import TracebackType
from typing import Literal, Protocol, Self
from uuid import UUID

from pydantic import model_validator

from app.job_analysis.domain import (
    CurrentWorkModel,
    DomainModel,
    Duty,
    DutyId,
    Identifier,
    JdHeader,
    JdTask,
    NonEmptyText,
    OpksEntityKind,
    OpksItem,
    OpksProposal,
    OpksProposalStatus,
    Proposal,
    ProposalStatus,
    TaskId,
)

from .context import ActiveQuestion, ConversationTurn
from .opks_digest import ScheduledOpks
from .transition import JobAnalysisState
from .verifier import TurnSpeaker


WORK_MODEL_SCHEMA_ID = "job-analysis-work-model/1"
JD_HEADER_SCHEMA_ID = "job-analysis-jd-header/1"
PROPOSAL_SCHEMA_ID = "job-analysis-proposal/1"
OPKS_ITEM_SCHEMA_ID = "job-analysis-opks-item/1"
OPKS_PROPOSAL_SCHEMA_ID = "job-analysis-opks-proposal/1"
OPKS_DIRECT_EDIT_SCHEMA_ID = "job-analysis-opks-direct-edit/1"
OPKS_PROPOSAL_DECISION_SCHEMA_ID = "job-analysis-opks-proposal-decision/1"
# /2:`analysis_input_digest` 必填且 `outcome` 值域改變,舊 entry 讀不回來
# (ADR 0054 決定 28)。依 owner 裁定不寫相容層、不搬舊資料。
OPKS_GENERATION_SCHEMA_ID = "job-analysis-opks-generation/2"
ACTIVE_QUESTION_SCHEMA_ID = "job-analysis-active-question/1"
CONSULTANT_OPENING_SCHEMA_ID = "job-analysis-consultant-opening/1"
COMPLETED_TURN_SCHEMA_ID = "job-analysis-completed-turn/1"
DIRECT_EDIT_SCHEMA_ID = "job-analysis-direct-edit/1"
JD_HEADER_DIRECT_EDIT_SCHEMA_ID = "job-analysis-jd-header-direct-edit/1"
DUTY_DIRECT_EDIT_SCHEMA_ID = "job-analysis-duty-direct-edit/1"
PROPOSAL_DECISION_SCHEMA_ID = "job-analysis-proposal-decision/1"


@dataclass(frozen=True)
class DocumentRecord:
    document_id: UUID
    title: str
    jd_header: JdHeader
    work_model: CurrentWorkModel
    active_question: ActiveQuestion | None
    authority_generation: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("document title cannot be blank")
        if self.authority_generation < 0:
            raise ValueError("authority_generation cannot be negative")


@dataclass(frozen=True)
class LoadedDocument:
    document: DocumentRecord
    state: JobAnalysisState
    conversation_turns: tuple[ConversationTurn, ...]


@dataclass(frozen=True)
class DocumentSummary:
    document_id: UUID
    title: str
    task_count: int
    updated_at: datetime

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("document title cannot be blank")
        if self.task_count < 0:
            raise ValueError("task_count cannot be negative")


class CompletedTurnPayload(DomainModel):
    operation_id: Identifier
    employee_turn: ConversationTurn
    consultant_turn: ConversationTurn

    scheduled_opks: ScheduledOpks | None = None
    """這個已提交的員工回合綁定的唯一 OPKS child(決定 7–8)。

    **綁定在 receipt 寫入時凍結。** 沒有這一條,replay 會重跑 scheduler 並改選下一個
    Task,使同一個員工回合付兩次錢——這是整條線最重要的單一不變量。

    child operation ID 由 `scheduled_opks_operation_id()` 推導,**不另存**。
    `None` 表示該回合沒有排定任何分析。
    """

    @model_validator(mode="after")
    def roles_match_the_completed_turn(self):
        if self.employee_turn.speaker is not TurnSpeaker.EMPLOYEE:
            raise ValueError("employee_turn must have the employee speaker")
        if self.consultant_turn.speaker is not TurnSpeaker.CONSULTANT:
            raise ValueError("consultant_turn must have the consultant speaker")
        return self


class ConsultantOpeningPayload(DomainModel):
    consultant_turn: ConversationTurn

    @model_validator(mode="after")
    def role_matches_the_opening(self):
        if self.consultant_turn.speaker is not TurnSpeaker.CONSULTANT:
            raise ValueError("consultant_turn must have the consultant speaker")
        return self


DirectEditKind = Literal["add", "edit", "delete", "reorder"]


class DirectEditPayload(DomainModel):
    edit_kind: DirectEditKind
    task_id: TaskId | None = None
    after: JdTask | None = None
    ordered_task_ids: tuple[TaskId, ...] = ()

    @model_validator(mode="after")
    def completed_value_matches_the_edit(self):
        if self.edit_kind == "reorder":
            if self.task_id is not None or self.after is not None:
                raise ValueError("reorder must not carry one task or completed value")
            if not self.ordered_task_ids:
                raise ValueError("reorder requires ordered_task_ids")
            if len(set(self.ordered_task_ids)) != len(self.ordered_task_ids):
                raise ValueError("reorder task ids must be distinct")
            return self
        if self.task_id is None:
            raise ValueError(f"{self.edit_kind} requires a task id")
        if self.ordered_task_ids:
            raise ValueError(f"{self.edit_kind} must not carry ordered_task_ids")
        if self.edit_kind == "delete":
            if self.after is not None:
                raise ValueError("delete direct edit must have a null completed task")
            return self
        if self.after is None:
            raise ValueError(f"{self.edit_kind} requires the completed task")
        if self.after.task_id != self.task_id:
            raise ValueError("direct edit task id must match its completed task")
        return self


class JdHeaderDirectEditPayload(DomainModel):
    """Immutable before/after receipt for an employee Header replacement."""

    before: JdHeader
    after: JdHeader

    @model_validator(mode="after")
    def replacement_must_change_the_header(self):
        if self.before == self.after:
            raise ValueError("JD header direct edit must change at least one field")
        return self


DutyDirectEditAction = Literal["add", "edit", "delete", "reorder"]


class DutyDirectEditPayload(DomainModel):
    """Immutable employee receipt for one Current-JD Duty edit.

    A Duty is document authority, not Task evidence.  Its receipt deliberately
    has no ``SourceRef`` and therefore cannot become Work Model support.
    """

    action: DutyDirectEditAction
    before: Duty | None = None
    after: Duty | None = None
    ordered_duty_ids: tuple[DutyId, ...] = ()

    @model_validator(mode="after")
    def snapshots_match_action(self):
        if self.action == "add":
            if self.before is not None or self.after is None or self.ordered_duty_ids:
                raise ValueError("add Duty edit must carry only an after snapshot")
            return self
        if self.action == "edit":
            if self.before is None or self.after is None or self.ordered_duty_ids:
                raise ValueError("edit Duty must carry before and after snapshots")
            if self.before.duty_id != self.after.duty_id:
                raise ValueError("edit Duty must preserve identity")
            if self.before.display_order != self.after.display_order:
                raise ValueError("edit Duty must preserve display order")
            return self
        if self.action == "delete":
            if self.before is None or self.after is not None or self.ordered_duty_ids:
                raise ValueError("delete Duty edit must carry only a before snapshot")
            return self
        if self.before is not None or self.after is not None:
            raise ValueError("reorder Duty edit must not carry snapshots")
        if not self.ordered_duty_ids:
            raise ValueError("reorder Duty edit requires ordered_duty_ids")
        if len(set(self.ordered_duty_ids)) != len(self.ordered_duty_ids):
            raise ValueError("reorder Duty ids must be distinct")
        return self


OpksDirectEditAction = Literal["add", "edit", "delete", "reorder"]


class OpksDirectEditPayload(DomainModel):
    action: OpksDirectEditAction
    before: OpksItem | None = None
    after: OpksItem | None = None
    entity_kind: OpksEntityKind | None = None
    ordered_entity_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def snapshots_match_action(self):
        if self.action == "reorder":
            if self.before is not None or self.after is not None:
                raise ValueError("reorder OPKS edit must not carry snapshots")
            if self.entity_kind is None:
                raise ValueError("reorder OPKS edit requires an entity kind")
            if not self.ordered_entity_ids:
                raise ValueError("reorder OPKS edit requires entity ids")
            if len(set(self.ordered_entity_ids)) != len(self.ordered_entity_ids):
                raise ValueError("reorder OPKS entity ids must be distinct")
            return self
        if self.entity_kind is not None or self.ordered_entity_ids:
            raise ValueError(
                f"{self.action} OPKS edit must not carry order fields"
            )
        valid = {
            "add": self.before is None and self.after is not None,
            "edit": self.before is not None and self.after is not None,
            "delete": self.before is not None and self.after is None,
        }[self.action]
        if not valid:
            raise ValueError(f"{self.action} OPKS edit snapshot shape is invalid")
        if (
            self.action == "edit"
            and self.before is not None
            and self.after is not None
            and self.before.entity_id != self.after.entity_id
        ):
            raise ValueError("OPKS edit must preserve entity identity")
        return self


EMPLOYEE_PROPOSAL_DECISIONS = frozenset(
    {
        ProposalStatus.ACCEPTED,
        ProposalStatus.EDITED,
        ProposalStatus.REJECTED,
        ProposalStatus.DEFERRED,
        ProposalStatus.REVISION_REQUESTED,
    }
)


class ProposalDecisionPayload(DomainModel):
    proposal_id: Identifier
    decision: ProposalStatus
    employee_text: NonEmptyText | None = None
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def status_is_an_employee_decision(self):
        if self.decision not in EMPLOYEE_PROPOSAL_DECISIONS:
            raise ValueError(f"{self.decision.value} is not an employee decision")
        return self


EMPLOYEE_OPKS_PROPOSAL_DECISIONS = frozenset(
    {
        OpksProposalStatus.ACCEPTED,
        OpksProposalStatus.EDITED,
        OpksProposalStatus.REJECTED,
        OpksProposalStatus.DEFERRED,
    }
)


class OpksProposalDecisionPayload(DomainModel):
    proposal_id: Identifier
    decision: OpksProposalStatus
    employee_text: NonEmptyText | None = None
    reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def status_is_an_employee_decision(self):
        if self.decision not in EMPLOYEE_OPKS_PROPOSAL_DECISIONS:
            raise ValueError(f"{self.decision.value} is not an employee decision")
        if self.decision is OpksProposalStatus.EDITED:
            if self.employee_text is None:
                raise ValueError("edited OPKS decision requires employee_text")
        elif self.employee_text is not None:
            raise ValueError("employee_text belongs to edited OPKS decision only")
        if self.decision is OpksProposalStatus.REJECTED:
            if self.reason is None:
                raise ValueError("rejected OPKS decision requires a reason")
        elif self.reason is not None:
            raise ValueError("reason belongs to rejected OPKS decision only")
        return self


class OpksGenerationOutcome(StrEnum):
    """一次 OPKS 分析的終端結果(ADR 0054 決定 28–29)。

    **四種全部是終端 receipt**,一律阻止相同 `analysis_input_digest` 自動重跑;
    差別只在呈現與診斷,不在阻擋效果。digest 漂移是 abandon,**不寫 receipt**,
    因此不在這個值域裡(決定 10)。
    """

    PROPOSED = "proposed"
    NEEDS_CLARIFICATION = "needs_clarification"
    NO_CHANGE = "no_change"
    FAILED = "failed"


class OpksGenerationPayload(DomainModel):
    operation_id: Identifier
    selected_task_id: TaskId
    analysis_input_digest: NonEmptyText
    outcome: OpksGenerationOutcome
    proposal_ids: tuple[Identifier, ...] = ()
    gap_issue_ids: tuple[Identifier, ...] = ()

    @model_validator(mode="after")
    def payload_matches_outcome(self):
        """決定 28 的一致性由 validator 寫死,不靠呼叫端自律。"""

        if self.gap_issue_ids and (
            self.outcome is not OpksGenerationOutcome.NEEDS_CLARIFICATION
        ):
            raise ValueError(
                f"{self.outcome.value} OPKS generation must not carry gap issue ids; "
                "gaps make the outcome needs_clarification"
            )
        if self.outcome is OpksGenerationOutcome.PROPOSED:
            if not self.proposal_ids:
                raise ValueError("proposed OPKS generation requires proposal ids")
        elif self.outcome is OpksGenerationOutcome.NEEDS_CLARIFICATION:
            if not self.gap_issue_ids:
                raise ValueError(
                    "needs_clarification OPKS generation requires gap issue ids"
                )
            # proposal_ids 刻意**不**限制:決定 18 的效力單位是 item,
            # 有依據的候選照常提案,同時保留其他軸的缺口。
        elif self.proposal_ids:
            raise ValueError(
                f"{self.outcome.value} OPKS generation must not carry proposal ids"
            )
        for label, values in (
            ("proposal ids", self.proposal_ids),
            ("gap issue ids", self.gap_issue_ids),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"OPKS generation {label} must be unique")
        return self


JournalKind = Literal[
    "consultant_opening",
    "employee_turn",
    "direct_edit",
    "proposal_decision",
    "opks_generation",
]
JournalPayload = (
    ConsultantOpeningPayload
    | CompletedTurnPayload
    | DirectEditPayload
    | JdHeaderDirectEditPayload
    | DutyDirectEditPayload
    | OpksDirectEditPayload
    | OpksProposalDecisionPayload
    | OpksGenerationPayload
    | ProposalDecisionPayload
)

_JOURNAL_CONTRACT: dict[type[DomainModel], tuple[JournalKind, str]] = {
    ConsultantOpeningPayload: (
        "consultant_opening",
        CONSULTANT_OPENING_SCHEMA_ID,
    ),
    CompletedTurnPayload: ("employee_turn", COMPLETED_TURN_SCHEMA_ID),
    DirectEditPayload: ("direct_edit", DIRECT_EDIT_SCHEMA_ID),
    JdHeaderDirectEditPayload: (
        "direct_edit",
        JD_HEADER_DIRECT_EDIT_SCHEMA_ID,
    ),
    DutyDirectEditPayload: (
        "direct_edit",
        DUTY_DIRECT_EDIT_SCHEMA_ID,
    ),
    OpksDirectEditPayload: ("direct_edit", OPKS_DIRECT_EDIT_SCHEMA_ID),
    OpksProposalDecisionPayload: (
        "proposal_decision",
        OPKS_PROPOSAL_DECISION_SCHEMA_ID,
    ),
    OpksGenerationPayload: (
        "opks_generation",
        OPKS_GENERATION_SCHEMA_ID,
    ),
    ProposalDecisionPayload: ("proposal_decision", PROPOSAL_DECISION_SCHEMA_ID),
}


class JournalEntry(DomainModel):
    document_id: UUID
    entry_id: Identifier
    kind: JournalKind
    payload_schema_id: NonEmptyText
    payload: JournalPayload
    created_at: datetime

    @model_validator(mode="after")
    def kind_schema_and_payload_agree(self):
        expected_kind, expected_schema = _JOURNAL_CONTRACT[type(self.payload)]
        if self.kind != expected_kind:
            raise ValueError(
                f"journal kind {self.kind!r} does not match "
                f"{type(self.payload).__name__}"
            )
        if self.payload_schema_id != expected_schema:
            raise ValueError(
                f"payload_schema_id must be {expected_schema!r} "
                f"for {type(self.payload).__name__}"
            )
        return self


class DocumentRepository(Protocol):
    async def create(self, record: DocumentRecord) -> None: ...

    async def get(
        self, document_id: UUID, *, for_update: bool = False
    ) -> DocumentRecord | None: ...

    async def list(self) -> tuple[DocumentSummary, ...]: ...

    async def update_title(
        self,
        document_id: UUID,
        *,
        title: str,
        updated_at: datetime,
    ) -> bool: ...

    async def update_authority(
        self,
        document_id: UUID,
        *,
        expected_generation: int,
        jd_header: JdHeader,
        work_model: CurrentWorkModel,
        active_question: ActiveQuestion | None,
        updated_at: datetime,
    ) -> bool: ...


class JdTaskRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[JdTask, ...]: ...

    async def replace(
        self, document_id: UUID, tasks: tuple[JdTask, ...]
    ) -> None: ...


class DutyRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[Duty, ...]: ...

    async def replace(
        self,
        document_id: UUID,
        duties: tuple[Duty, ...],
    ) -> None: ...


class ProposalRepository(Protocol):
    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[ProposalStatus] | None = None,
    ) -> tuple[Proposal, ...]: ...

    async def replace(
        self, document_id: UUID, proposals: tuple[Proposal, ...]
    ) -> None: ...


class OpksRepository(Protocol):
    async def list(self, document_id: UUID) -> tuple[OpksItem, ...]: ...

    async def replace(
        self, document_id: UUID, items: tuple[OpksItem, ...]
    ) -> None: ...


class OpksProposalRepository(Protocol):
    async def list(
        self,
        document_id: UUID,
        *,
        statuses: frozenset[OpksProposalStatus] | None = None,
    ) -> tuple[OpksProposal, ...]: ...

    async def replace(
        self,
        document_id: UUID,
        proposals: tuple[OpksProposal, ...],
    ) -> None: ...


class JournalRepository(Protocol):
    async def get(
        self, document_id: UUID, entry_id: Identifier
    ) -> JournalEntry | None: ...

    async def add(self, entry: JournalEntry) -> None: ...

    async def list_conversation_turns(
        self, document_id: UUID
    ) -> tuple[ConversationTurn, ...]: ...


class JobAnalysisUnitOfWork(Protocol):
    documents: DocumentRepository
    tasks: JdTaskRepository
    duties: DutyRepository
    proposals: ProposalRepository
    opks: OpksRepository
    opks_proposals: OpksProposalRepository
    journal: JournalRepository

    async def __aenter__(self) -> Self: ...

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...


JobAnalysisUnitOfWorkFactory = Callable[[], JobAnalysisUnitOfWork]
