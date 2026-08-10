"""Typed application failures shared by job-analysis use cases.

The six failures consumed by more than one future feature module now live in
`app.core.errors` (ADR 0058 rule 7); Duty/Task/JD-header direct-edit failures
moved to `app.documents.errors` when the `documents` feature module was
carved out. This module re-exports the remaining feature-specific errors that
still belong here until their owning feature module is carved out.
"""

from app.core.errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    InvalidProposalDecision,
    JdTaskNotFound,
    JobAnalysisApplicationError,
)


class OpksItemNotFound(JobAnalysisApplicationError):
    pass


class InvalidOpksOrder(JobAnalysisApplicationError):
    pass


class OpksProposalNotFound(JobAnalysisApplicationError):
    pass


class OpksProposalNotDecidable(JobAnalysisApplicationError):
    pass
