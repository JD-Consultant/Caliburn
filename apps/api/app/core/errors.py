"""Application failures consumed by more than one future feature module.

`DocumentNotFound`／`IdempotencyConflict`／`ConcurrentAuthorityChange` are raised by
every authority-writing use case across `documents`／`task_analysis`／`opks`／
`consultation`. `JdTaskNotFound` is consumed by both `documents` and `opks`;
`InvalidProposalDecision` by both `task_analysis` and `opks` (ADR 0058 rule 7).

`StaleAuthoritySnapshot` is raised by both `opks`(`generation.py`'s
`prepare_opks_generation`／`commit_opks_generation`)and the future `consultation`
module(`durable_turn.py`)whenever a read-outside-transaction snapshot has drifted
before the provider-before-replay write lands — the same "read authority is no
longer current" fact, just observed from two different call sites (ADR 0058 rule 7).

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


class StaleAuthoritySnapshot(ConcurrentAuthorityChange):
    """The model read authority that is no longer current."""
