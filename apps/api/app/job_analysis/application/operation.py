"""One-stage Task Analysis operation(T5)。

組 packet → 呼叫 → parse → 交給 verifier 的**單一顯式流程**,不是通用 agent runner:
沒有 tool loop、沒有 planner、沒有 retry。每種結局都有名字,呼叫端(T6)照名字處置。

provider 只收 `render_context_packet()` 的文字與 committed 的 provider schema。
packet 的內部模型從來沒有離開這一層——`adapter.complete()` 的簽章根本收不到它,
所以 task_id／turn_id／issue_id 不會外洩到 provider。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import ValidationError

from app.core.domain import DomainModel, NonEmptyText
from app.job_analysis.llm import (
    TASK_ANALYSIS_WIRE_SCHEMA_NAME,
    TaskAnalysisResult,
    TaskAnalysisWire,
    WireMappingError,
    task_analysis_wire_provider_schema,
    wire_to_task_analysis_result,
)
from app.job_analysis.llm.prompt import TASK_ANALYSIS_INSTRUCTIONS
from app.job_analysis.providers import (
    OpenRouterAdapter,
    ProviderFailure,
    ProviderRefusal,
    ProviderText,
)

from .context import TaskAnalysisPacket, render_context_packet
from .verifier import VerificationReport, verify_task_analysis_result


class OperationOutcome(StrEnum):
    VERIFIED = "verified"
    """通過 verifier;可以交給 transition service 套用。"""

    REJECTED = "rejected"
    """parse 得出來,但違反確定性規則(§9.5／§12.3);不得套用。"""

    INVALID_OUTPUT = "invalid_output"
    """不是合法的 `task_analysis_result.v2` JSON,或還原不成 domain 契約。"""

    REFUSED = "refused"
    """模型拒答。不是錯誤,也不是可重試的失敗。"""

    FAILED = "failed"
    """provider 端失敗(timeout／連線／非 200／截斷)。"""


class TaskAnalysisOperationResult(DomainModel):
    outcome: OperationOutcome
    result: TaskAnalysisResult | None = None
    report: VerificationReport | None = None
    detail: NonEmptyText | None = None

    @property
    def is_applicable(self) -> bool:
        return self.outcome is OperationOutcome.VERIFIED


async def run_task_analysis_operation(
    *, packet: TaskAnalysisPacket, adapter: OpenRouterAdapter
) -> TaskAnalysisOperationResult:
    outcome = await adapter.complete(
        instructions=TASK_ANALYSIS_INSTRUCTIONS,
        packet_text=render_context_packet(packet),
        schema_name=TASK_ANALYSIS_WIRE_SCHEMA_NAME,
        schema=task_analysis_wire_provider_schema(),
    )

    if isinstance(outcome, ProviderFailure):
        return TaskAnalysisOperationResult(
            outcome=OperationOutcome.FAILED,
            detail=f"{outcome.kind.value}: {outcome.detail}",
        )
    if isinstance(outcome, ProviderRefusal):
        return TaskAnalysisOperationResult(
            outcome=OperationOutcome.REFUSED,
            detail=outcome.message or "the model declined this request",
        )

    assert isinstance(outcome, ProviderText)
    try:
        result = wire_to_task_analysis_result(
            TaskAnalysisWire.model_validate_json(outcome.text)
        )
    except ValidationError as error:
        return TaskAnalysisOperationResult(
            outcome=OperationOutcome.INVALID_OUTPUT,
            detail=(
                f"output did not match {TASK_ANALYSIS_WIRE_SCHEMA_NAME}: "
                f"{error.error_count()} error(s)"
            ),
        )
    except WireMappingError as error:
        return TaskAnalysisOperationResult(
            outcome=OperationOutcome.INVALID_OUTPUT, detail=str(error)
        )

    report = verify_task_analysis_result(result, packet.verification_context())
    return TaskAnalysisOperationResult(
        outcome=(
            OperationOutcome.VERIFIED if report.is_valid else OperationOutcome.REJECTED
        ),
        result=result,
        report=report,
    )
