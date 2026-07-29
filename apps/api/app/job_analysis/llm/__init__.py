"""`TaskAnalysisResult.v1` 契約與其 provider-facing schema(§12)。"""

from .portable_schema import (
    ProviderSchemaPortabilityError,
    assert_portable_strict_output_schema,
    portable_strict_output_schema,
)
from .provider_schema import (
    PROVIDER_SCHEMA_PATH,
    committed_provider_schema,
    render_provider_schema_file,
    task_analysis_result_provider_schema,
)
from .prompt import TASK_ANALYSIS_INSTRUCTIONS
from .result import (
    TASK_ANALYSIS_RESULT_SCHEMA_NAME,
    ExcludePayload,
    IdentityAssessment,
    IdentityRelation,
    NextQuestion,
    NextQuestionTarget,
    NextQuestionTargetKind,
    OpenIssuePayload,
    SignalAnchor,
    SignalDisposition,
    SupportOrdinalRef,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
)

__all__ = [
    "PROVIDER_SCHEMA_PATH",
    "TASK_ANALYSIS_INSTRUCTIONS",
    "TASK_ANALYSIS_RESULT_SCHEMA_NAME",
    "ExcludePayload",
    "IdentityAssessment",
    "IdentityRelation",
    "NextQuestion",
    "NextQuestionTarget",
    "NextQuestionTargetKind",
    "OpenIssuePayload",
    "ProviderSchemaPortabilityError",
    "SignalAnchor",
    "SignalDisposition",
    "SupportOrdinalRef",
    "TaskAnalysisResult",
    "TaskChangeKind",
    "TaskChangePayload",
    "WorkSignal",
    "assert_portable_strict_output_schema",
    "committed_provider_schema",
    "portable_strict_output_schema",
    "render_provider_schema_file",
    "task_analysis_result_provider_schema",
]
