"""Typed application failures shared by job-analysis use cases."""


class JobAnalysisApplicationError(RuntimeError):
    pass


class DocumentNotFound(JobAnalysisApplicationError):
    pass


class JdTaskNotFound(JobAnalysisApplicationError):
    pass


class IdempotencyConflict(JobAnalysisApplicationError):
    pass


class ConcurrentAuthorityChange(JobAnalysisApplicationError):
    pass


class InvalidJdTaskOrder(JobAnalysisApplicationError):
    pass

