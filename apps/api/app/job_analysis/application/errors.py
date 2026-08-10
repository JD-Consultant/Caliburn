"""Typed application failures shared by job-analysis use cases.

The seven failures consumed by more than one future feature module now live
in `app.core.errors` (ADR 0058 rule 7); Duty/Task/JD-header direct-edit
failures moved to `app.documents.errors`, and the four OPKS-specific failures
(`OpksItemNotFound`, `InvalidOpksOrder`, `OpksProposalNotFound`,
`OpksProposalNotDecidable`) moved to `app.opks.errors`, when their owning
feature modules were carved out. `app.consultation` (Task 6) now imports
these straight from `app.core.errors` rather than through this module. This
module re-exports them only for the remaining `app.job_analysis.application`
consumers (`app.api`, adapters) until Task 7 dissolves `app.job_analysis`
entirely.
"""

from app.core.errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    InvalidProposalDecision,
    JdTaskNotFound,
    JobAnalysisApplicationError,
)
