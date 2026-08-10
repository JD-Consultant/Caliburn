"""Typed application failures shared by job-analysis use cases.

The six failures consumed by more than one future feature module now live in
`app.core.errors` (ADR 0058 rule 7); this module re-exports them alongside the
feature-specific errors that still belong here until their owning feature module
is carved out.
"""

from app.core.errors import (
    ConcurrentAuthorityChange,
    DocumentNotFound,
    IdempotencyConflict,
    InvalidProposalDecision,
    JdTaskNotFound,
    JobAnalysisApplicationError,
)


class DutyNotFound(JobAnalysisApplicationError):
    pass


class InvalidDutyOrder(JobAnalysisApplicationError):
    pass


class OpksItemNotFound(JobAnalysisApplicationError):
    pass


class InvalidOpksOrder(JobAnalysisApplicationError):
    pass


class OpksProposalNotFound(JobAnalysisApplicationError):
    pass


class OpksProposalNotDecidable(JobAnalysisApplicationError):
    pass


class InvalidJdTaskOrder(JobAnalysisApplicationError):
    pass


class JdHeaderNotChanged(JobAnalysisApplicationError):
    pass
