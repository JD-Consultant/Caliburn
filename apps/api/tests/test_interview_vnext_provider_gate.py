"""R3-C2:application provider gate 的 typed cross-artifact 驗證(修正計畫 §5.4/§6.4)。

一個 persisted provider gate = request + binding + result/evidence/conformance
三件 inline artifact。durable write 與每個 fresh-process recovery 分支共用
`validate_provider_gate_artifacts()`;任何 tamper/漂移都必須 fail closed
(`PersistedDataCorruption`),不得只因欄位「看起來都有」就放行。
"""

from __future__ import annotations

import pytest

from app.interview_vnext.application.provider_gate import (
    ValidatedProviderGate,
    require_result_identity,
    validate_provider_gate_artifacts,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.llm.conformance import (
    ConformanceReasonCode,
    ConformanceReport,
    ConformanceReportDefinition,
)
from app.interview_vnext.llm.result import (
    FailureKind,
    FinishReason,
    ModelFailure,
    ModelOutcome,
    TokenUsage,
)
from app.interview_vnext.llm.testing import scripted_turn_binding
from app.interview_vnext.persistence.errors import PersistedDataCorruption

from tests.interview_vnext_llm_fixtures import (
    GateRecords,
    scripted_gate_records,
    scripted_model_request,
    unknown_execution_evidence,
)


BINDING = scripted_turn_binding()


def build_gate(
    name: str, *, outcome: ModelOutcome = ModelOutcome.SUCCEEDED, **overrides
):
    request = scripted_model_request(name=name)
    return request, scripted_gate_records(
        request, BINDING, outcome=outcome, **overrides
    )


def validate(request, gate: GateRecords, *, require_eligible):
    return validate_provider_gate_artifacts(
        request=request,
        binding=BINDING,
        result_artifact=gate.result_record,
        evidence_artifact=gate.evidence_record,
        conformance_artifact=gate.conformance_record,
        require_eligible=require_eligible,
    )


def forged_report(report: ConformanceReport, **overrides) -> ConformanceReport:
    definition = ConformanceReportDefinition.model_validate(
        {**report.model_dump(exclude={"report_hash"}), **overrides}
    )
    return ConformanceReport(
        **definition.model_dump(), report_hash=canonical_hash(definition)
    )


# ── 合法 gate ────────────────────────────────────────────────────────────────


def test_clean_succeeded_gate_validates_and_returns_typed_models():
    request, gate = build_gate("clean-success")
    validated = validate(request, gate, require_eligible=True)
    assert isinstance(validated, ValidatedProviderGate)
    assert validated.result == gate.result
    assert validated.evidence == gate.evidence
    assert validated.conformance == gate.conformance
    assert validated.conformance.eligible is True


def test_wire_failure_gate_validates_with_wire_not_succeeded():
    request, gate = build_gate("wire-failure", outcome=ModelOutcome.FAILED)
    validated = validate(request, gate, require_eligible=False)
    assert validated.conformance.eligible is False
    assert (
        ConformanceReasonCode.WIRE_NOT_SUCCEEDED in validated.conformance.reason_codes
    )


def test_require_eligible_true_rejects_an_ineligible_gate():
    request, gate = build_gate("must-be-eligible", outcome=ModelOutcome.FAILED)
    with pytest.raises(PersistedDataCorruption, match="eligible"):
        validate(request, gate, require_eligible=True)


def test_require_eligible_false_rejects_an_eligible_gate():
    request, gate = build_gate("must-be-ineligible")
    with pytest.raises(PersistedDataCorruption, match="eligible"):
        validate(request, gate, require_eligible=False)


def test_require_eligible_none_accepts_either_verdict():
    request, gate = build_gate("either-success")
    assert validate(request, gate, require_eligible=None).conformance.eligible
    request, gate = build_gate("either-failure", outcome=ModelOutcome.FAILED)
    assert not validate(request, gate, require_eligible=None).conformance.eligible


# ── §7.3.7–§7.3.10:typed 交叉驗證 ───────────────────────────────────────────


def test_evidence_bound_to_another_binding_is_rejected():
    """§7.3.7:evidence 的 binding hash 與 result 不同。"""

    foreign = scripted_turn_binding(binding_id="turn-interpret-foreign")
    foreign = foreign.model_copy(
        update={"binding_hash": foreign.binding_hash}
    )  # 明確:同定義、不同 binding_id → 不同 hash
    request = scripted_model_request(name="evidence-foreign")
    tampered_evidence = unknown_execution_evidence(foreign)
    gate = scripted_gate_records(
        request,
        BINDING,
        outcome=ModelOutcome.FAILED,
        evidence_override=tampered_evidence,
    )
    with pytest.raises(PersistedDataCorruption, match="binding|evidence"):
        validate(request, gate, require_eligible=False)


def test_report_evidence_hash_drift_is_rejected():
    """§7.3.8:report 的 evidence hash 與 evidence 不同(自我 hash 合法)。"""

    request = scripted_model_request(name="report-evidence-drift")
    base = scripted_gate_records(request, BINDING)
    gate = scripted_gate_records(
        request,
        BINDING,
        conformance_override=forged_report(
            base.conformance, execution_evidence_hash="sha256:" + "9" * 64
        ),
    )
    with pytest.raises(PersistedDataCorruption, match="evidence"):
        validate(request, gate, require_eligible=True)


def test_report_wire_outcome_drift_is_rejected():
    """§7.3.9:report 的 wire outcome 與 result 不同(自我 hash 合法)。"""

    request = scripted_model_request(name="report-outcome-drift")
    base = scripted_gate_records(request, BINDING)
    gate = scripted_gate_records(
        request,
        BINDING,
        conformance_override=forged_report(
            base.conformance,
            wire_outcome=ModelOutcome.FAILED,
            eligible=False,
            reason_codes=(ConformanceReasonCode.WIRE_NOT_SUCCEEDED,),
        ),
    )
    with pytest.raises(PersistedDataCorruption, match="wire|outcome"):
        validate(request, gate, require_eligible=True)


def test_self_consistent_but_not_reevaluated_report_is_rejected():
    """§7.3.10:合法自我 hash、但不等於 deterministic re-evaluation。"""

    request = scripted_model_request(name="report-not-reevaluated")
    base = scripted_gate_records(request, BINDING)
    gate = scripted_gate_records(
        request,
        BINDING,
        conformance_override=forged_report(
            base.conformance,
            eligible=False,
            reason_codes=(ConformanceReasonCode.CACHE_INELIGIBLE,),
        ),
    )
    with pytest.raises(PersistedDataCorruption, match="re-evaluat|equal"):
        validate(request, gate, require_eligible=None)


def test_wire_failure_report_missing_wire_not_succeeded_is_rejected():
    """§5.5:wire failure 的 persisted conformance 必含 wire_not_succeeded。"""

    request = scripted_model_request(name="missing-wire-reason")
    base = scripted_gate_records(request, BINDING, outcome=ModelOutcome.FAILED)
    gate = scripted_gate_records(
        request,
        BINDING,
        outcome=ModelOutcome.FAILED,
        conformance_override=forged_report(
            base.conformance,
            reason_codes=(ConformanceReasonCode.CACHE_INELIGIBLE,),
        ),
    )
    with pytest.raises(PersistedDataCorruption):
        validate(request, gate, require_eligible=False)


# ── §7.3.11:kind/schema/scope/attempt exact ────────────────────────────────


def _rebuild_record(record, **ref_overrides):
    from app.interview_vnext.observability.artifacts import ArtifactRecord

    payload = record.model_dump()
    payload["ref"] = {**payload["ref"], **ref_overrides}
    return ArtifactRecord.model_validate(payload)


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("kind", "model.request", "kind"),
        ("schema_id", "https://caliburn.local/schemas/unknown.v1.schema.json", "schema"),
        ("schema_id", None, "schema"),
    ],
)
def test_wrong_result_artifact_kind_or_schema_is_rejected(field, value, match):
    request, gate = build_gate("wrong-result-meta")
    tampered = GateRecords(
        result=gate.result,
        evidence=gate.evidence,
        conformance=gate.conformance,
        result_record=_rebuild_record(gate.result_record, **{field: value}),
        evidence_record=gate.evidence_record,
        conformance_record=gate.conformance_record,
    )
    with pytest.raises(PersistedDataCorruption, match=match):
        validate(request, tampered, require_eligible=True)


def test_foreign_attempt_scope_is_rejected():
    request, _ = build_gate("scope-owner")
    foreign_request = scripted_model_request(name="scope-foreign")
    foreign_gate = scripted_gate_records(foreign_request, BINDING)
    with pytest.raises(PersistedDataCorruption, match="scope|attempt"):
        validate(request, foreign_gate, require_eligible=True)


def test_result_identity_mismatch_with_request_is_rejected():
    # 另一個 request 的 gate:先被 artifact scope 檢查擋(同屬 §5.4 fail closed)。
    request, gate = build_gate("identity-owner")
    other_request = scripted_model_request(name="identity-other", attempt=2)
    with pytest.raises(PersistedDataCorruption, match="scope|identity"):
        validate_provider_gate_artifacts(
            request=other_request,
            binding=BINDING,
            result_artifact=gate.result_record,
            evidence_artifact=gate.evidence_record,
            conformance_artifact=gate.conformance_record,
            require_eligible=True,
        )


# ── §7.1 防放寬:gateway 漂移只有 runtime_binding_mismatch 可解釋 ───────────


def _gateway_drift_gate(name: str, *, failure_kind: FailureKind):
    """result/evidence 的 gateway 都是 runtime 'openrouter',binding 是 scripted。"""

    request = scripted_model_request(name=name)
    usage = TokenUsage(limitations=("no provider usage available",))
    base = scripted_gate_records(request, BINDING, outcome=ModelOutcome.FAILED)
    drift_result = base.result.model_copy(
        update={
            "gateway_provider": "openrouter",
            "failure": ModelFailure(
                kind=failure_kind,
                reason_code="openrouter.binding_invalid"
                if failure_kind == FailureKind.RUNTIME_BINDING_MISMATCH
                else "provider.timeout",
                retryable=failure_kind != FailureKind.RUNTIME_BINDING_MISMATCH,
                safe_message="The model request does not match the approved eval configuration."
                if failure_kind == FailureKind.RUNTIME_BINDING_MISMATCH
                else "Provider timed out.",
            ),
            "finish_reason": FinishReason.PROVIDER_ERROR,
            "usage": usage,
        }
    )
    drift_evidence = unknown_execution_evidence(BINDING).model_copy(
        update={
            "gateway_provider": "openrouter",
            "adapter_id": "openrouter.chat-completions",
            "adapter_version": "2.0.0",
            "usage": usage,
        }
    )
    # model_copy 不重算 hash:重建 evidence 讓自我 hash 合法。
    from app.interview_vnext.llm.execution import (
        ProviderExecutionEvidenceDefinition,
        define_provider_execution_evidence,
    )

    drift_evidence = define_provider_execution_evidence(
        **ProviderExecutionEvidenceDefinition.model_validate(
            drift_evidence.model_dump(exclude={"evidence_hash"})
        ).model_dump()
    )
    from app.interview_vnext.llm.result import ModelCallResult

    drift_result = ModelCallResult.model_validate(drift_result.model_dump())
    return request, scripted_gate_records(
        request,
        BINDING,
        outcome=ModelOutcome.FAILED,
        result_override=drift_result,
        evidence_override=drift_evidence,
    )


def test_gateway_drift_with_runtime_binding_mismatch_kind_is_accepted():
    """§5.1.1:唯一允許 result/evidence gateway 與 binding 不同的 failure kind。"""

    request, gate = _gateway_drift_gate(
        "drift-mismatch", failure_kind=FailureKind.RUNTIME_BINDING_MISMATCH
    )
    validated = validate(request, gate, require_eligible=False)
    assert validated.result.gateway_provider == "openrouter"
    assert validated.evidence.gateway_provider == "openrouter"


def test_gateway_drift_with_any_other_failure_kind_is_rejected():
    """§7.1 防放寬:不能因 outcome=failed 一律放行 gateway 漂移。"""

    request, gate = _gateway_drift_gate(
        "drift-timeout", failure_kind=FailureKind.TRANSPORT_TIMEOUT
    )
    with pytest.raises(PersistedDataCorruption, match="gateway"):
        validate(request, gate, require_eligible=False)


def test_require_result_identity_rejects_gateway_drift_without_mismatch_kind():
    request, gate = _gateway_drift_gate(
        "identity-drift-timeout", failure_kind=FailureKind.TRANSPORT_TIMEOUT
    )
    with pytest.raises(PersistedDataCorruption, match="gateway"):
        require_result_identity(request, gate.result, binding=BINDING)
