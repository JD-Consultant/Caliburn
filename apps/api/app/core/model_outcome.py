"""Provider-neutral operation and provider-call outcome types.

`ProviderFailureKind`／`ProviderText`／`ProviderRefusal`／`ProviderFailure`／
`ProviderOutcome` are the OpenRouter adapter's boundary types(T5):one HTTP call's
every possible ending comes back as one of these typed values, and the adapter
imports nothing provider-specific beyond them.

`OperationOutcome` is the terminal result shared by every one-stage model operation
(§9.5). `task_analysis`（`operation.py`）、`opks`（`opks_operation.py`／
`opks_generation.py`）與 `consultation`（`durable_turn.py`）都直接消費同一個值域,
因此放在 core 而非任一 feature(ADR 0058 規則 7)。
"""

from __future__ import annotations

from enum import StrEnum

from app.core.domain import DomainModel, NonEmptyText


class ProviderFailureKind(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    HTTP_STATUS = "http_status"
    PROVIDER_ERROR = "provider_error"
    MALFORMED_RESPONSE = "malformed_response"
    MODEL_MISMATCH = "model_mismatch"
    TRUNCATED = "truncated"


class ProviderText(DomainModel):
    text: NonEmptyText


class ProviderRefusal(DomainModel):
    """模型拒答。這不是錯誤,也不得被當成可重試的失敗。"""

    message: str = ""


class ProviderFailure(DomainModel):
    kind: ProviderFailureKind
    detail: NonEmptyText


ProviderOutcome = ProviderText | ProviderRefusal | ProviderFailure


class OperationOutcome(StrEnum):
    VERIFIED = "verified"
    """通過 verifier;可以交給 transition service 套用。"""

    REJECTED = "rejected"
    """parse 得出來,但違反確定性規則(§9.5／§12.3);不得套用。"""

    INVALID_OUTPUT = "invalid_output"
    """不是合法的 wire JSON,或還原不成 domain 契約。"""

    REFUSED = "refused"
    """模型拒答。不是錯誤,也不是可重試的失敗。"""

    FAILED = "failed"
    """provider 端失敗(timeout／連線／非 200／截斷)。"""
