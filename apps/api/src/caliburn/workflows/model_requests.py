"""Coordinate existing execution budgets with direct model I/O; no response storage here."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from openai import AsyncOpenAI
from openai.types.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_responses import ResponseRequest, create_response
from caliburn.agent_execution.tool_steps import ReceivedModelResponse
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    OutboundKind,
    OutboundRequest,
    validate_cost,
)
from caliburn.features.executions.models import ExecutionWriter


@dataclass(frozen=True, slots=True)
class ModelRequestAccounting:
    """Explicit per-work cost policy, not a claim about provider billing precision."""

    cost_basis: str
    reserved_cost_usd: Decimal
    observed_cost: Callable[[Response], Decimal | None]

    def __post_init__(self) -> None:
        validate_cost(self.reserved_cost_usd, positive=True)
        if not self.cost_basis.strip():
            raise ValueError("An explicit cost basis is required")


class PriorModelAttemptError(RuntimeError):
    """The logical request has a prior send; reconcile it rather than blindly sending again."""


class ModelUsageUnavailableError(RuntimeError):
    """Keep the original reservation when no reliable observed cost can be calculated."""


@dataclass(frozen=True, slots=True)
class ModelRequestExecutor:
    sessions: async_sessionmaker[AsyncSession]
    writer: ExecutionWriter
    client: AsyncOpenAI
    accounting: ModelRequestAccounting

    async def request_model(
        self, request: ResponseRequest, request_id: UUID
    ) -> ReceivedModelResponse:
        payload = json.dumps(
            request.create_payload(),
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        outbound = OutboundRequest(
            request_id, OutboundKind.MODEL, sha256(payload.encode("utf-8")).hexdigest()
        )
        attempt_id = uuid4()
        async with self.sessions.begin() as session:
            # Same-request competitors serialize here. No Python lock or HTTP transaction.
            await service.lock_active_writer(session, self.writer)
            await self._require_cost_basis(session)
            prior = await budgets.read_request_attempts(session, self.writer.scope, request_id)
            if any(attempt.request != outbound for attempt in prior):
                raise BudgetConflictError("A model request cannot change its saved payload")
            if prior:
                raise PriorModelAttemptError("Reconcile the original model attempt before retrying")
            admission = await budgets.reserve_outbound_attempt(
                session,
                self.writer,
                request=outbound,
                attempt_id=attempt_id,
                reserved_cost_usd=self.accounting.reserved_cost_usd,
            )
        # This line is reached only after COMMIT acknowledgement. Lost acknowledgement
        # raises above; the saved request ID lets recovery find the reservation, not resend.
        if not admission.created:
            raise PriorModelAttemptError("An existing admission does not permit another send")
        response = await create_response(self.client, request)
        # No DB or cost calculation after the HTTP await: hand intact R to Graph first.
        return ReceivedModelResponse(response, attempt_id)

    async def account_response(self, received: ReceivedModelResponse) -> None:
        """Settle the original attempt even if its writer is no longer eligible to adopt R."""
        cost = self.accounting.observed_cost(received.response)
        if cost is None:
            raise ModelUsageUnavailableError(
                "Original usage is unavailable; retain the reservation"
            )
        async with self.sessions.begin() as session:
            await self._require_cost_basis(session)
            attempt = await budgets.read_outbound_attempt(
                session, self.writer.scope, received.attempt_id
            )
            if attempt is None or attempt.request.kind != OutboundKind.MODEL:
                raise BudgetConflictError("The model result has no matching admitted attempt")
            await budgets.record_attempt_cost(
                session, self.writer.scope, received.attempt_id, cost_usd=cost
            )

    async def _require_cost_basis(self, session: AsyncSession) -> None:
        policy = await budgets.read_execution_budget(session, self.writer.scope)
        if policy is None or policy.cost_basis != self.accounting.cost_basis:
            raise BudgetConflictError("The accounting policy does not match this execution")
