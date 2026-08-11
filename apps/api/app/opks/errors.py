"""OPKS-specific application failures owned by `opks`.

The failures consumed by more than one future feature module now live in
`app.core.errors` (ADR 0058 rule 7). Only the four failures specific to OPKS
item authoring and OPKS Proposal decisions live here.
"""

from __future__ import annotations

from app.core.errors import JobAnalysisApplicationError


class OpksItemNotFound(JobAnalysisApplicationError):
    pass


class InvalidOpksOrder(JobAnalysisApplicationError):
    pass


class OpksProposalNotFound(JobAnalysisApplicationError):
    pass


class OpksProposalNotDecidable(JobAnalysisApplicationError):
    pass
