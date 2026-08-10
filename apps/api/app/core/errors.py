"""Application failures consumed by more than one future feature module.

`DocumentNotFound`／`IdempotencyConflict`／`ConcurrentAuthorityChange` are raised by
every authority-writing use case across `documents`／`task_analysis`／`opks`／
`consultation`. `JdTaskNotFound` is consumed by both `documents` and `opks`;
`InvalidProposalDecision` by both `task_analysis` and `opks` (ADR 0058 rule 7).

Feature-specific errors (e.g. `DutyNotFound`, `OpksItemNotFound`) stay in
`app.job_analysis.application.errors` until their owning feature module exists.
"""

from __future__ import annotations


class JobAnalysisApplicationError(RuntimeError):
    pass


class DocumentNotFound(JobAnalysisApplicationError):
    pass


class JdTaskNotFound(JobAnalysisApplicationError):
    pass


class InvalidProposalDecision(JobAnalysisApplicationError):
    pass


class IdempotencyConflict(JobAnalysisApplicationError):
    pass


class ConcurrentAuthorityChange(JobAnalysisApplicationError):
    pass
