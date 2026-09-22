"""Greenfield professional consultant core introduced by ADR 0040.

The package is provider-, persistence-, transport-, and legacy-interview-neutral.
"""

from .contracts import (
    ConsultantAction,
    EmployeeMessage,
    NextQuestion,
    SourceClaim,
    SourceSpan,
    TaskCandidate,
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
    TurnUnderstandInput,
    TurnUnderstandOutput,
    WorkReconcileDecideInput,
    WorkReconcileDecideOutput,
)
from .prompts import OperationName, PromptProfile
from .runner import (
    OperationRunError,
    StructuredOutputProvider,
    run_task_discovery_once,
    run_task_discovery_two_stage,
)
from .schema_projection import SchemaProfile
from .verifier import (
    VerificationReport,
    verify_task_discovery,
    verify_turn_understand,
)

__all__ = [
    "ConsultantAction",
    "EmployeeMessage",
    "NextQuestion",
    "OperationName",
    "OperationRunError",
    "PromptProfile",
    "SchemaProfile",
    "SourceClaim",
    "SourceSpan",
    "TaskCandidate",
    "TaskDiscoveryInput",
    "TaskDiscoveryOutput",
    "StructuredOutputProvider",
    "TurnUnderstandInput",
    "TurnUnderstandOutput",
    "WorkReconcileDecideInput",
    "WorkReconcileDecideOutput",
    "VerificationReport",
    "run_task_discovery_once",
    "run_task_discovery_two_stage",
    "verify_task_discovery",
    "verify_turn_understand",
]
