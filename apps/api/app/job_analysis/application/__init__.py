"""Use-case 層：OPKS use cases 與純 persistence ports。

Document/header/Duty/Task direct-edit use cases and readiness moved to
`app.documents` (ADR 0058). `create_document` is re-exported here from
`app.documents.authoring` only because scripts outside the composition root
still consume it directly; it is not part of `app.documents`'s curated
public API.

Task Proposal analysis (packet building, the analysis operation, proposal
decisions, transition, verifier) moved to `app.task_analysis` (ADR 0058);
this module no longer re-exports it. `JobAnalysisState`／`ConversationTurn`／
`ActiveQuestion`／`TurnSpeaker`／`OperationOutcome` are core-owned types this
package still consumes internally, imported straight from `app.core` rather
than through `task_analysis`.
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
from .errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    InvalidOpksOrder,
    InvalidProposalDecision,
    JdTaskNotFound,
    OpksItemNotFound,
    OpksProposalNotDecidable,
    OpksProposalNotFound,
)
from .consultation import submit_employee_turn
from .durable_turn import (
    CommittedTurn,
    StaleAuthoritySnapshot,
    TransitionCommitRejected,
    TurnSnapshot,
    UncommittableOperationResult,
    commit_verified_turn,
    prepare_turn,
)
from .opks_authoring import (
    add_opks_item,
    delete_opks_item,
    edit_opks_item,
    prune_opks_for_current_jd,
    prune_opks_gaps_for_current_jd,
    reorder_opks_items,
)
from .opks_context import (
    OpksContextPacket,
    OpksGroundingUnavailable,
    build_opks_context_packet,
    render_opks_context_packet,
)
from .opks_digest import (
    ScheduledOpks,
    compute_analysis_input_digest,
    scheduled_opks_operation_id,
)
from .opks_scheduler import (
    OpksTaskStatus,
    eligible_opks_candidates,
    opks_task_status,
    question_target_task_ids,
    select_scheduled_opks,
)
from .opks_operation import OpksOperationResult, run_opks_operation
from .opks_generation import (
    OpksGenerationResult,
    OpksGenerationSnapshot,
    commit_opks_generation,
    generate_opks_proposals,
    prepare_opks_generation,
)
from .opks_proposals import (
    decide_opks_proposal,
    remove_opks_item_and_indicator_refs,
    stale_invalid_opks_proposals,
)
from .opks_verifier import (
    OpksGap,
    OpksVerificationReport,
    OpksViolation,
    OpksViolationCode,
    VerifiedOpksChange,
    verify_opks_result,
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
    "InvalidOpksOrder",
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
    "OpksItemNotFound",
    "reorder_opks_items",
    "OpksContextPacket",
    "OpksGroundingUnavailable",
    "OpksGenerationOutcome",
    "OpksGenerationPayload",
    "OpksGenerationResult",
    "OpksGenerationSnapshot",
    "OpksOperationResult",
    "OpksProposalDecisionPayload",
    "OpksProposalNotDecidable",
    "OpksProposalNotFound",
    "OpksGap",
    "OpksTaskStatus",
    "OpksVerificationReport",
    "OpksViolation",
    "OpksViolationCode",
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
    "VerifiedOpksChange",
    "WORK_MODEL_SCHEMA_ID",
    "add_opks_item",
    "ScheduledOpks",
    "build_opks_context_packet",
    "compute_analysis_input_digest",
    "eligible_opks_candidates",
    "opks_task_status",
    "question_target_task_ids",
    "scheduled_opks_operation_id",
    "select_scheduled_opks",
    "create_document",
    "commit_verified_turn",
    "commit_opks_generation",
    "delete_opks_item",
    "decide_opks_proposal",
    "edit_opks_item",
    "generate_opks_proposals",
    "prepare_turn",
    "prepare_opks_generation",
    "prune_opks_for_current_jd",
    "prune_opks_gaps_for_current_jd",
    "render_opks_context_packet",
    "run_opks_operation",
    "remove_opks_item_and_indicator_refs",
    "stale_invalid_opks_proposals",
    "verify_opks_result",
]
