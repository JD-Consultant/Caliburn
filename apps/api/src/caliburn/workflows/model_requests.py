"""Coordinate existing execution budgets with direct model I/O; no response storage here."""

import json
from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from uuid import UUID, uuid4

from openai import AsyncOpenAI
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_responses import (
    ResponseRequest,
    compact_context,
    compaction_payload,
    count_response_input,
    create_response,
)
from caliburn.agent_execution.context_compaction import ReceivedCompaction
from caliburn.agent_execution.request_capacity import ReceivedInputCount
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
    token_count_reservation_usd: Decimal | None = None
    compaction_reservation_usd: Decimal | None = None
    observed_compaction_cost: Callable[[CompactedResponse], Decimal | None] | None = None

    def __post_init__(self) -> None:
        validate_cost(self.reserved_cost_usd, positive=True)
        if self.token_count_reservation_usd is not None:
            validate_cost(self.token_count_reservation_usd, positive=True)
        if self.compaction_reservation_usd is not None:
            validate_cost(self.compaction_reservation_usd, positive=True)
        if not self.cost_basis.strip():
            raise ValueError("An explicit cost basis is required")


class PriorModelAttemptError(RuntimeError):
    """The logical request has a prior send; reconcile it rather than blindly sending again."""


class ModelUsageUnavailableError(RuntimeError):
    """Keep the original reservation when no reliable observed cost can be calculated."""


class PriorInputCountAttemptError(RuntimeError):
    """Reconcile the original counting attempt; do not blindly repeat a remote count."""


class PriorCompactionAttemptError(RuntimeError):
    """Reconcile the original compaction attempt; an admission never permits a resend."""


@dataclass(frozen=True, slots=True)
class ModelRequestExecutor:
    sessions: async_sessionmaker[AsyncSession]
    writer: ExecutionWriter
    client: AsyncOpenAI
    accounting: ModelRequestAccounting

    async def request_model(
        self, request: ResponseRequest, request_id: UUID
    ) -> ReceivedModelResponse:
        attempt_id = await self._reserve_request(
            request_id,
            OutboundKind.MODEL,
            request.create_payload(),
            self.accounting.reserved_cost_usd,
        )
        response = await create_response(self.client, request)
        # No DB or cost calculation after the HTTP await: hand intact R to Graph first.
        return ReceivedModelResponse(response, attempt_id)

    async def count_input(self, request: ResponseRequest, request_id: UUID) -> ReceivedInputCount:
        reservation = self.accounting.token_count_reservation_usd
        if reservation is None:
            raise ValueError("Configure a positive reservation before remote token counting")
        attempt_id = await self._reserve_request(
            request_id, OutboundKind.TOKEN_COUNT, request.count_payload(), reservation
        )
        response = await count_response_input(self.client, request)
        # Counting provides no billing usage. Keep the administrative reservation unknown,
        # and persist the returned count before capacity interpretation or another HTTP call.
        return {"input_tokens": response.input_tokens, "attempt_id": attempt_id}

    async def request_compaction(
        self, request: ResponseRequest, request_id: UUID
    ) -> ReceivedCompaction:
        reservation = self.accounting.compaction_reservation_usd
        if reservation is None or self.accounting.observed_compaction_cost is None:
            raise ValueError("Configure an explicit compaction reservation and cost calculator")
        context = request.count_payload()
        payload = compaction_payload(model=context["model"], input_items=context["input"])
        attempt_id = await self._reserve_request(
            request_id,
            OutboundKind.COMPACTION,
            payload,
            reservation,
        )
        response = await compact_context(
            self.client, model=payload["model"], input_items=payload["input"]
        )
        # Hand intact C to Graph before any DB work or fallible cost calculation.
        return ReceivedCompaction(response, attempt_id)

    async def _reserve_request(
        self,
        request_id: UUID,
        kind: OutboundKind,
        request_payload: dict[str, object],
        reservation: Decimal,
    ) -> UUID:
        payload = json.dumps(
            request_payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
        outbound = OutboundRequest(request_id, kind, sha256(payload.encode("utf-8")).hexdigest())
        prior_error = {
            OutboundKind.MODEL: PriorModelAttemptError,
            OutboundKind.TOKEN_COUNT: PriorInputCountAttemptError,
            OutboundKind.COMPACTION: PriorCompactionAttemptError,
        }[kind]
        attempt_id = uuid4()
        async with self.sessions.begin() as session:
            # Same-request competitors serialize here. No Python lock or HTTP transaction.
            await service.lock_active_writer(session, self.writer)
            await self._require_cost_basis(session)
            prior = await budgets.read_request_attempts(session, self.writer.scope, request_id)
            if any(attempt.request != outbound for attempt in prior):
                raise BudgetConflictError("An outbound request cannot change its saved payload")
            if prior:
                raise prior_error("Reconcile the original outbound attempt before retrying")
            admission = await budgets.reserve_outbound_attempt(
                session,
                self.writer,
                request=outbound,
                attempt_id=attempt_id,
                reserved_cost_usd=reservation,
            )
        # This line is reached only after COMMIT acknowledgement. Lost acknowledgement
        # raises above; the saved request ID lets recovery find the reservation, not resend.
        if not admission.created:
            raise prior_error("An existing admission does not permit another send")
        return attempt_id

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

    async def account_compaction(self, received: ReceivedCompaction) -> None:
        """Settle saved C independently of eligibility to adopt its compacted window."""
        observed_cost = self.accounting.observed_compaction_cost
        if observed_cost is None:
            raise ValueError("Configure an explicit compaction cost calculator")
        cost = observed_cost(received.response)
        if cost is None:
            raise ModelUsageUnavailableError(
                "Original compaction usage is unavailable; retain the reservation"
            )
        async with self.sessions.begin() as session:
            await self._require_cost_basis(session)
            attempt = await budgets.read_outbound_attempt(
                session, self.writer.scope, received.attempt_id
            )
            if attempt is None or attempt.request.kind != OutboundKind.COMPACTION:
                raise BudgetConflictError("The compaction result has no matching admitted attempt")
            await budgets.record_attempt_cost(
                session, self.writer.scope, received.attempt_id, cost_usd=cost
            )

    async def _require_cost_basis(self, session: AsyncSession) -> None:
        policy = await budgets.read_execution_budget(session, self.writer.scope)
        if policy is None or policy.cost_basis != self.accounting.cost_basis:
            raise BudgetConflictError("The accounting policy does not match this execution")
