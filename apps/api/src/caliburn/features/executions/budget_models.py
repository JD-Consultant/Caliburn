"""Per-work outbound limits and immutable request bindings; no model payloads or credentials."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID


class OutboundKind(StrEnum):
    MODEL = "model"
    COMPACTION = "compaction"
    TOKEN_COUNT = "token_count"


class BudgetLimit(StrEnum):
    DEADLINE = "deadline"
    OUTBOUND_ATTEMPTS = "outbound_attempts"
    MODEL_STEPS = "model_steps"
    COMPACTIONS = "compactions"
    REQUEST_ATTEMPTS = "request_attempts"
    COST = "cost"


class BudgetExceededError(RuntimeError):
    def __init__(self, limit: BudgetLimit) -> None:
        self.limit = limit
        super().__init__(f"Execution budget exhausted: {limit.value}")


class BudgetConflictError(RuntimeError):
    """A saved policy, request binding, cost or failure cannot be replaced."""


def validate_cost(cost_usd: Decimal, *, positive: bool = False) -> None:
    if (
        not cost_usd.is_finite()
        or cost_usd < 0
        or (positive and cost_usd == 0)
        or cost_usd >= Decimal("1000000000")
        or cost_usd != cost_usd.quantize(Decimal("0.000000001"))
    ):
        raise ValueError("Cost must be finite USD with at most nine decimal places")


@dataclass(frozen=True, slots=True)
class ExecutionBudget:
    max_model_steps: int
    max_compactions: int
    max_outbound_attempts: int
    max_attempts_per_request: int
    deadline_at: datetime
    max_cost_usd: Decimal | None
    cost_basis: str

    def __post_init__(self) -> None:
        for value in (
            self.max_model_steps,
            self.max_compactions,
            self.max_outbound_attempts,
            self.max_attempts_per_request,
        ):
            if type(value) is not int or value < 1:
                raise ValueError("Execution limits must be positive integers")
        if self.deadline_at.utcoffset() is None or not self.cost_basis.strip():
            raise ValueError("An aware deadline and explicit cost basis are required")
        if self.max_cost_usd is not None:
            validate_cost(self.max_cost_usd, positive=True)


@dataclass(frozen=True, slots=True)
class OutboundRequest:
    request_id: UUID
    kind: OutboundKind
    fingerprint: str

    def __post_init__(self) -> None:
        if len(self.fingerprint) != 64 or any(
            c not in "0123456789abcdef" for c in self.fingerprint
        ):
            raise ValueError("Use the SHA-256 of the exact outbound payload as request fingerprint")


# The provider asked us to slow down. Waiting for it is not a fault of the work, so these
# attempts do not spend the per-request attempt budget (the execution's deadline and overall
# attempt limit still end an endless wait).
RATE_LIMITED = "rate_limited"


@dataclass(frozen=True, slots=True)
class OutboundFailure:
    failure_code: str
    retry_not_before: datetime | None

    def __post_init__(self) -> None:
        if self.failure_code not in (
            "remote_result_unknown",
            "transient_service",
            RATE_LIMITED,
            "access_blocked",
            "capacity_exceeded",
            "request_rejected",
            "response_protocol",
        ):
            raise ValueError("Use a recognized outbound failure code without provider payloads")
        if self.retry_not_before is not None:
            if self.failure_code not in (
                "remote_result_unknown",
                "transient_service",
                RATE_LIMITED,
            ):
                raise ValueError("Only retryable outbound failures can carry a retry deadline")
            if self.retry_not_before.utcoffset() is None:
                raise ValueError("An outbound retry deadline must be timezone-aware")


@dataclass(frozen=True, slots=True)
class OutboundAttempt:
    attempt_id: UUID
    request: OutboundRequest
    writer_id: UUID
    reserved_cost_usd: Decimal
    reported_cost_usd: Decimal | None
    failure: OutboundFailure | None = None


@dataclass(frozen=True, slots=True)
class OutboundAdmission:
    attempt: OutboundAttempt
    created: bool


@dataclass(frozen=True, slots=True)
class BudgetUsage:
    outbound_attempts: int
    model_steps: int
    compactions: int
    accounted_cost_usd: Decimal
