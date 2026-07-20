"""Application-owned provider gate validation authority(R3-C2;修正計畫 §5.4/§6.4)。

一個 persisted provider gate 由 request、binding 與三件 inline artifact
(result → ``ModelCallResult.v2``、evidence → ``ProviderExecutionEvidence.v1``、
conformance → ``ConformanceReport.v1``)組成。durable write 與每個 fresh-process
recovery 分支共用 ``validate_provider_gate_artifacts()``:typed 解析、identity
交叉、conformance 重新評估與 eligibility 檢查全部 fail closed
(``PersistedDataCorruption``)。本 module 不做 I/O:不開 UoW、不打 provider、
不決定 retry budget、不 import evals。
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import ValidationError

from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.conformance import (
    ConformanceMismatch,
    ConformanceReasonCode,
    ConformanceReport,
    require_conformance_report,
    resolve_conformance_policy,
)
from app.interview_vnext.llm.execution import ProviderExecutionEvidence
from app.interview_vnext.llm.port import ModelCallRequest
from app.interview_vnext.llm.result import FailureKind, ModelCallResult, ModelOutcome
from app.interview_vnext.llm.schema_ids import (
    CONFORMANCE_SCHEMA_ID,
    EXECUTION_EVIDENCE_SCHEMA_ID,
    MODEL_RESULT_SCHEMA_ID,
)
from app.interview_vnext.observability.artifacts import ArtifactRecord, ArtifactStorage
from app.interview_vnext.persistence.errors import PersistedDataCorruption


RESULT_ARTIFACT_KIND = "model.result"
EVIDENCE_ARTIFACT_KIND = "model.provider_execution_evidence"
CONFORMANCE_ARTIFACT_KIND = "model.provider_conformance"


@dataclass(frozen=True)
class ValidatedProviderGate:
    result: ModelCallResult
    evidence: ProviderExecutionEvidence
    conformance: ConformanceReport


def _result_permits_foreign_gateway(result: ModelCallResult) -> bool:
    """§5.1.1:唯一允許 gateway 與 binding 不同的 exact failure kind。"""

    return (
        result.outcome == ModelOutcome.FAILED
        and result.failure is not None
        and result.failure.kind == FailureKind.RUNTIME_BINDING_MISMATCH
    )


def require_result_identity(
    request: ModelCallRequest,
    result: ModelCallResult,
    *,
    binding: ProviderBinding,
) -> None:
    """Result identity 對 request/binding 的 exact 驗證(單一 authority)。

    identity 欄位保留被嘗試的 request/binding;``gateway_provider`` 記實際
    runtime gateway,必須等於 binding gateway,唯一例外是
    ``runtime_binding_mismatch`` failure(不得用 ``outcome=FAILED`` 放寬)。
    """

    expected = (
        request.run_id,
        request.session_id,
        request.turn_id,
        request.operation_id,
        request.attempt_id,
        request.attempt,
        request.operation_name,
        request.operation_definition_hash,
        request.binding_id,
        request.binding_hash,
        request.requested_model,
        request.prompt_hash,
        request.output_schema_id,
        request.output_schema_hash,
        request.context_hash,
    )
    actual = (
        result.run_id,
        result.session_id,
        result.turn_id,
        result.operation_id,
        result.attempt_id,
        result.attempt,
        result.operation_name,
        result.operation_definition_hash,
        result.binding_id,
        result.binding_hash,
        result.requested_model,
        result.prompt_hash,
        result.output_schema_id,
        result.output_schema_hash,
        result.context_hash,
    )
    if actual != expected or result.started_at < request.created_at:
        raise PersistedDataCorruption(
            "model result identity does not match the request",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    if result.gateway_provider != binding.gateway_provider and not (
        _result_permits_foreign_gateway(result)
    ):
        raise PersistedDataCorruption(
            "model result gateway provider does not match the binding",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )


def _require_gate_record(
    record: ArtifactRecord,
    *,
    request: ModelCallRequest,
    kind: str,
    schema_id: str,
) -> str:
    """kind/schema/scope/attempt exact 且 inline JSON(§5.4);回 inline content。"""

    def reject(message: str) -> PersistedDataCorruption:
        return PersistedDataCorruption(
            message,
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
            artifact_id=record.ref.artifact_id,
        )

    if record.storage != ArtifactStorage.INLINE or record.inline_content is None:
        raise reject("provider gate artifact is not inline JSON")
    if record.ref.kind != kind:
        raise reject(
            f"provider gate artifact kind {record.ref.kind!r} is not {kind!r}"
        )
    if record.ref.schema_id != schema_id:
        raise reject(
            f"provider gate artifact schema {record.ref.schema_id!r} is not {schema_id!r}"
        )
    if (
        record.run_id != request.run_id
        or record.session_id != request.session_id
        or record.turn_id != request.turn_id
        or record.operation_id != request.operation_id
        or record.attempt_id != request.attempt_id
    ):
        raise reject("provider gate artifact scope does not match the request attempt")
    return record.inline_content


def validate_provider_gate_artifacts(
    *,
    request: ModelCallRequest,
    binding: ProviderBinding,
    result_artifact: ArtifactRecord,
    evidence_artifact: ArtifactRecord,
    conformance_artifact: ArtifactRecord,
    require_eligible: bool | None,
) -> ValidatedProviderGate:
    """§5.4 的 typed/cross-artifact 驗證(durable write 與 recovery 共用)。

    ``require_eligible``:``True``(success/provider-completed path)、``False``
    (terminal failure path)、``None``(retry 重驗,由 caller 的分類重驗把關)。
    """

    result_content = _require_gate_record(
        result_artifact,
        request=request,
        kind=RESULT_ARTIFACT_KIND,
        schema_id=MODEL_RESULT_SCHEMA_ID,
    )
    evidence_content = _require_gate_record(
        evidence_artifact,
        request=request,
        kind=EVIDENCE_ARTIFACT_KIND,
        schema_id=EXECUTION_EVIDENCE_SCHEMA_ID,
    )
    conformance_content = _require_gate_record(
        conformance_artifact,
        request=request,
        kind=CONFORMANCE_ARTIFACT_KIND,
        schema_id=CONFORMANCE_SCHEMA_ID,
    )
    try:
        result = ModelCallResult.model_validate_json(result_content)
        evidence = ProviderExecutionEvidence.model_validate_json(evidence_content)
        conformance = ConformanceReport.model_validate_json(conformance_content)
    except ValidationError as exc:
        raise PersistedDataCorruption(
            f"provider gate artifact failed typed validation: {exc.errors()[0]['msg']}",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        ) from exc

    require_result_identity(request, result, binding=binding)

    if (
        evidence.binding_id != result.binding_id
        or evidence.binding_hash != result.binding_hash
    ):
        raise PersistedDataCorruption(
            "execution evidence binding does not match the result",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    if evidence.requested_model != result.requested_model:
        raise PersistedDataCorruption(
            "execution evidence requested model does not match the result",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    # result/evidence gateway 永遠 exact 相等(§5.4);與 binding 的一致性已由
    # require_result_identity 依 §5.1.1 的唯一例外把關。
    if evidence.gateway_provider != result.gateway_provider:
        raise PersistedDataCorruption(
            "execution evidence gateway provider does not match the result",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    if (
        evidence.adapter_id != binding.adapter_id
        or evidence.adapter_version != binding.adapter_version
    ) and not _result_permits_foreign_gateway(result):
        raise PersistedDataCorruption(
            "execution evidence adapter identity does not match the binding",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )

    try:
        policy = resolve_conformance_policy(binding.conformance_policy)
        require_conformance_report(
            policy=policy,
            binding=binding,
            evidence=evidence,
            wire_outcome=result.outcome,
            report=conformance,
        )
    except ConformanceMismatch as exc:
        raise PersistedDataCorruption(
            str(exc),
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        ) from exc

    if result.outcome != ModelOutcome.SUCCEEDED and (
        ConformanceReasonCode.WIRE_NOT_SUCCEEDED not in conformance.reason_codes
    ):
        raise PersistedDataCorruption(
            "wire-failure conformance report is missing wire_not_succeeded",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    if require_eligible is True and not conformance.eligible:
        raise PersistedDataCorruption(
            "provider gate requires an eligible conformance report",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    if require_eligible is False and conformance.eligible:
        raise PersistedDataCorruption(
            "provider gate requires an ineligible conformance report",
            operation_id=request.operation_id,
            attempt_id=request.attempt_id,
        )
    return ValidatedProviderGate(
        result=result, evidence=evidence, conformance=conformance
    )
