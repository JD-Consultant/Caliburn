"""Typed application failures shared by job-analysis use cases.

The seven failures consumed by more than one future feature module now live
in `app.core.errors` (ADR 0058 rule 7); Duty/Task/JD-header direct-edit
failures moved to `app.documents.errors`, and the four OPKS-specific failures
(`OpksItemNotFound`, `InvalidOpksOrder`, `OpksProposalNotFound`,
`OpksProposalNotDecidable`) moved to `app.opks.errors`, when their owning
feature modules were carved out. This module re-exports the errors still
consumed by what remains in `app.job_analysis.application` until Task 6
carves consultation out.
"""

from app.core.errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    InvalidProposalDecision,
    JdTaskNotFound,
    JobAnalysisApplicationError,
)
