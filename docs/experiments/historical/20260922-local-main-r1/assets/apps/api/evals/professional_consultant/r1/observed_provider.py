"""Eval-only scripted provider that preserves response-supplied facts."""

from __future__ import annotations

from app.professional_consultant.contracts import ShortText
from app.professional_consultant.runner import (
    ProviderCallError,
    StructuredOperationRequest,
    StructuredOperationResponse,
)

from .capture import (
    CapturedOperationInput,
    ProviderAttemptEvidence,
    ResolvedResponseFacts,
)
from .contracts import R1EvalModel


class ScriptedObservedSuccess(R1EvalModel):
    response: StructuredOperationResponse
    resolved: ResolvedResponseFacts


class ScriptedObservedFailure(R1EvalModel):
    safe_reason: ShortText


ScriptedObservedStep = ScriptedObservedSuccess | ScriptedObservedFailure


class ObservedScriptedProvider:
    """The only T3 fake boundary; it never derives resolved facts from request."""

    def __init__(
        self,
        *,
        requested_model: str,
        steps: tuple[ScriptedObservedStep, ...],
    ) -> None:
        self.requested_model = requested_model
        self._steps = steps
        self._index = 0
        self.operation_inputs: list[CapturedOperationInput] = []
        self.attempts: list[ProviderAttemptEvidence] = []

    async def generate(
        self, request: StructuredOperationRequest
    ) -> StructuredOperationResponse:
        call_index = len(self.operation_inputs) + 1
        self.operation_inputs.append(
            CapturedOperationInput(
                call_index=call_index,
                requested_model=self.requested_model,
                request=request,
            )
        )
        if self._index >= len(self._steps):
            raise AssertionError("observed scripted provider has no next step")
        step = self._steps[self._index]
        self._index += 1
        if isinstance(step, ScriptedObservedFailure):
            self.attempts.append(
                ProviderAttemptEvidence(
                    call_index=call_index,
                    status="provider_failed",
                    response=None,
                    resolved=None,
                )
            )
            raise ProviderCallError(step.safe_reason)
        self.attempts.append(
            ProviderAttemptEvidence(
                call_index=call_index,
                status="succeeded",
                response=step.response,
                resolved=step.resolved,
            )
        )
        return step.response
