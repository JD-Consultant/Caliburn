"""Use-case 層：consultation 協調層與純 persistence ports。

Document/header/Duty/Task direct-edit use cases and readiness moved to
`app.documents` (ADR 0058). `create_document` is re-exported here from
`app.documents.authoring` only because scripts outside the composition root
still consume it directly; it is not part of `app.documents`'s curated
public API.

Task Proposal analysis (packet building, the analysis operation, proposal
decisions, transition, verifier) moved to `app.task_analysis`; OPKS(item
authoring, context, generation, scheduler, proposals, verifier)moved to
`app.opks`(both ADR 0058); this module no longer re-exports either. What
remains here — `consultation.py`／`durable_turn.py` — is the not-yet-carved
`consultation` module(Task 6),which imports both feature modules' curated
public APIs directly. `JobAnalysisState`／`ConversationTurn`／
`ActiveQuestion`／`TurnSpeaker`／`OperationOutcome` are core-owned types this
package still consumes internally, imported straight from `app.core` rather
than through `task_analysis`／`opks`.
"""

from app.core.journal import ActiveQuestion, ConversationTurn, TurnSpeaker
from app.core.model_outcome import OperationOutcome
from app.core.state import JobAnalysisState
from app.documents.authoring import create_document
from .export import (
    ExportDocument,
    ExportDutySection,
    ExportOpksEntry,
    ExportTaskEntry,
    assemble_export_document,
)
from app.core.errors import StaleAuthoritySnapshot
from .errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    InvalidProposalDecision,
    JdTaskNotFound,
)
from .consultation import submit_employee_turn
from .durable_turn import (
    CommittedTurn,
    TransitionCommitRejected,
    TurnSnapshot,
    UncommittableOperationResult,
    commit_verified_turn,
    prepare_turn,
)
from app.core.journal import (
    CONSULTANT_OPENING_SCHEMA_ID,
    COMPLETED_TURN_SCHEMA_ID,
    DIRECT_EDIT_SCHEMA_ID,
    DUTY_DIRECT_EDIT_SCHEMA_ID,
    JD_HEADER_DIRECT_EDIT_SCHEMA_ID,
    OPKS_DIRECT_EDIT_SCHEMA_ID,
    OPKS_PROPOSAL_DECISION_SCHEMA_ID,
    OPKS_GENERATION_SCHEMA_ID,
    PROPOSAL_DECISION_SCHEMA_ID,
    CompletedTurnPayload,
    ConsultantOpeningPayload,
    DirectEditKind,
    DirectEditPayload,
    DutyDirectEditPayload,
    JournalEntry,
    JournalKind,
    JdHeaderDirectEditPayload,
    OpksDirectEditPayload,
    OpksProposalDecisionPayload,
    OpksGenerationOutcome,
    OpksGenerationPayload,
    ProposalDecisionPayload,
)
from app.core.persistence import (
    ACTIVE_QUESTION_SCHEMA_ID,
    JD_HEADER_SCHEMA_ID,
    OPKS_ITEM_SCHEMA_ID,
    OPKS_PROPOSAL_SCHEMA_ID,
    PROPOSAL_SCHEMA_ID,
    WORK_MODEL_SCHEMA_ID,
    DutyRepository,
    DocumentRecord,
    DocumentRepository,
    DocumentSummary,
    JdTaskRepository,
    JobAnalysisUnitOfWork,
    JobAnalysisUnitOfWorkFactory,
    JournalRepository,
    LoadedDocument,
    OpksProposalRepository,
    OpksRepository,
    ProposalRepository,
)

__all__ = [
    "ActiveQuestion",
    "ACTIVE_QUESTION_SCHEMA_ID",
    "COMPLETED_TURN_SCHEMA_ID",
    "CONSULTANT_OPENING_SCHEMA_ID",
    "CommittedTurn",
    "CompletedTurnPayload",
    "ConsultantOpeningPayload",
    "ConcurrentAuthorityChange",
    "DIRECT_EDIT_SCHEMA_ID",
    "DUTY_DIRECT_EDIT_SCHEMA_ID",
    "JD_HEADER_DIRECT_EDIT_SCHEMA_ID",
    "DirectEditKind",
    "DirectEditPayload",
    "DutyDirectEditPayload",
    "DutyRepository",
    "ExportDocument",
    "ExportDutySection",
    "ExportOpksEntry",
    "ExportTaskEntry",
    "assemble_export_document",
    "DocumentNotFound",
    "DocumentRecord",
    "DocumentRepository",
    "DocumentSummary",
    "IdempotencyConflict",
    "InvalidProposalDecision",
    "JobAnalysisState",
    "JobAnalysisUnitOfWork",
    "JobAnalysisUnitOfWorkFactory",
    "JdTaskRepository",
    "JdHeaderDirectEditPayload",
    "JD_HEADER_SCHEMA_ID",
    "JdTaskNotFound",
    "JournalEntry",
    "JournalKind",
    "JournalRepository",
    "LoadedDocument",
    "OperationOutcome",
    "OPKS_DIRECT_EDIT_SCHEMA_ID",
    "OPKS_ITEM_SCHEMA_ID",
    "OPKS_GENERATION_SCHEMA_ID",
    "OPKS_PROPOSAL_DECISION_SCHEMA_ID",
    "OPKS_PROPOSAL_SCHEMA_ID",
    "OpksProposalRepository",
    "OpksRepository",
    "OpksDirectEditPayload",
    "OpksGenerationOutcome",
    "OpksGenerationPayload",
    "OpksProposalDecisionPayload",
    "PROPOSAL_DECISION_SCHEMA_ID",
    "PROPOSAL_SCHEMA_ID",
    "ProposalDecisionPayload",
    "ProposalRepository",
    "StaleAuthoritySnapshot",
    "TransitionCommitRejected",
    "TurnSnapshot",
    "UncommittableOperationResult",
    "ConversationTurn",
    "submit_employee_turn",
    "TurnSpeaker",
    "WORK_MODEL_SCHEMA_ID",
    "create_document",
    "commit_verified_turn",
    "prepare_turn",
]
