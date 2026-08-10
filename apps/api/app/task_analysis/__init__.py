"""Public API: LLM-driven Task Proposal analysis for one Current JD.

`task_analysis` owns packet building, the one-stage analysis operation,
Task Proposal decisions, the pure transition service, and the deterministic
verifier that turns a model result into Work Model / Proposal writes (ADR
0058). It never imports the concrete OpenRouter adapter or `app.opks`—only
`TaskAnalysisModelPort` and `app.core.opks_integrity`.

Only what `consultation` (Task 6) and `app.api` actually consume is
re-exported here. LLM wire mapping, prompt text, and verifier internals
(the `Packet*` ordinal views, `ViolationCode`, `VerificationContext`) stay
reachable via `app.task_analysis.llm` / `app.task_analysis.verifier` for
tests and scripts, but are not part of this curated surface (ADR 0058 rule
4). Core-owned types this feature merely consumes—`JobAnalysisState`,
`OperationOutcome`, `ConversationTurn`—are not re-exported either; callers
get those straight from `app.core`.
"""

from __future__ import annotations

from .context import (
    TaskAnalysisPacket,
    build_context_packet,
    render_context_packet,
)
from .errors import ProposalNotDecidable, ProposalNotFound
from .operation import TaskAnalysisOperationResult, run_task_analysis_operation
from .ports import TaskAnalysisModelPort
from .proposal_decisions import (
    ProposalDecision,
    decide_proposal,
    propose_task_for_jd,
)
from .transition import (
    TransitionOutcome,
    TransitionResult,
    apply_task_analysis_result,
)
from .verifier import VerificationReport, verify_task_analysis_result

__all__ = [
    "ProposalDecision",
    "ProposalNotDecidable",
    "ProposalNotFound",
    "TaskAnalysisModelPort",
    "TaskAnalysisOperationResult",
    "TaskAnalysisPacket",
    "TransitionOutcome",
    "TransitionResult",
    "VerificationReport",
    "apply_task_analysis_result",
    "build_context_packet",
    "decide_proposal",
    "propose_task_for_jd",
    "render_context_packet",
    "run_task_analysis_operation",
    "verify_task_analysis_result",
]
