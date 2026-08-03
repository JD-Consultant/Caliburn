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
from .verifier import VerificationReport, verify_task_discovery

__all__ = [
    "ConsultantAction",
    "EmployeeMessage",
    "NextQuestion",
    "SourceClaim",
    "SourceSpan",
    "TaskCandidate",
    "TaskDiscoveryInput",
    "TaskDiscoveryOutput",
    "TurnUnderstandInput",
    "TurnUnderstandOutput",
    "WorkReconcileDecideInput",
    "WorkReconcileDecideOutput",
    "VerificationReport",
    "verify_task_discovery",
]
