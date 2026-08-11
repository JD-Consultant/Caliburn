"""單一 Task 的 one-stage OPKS model operation。"""

from __future__ import annotations

from pydantic import ValidationError

from app.core.domain import DomainModel, NonEmptyText
from app.core.model_outcome import (
    OperationOutcome,
    ProviderFailure,
    ProviderRefusal,
    ProviderText,
)

from .context import OpksContextPacket, render_opks_context_packet
from .llm import (
    OPKS_INSTRUCTIONS,
    OPKS_RESULT_WIRE_SCHEMA_NAME,
    OpksResult,
    OpksResultWire,
    opks_result_wire_provider_schema,
    opks_wire_to_result,
)
from .ports import OpksModelPort
from .verifier import OpksVerificationReport, verify_opks_result


class OpksOperationResult(DomainModel):
    outcome: OperationOutcome
    result: OpksResult | None = None
    report: OpksVerificationReport | None = None
    detail: NonEmptyText | None = None

    @property
    def is_applicable(self) -> bool:
        return self.outcome is OperationOutcome.VERIFIED


async def run_opks_operation(
    *,
    packet: OpksContextPacket,
    adapter: OpksModelPort,
    operation_id: str,
) -> OpksOperationResult:
    provider_outcome = await adapter.complete(
        instructions=OPKS_INSTRUCTIONS,
        packet_text=render_opks_context_packet(packet),
        schema_name=OPKS_RESULT_WIRE_SCHEMA_NAME,
        schema=opks_result_wire_provider_schema(),
    )
    if isinstance(provider_outcome, ProviderFailure):
        return OpksOperationResult(
            outcome=OperationOutcome.FAILED,
            detail=f"{provider_outcome.kind.value}: {provider_outcome.detail}",
        )
    if isinstance(provider_outcome, ProviderRefusal):
        return OpksOperationResult(
            outcome=OperationOutcome.REFUSED,
            detail=provider_outcome.message or "the model declined this request",
        )

    assert isinstance(provider_outcome, ProviderText)
    try:
        result = opks_wire_to_result(
            OpksResultWire.model_validate_json(provider_outcome.text)
        )
    except ValidationError as error:
        return OpksOperationResult(
            outcome=OperationOutcome.INVALID_OUTPUT,
            detail=(
                f"output did not match {OPKS_RESULT_WIRE_SCHEMA_NAME}: "
                f"{error.error_count()} error(s)"
            ),
        )

    report = verify_opks_result(
        packet,
        result,
        operation_id=operation_id,
    )
    return OpksOperationResult(
        outcome=(
            OperationOutcome.VERIFIED
            if report.is_valid
            else OperationOutcome.REJECTED
        ),
        result=result,
        report=report,
    )
