"""Task Proposal decision failures owned by `task_analysis`.

`InvalidProposalDecision` stays a shared `app.core.errors` type (ADR 0058
rule 7); this module does not duplicate it. Only the two failures specific to
Task Proposal decisions (`decide_proposal`／`propose_task_for_jd`) live here.
"""

from __future__ import annotations

from app.core.errors import JobAnalysisApplicationError


class ProposalNotFound(JobAnalysisApplicationError):
    pass


class ProposalNotDecidable(JobAnalysisApplicationError):
    pass
