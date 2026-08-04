"""Typed application failures shared by job-analysis use cases."""


class JobAnalysisApplicationError(RuntimeError):
    pass


class DocumentNotFound(JobAnalysisApplicationError):
    pass


class JdTaskNotFound(JobAnalysisApplicationError):
    pass


class DutyNotFound(JobAnalysisApplicationError):
    pass


class OpksItemNotFound(JobAnalysisApplicationError):
    pass


class OpksProposalNotFound(JobAnalysisApplicationError):
    pass


class OpksProposalNotDecidable(JobAnalysisApplicationError):
    pass


class InvalidProposalDecision(JobAnalysisApplicationError):
    pass


class IdempotencyConflict(JobAnalysisApplicationError):
    pass


class ConcurrentAuthorityChange(JobAnalysisApplicationError):
    pass


class InvalidJdTaskOrder(JobAnalysisApplicationError):
    pass


class InvalidDutyOrder(JobAnalysisApplicationError):
    pass


class JdHeaderNotChanged(JobAnalysisApplicationError):
    pass


class DutyNotChanged(JobAnalysisApplicationError):
    pass
