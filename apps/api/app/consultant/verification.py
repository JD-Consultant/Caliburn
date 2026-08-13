"""Deterministic gates between framework output and semantic state transitions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from app.consultant.model_runtime import (
    AttemptReceipt,
    AttemptStatus,
    ResolvedExecution,
    verify_attempt_budget,
)

if TYPE_CHECKING:
    from app.consultant.context import ContextSelectionReceipt


class ConsultantVerificationError(RuntimeError):
    pass


def verify_context_selection(
    execution: ResolvedExecution,
    receipt: ContextSelectionReceipt,
) -> None:
    if (
        receipt.profile_id != execution.profile_id
        or receipt.profile_revision != execution.profile_revision
        or receipt.policy_id != execution.policy_id
        or receipt.policy_revision != execution.policy_revision
    ):
        raise ConsultantVerificationError(
            "context receipt does not match the resolved execution"
        )
    if receipt.total_input_tokens > execution.max_context_tokens:
        raise ConsultantVerificationError("context exceeded its resolved token budget")
    if not set(receipt.selected_skill_ids) <= set(execution.allowed_skill_ids):
        raise ConsultantVerificationError("context loaded an ineligible Skill")
    source_ids = [item.source_id for item in receipt.loaded_sources]
    if len(source_ids) != len(set(source_ids)):
        raise ConsultantVerificationError("context loaded a source more than once")


def verify_model_attempts(
    execution: ResolvedExecution,
    receipts: Sequence[AttemptReceipt],
) -> None:
    if not receipts:
        raise ConsultantVerificationError("model-bearing run has no attempt receipt")
    attempt_ids = [receipt.attempt_id for receipt in receipts]
    if len(attempt_ids) != len(set(attempt_ids)):
        raise ConsultantVerificationError("model attempt receipt ID was reused")
    if len({receipt.product_run_id for receipt in receipts}) != 1:
        raise ConsultantVerificationError("model attempts span more than one product run")
    for receipt in receipts:
        if (
            receipt.requested_model != execution.requested_model
            or receipt.provider_allowlist != execution.provider_allowlist
            or receipt.profile_id != execution.profile_id
            or receipt.profile_revision != execution.profile_revision
            or receipt.policy_id != execution.policy_id
            or receipt.policy_revision != execution.policy_revision
            or receipt.effective_parameters != execution.effective_parameters
        ):
            raise ConsultantVerificationError(
                "model attempt receipt does not match the resolved execution"
            )
        if receipt.status is AttemptStatus.SUCCEEDED:
            if not receipt.actual_model or not receipt.actual_provider:
                raise ConsultantVerificationError(
                    "successful model attempt is missing its actual route"
                )
            if receipt.usage.total_tokens is None:
                raise ConsultantVerificationError(
                    "successful model attempt is missing provider usage"
                )
            if execution.max_cost_usd is not None and receipt.cost_usd is None:
                raise ConsultantVerificationError(
                    "successful model attempt is missing provider cost"
                )
    verify_attempt_budget(execution, receipts)
