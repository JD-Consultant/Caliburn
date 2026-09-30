"""Coordinate existing execution budgets with direct model I/O; no response storage here."""

import json
from asyncio import CancelledError, sleep
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from random import random
from uuid import UUID, uuid4

from openai import APIError, AsyncOpenAI
from openai.types.responses import Response
from openai.types.responses.compacted_response import CompactedResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_failures import ResponseFailure, classify_response_failure
from caliburn.adapters.openai_pricing import TextResponsePricing
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    compact_context,
    compaction_payload,
    count_response_input,
    create_response,
)
from caliburn.adapters.response_streaming import (
    PublicCommentaryUpdate,
    ResponseStreamCancelledError,
    ResponseStreamCleanupError,
)
from caliburn.agent_execution.context_compaction import ReceivedCompaction
from caliburn.agent_execution.request_capacity import ReceivedInputCount
from caliburn.agent_execution.response_retries import ResponseRetryPolicy
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    ReceivedModelResponseCancelledError,
    ReceivedModelResponseError,
)
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    BudgetLimit,
    ExecutionBudget,
    OutboundAttempt,
    OutboundFailure,
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
    model: str | None = None

    def __post_init__(self) -> None:
        validate_cost(self.reserved_cost_usd, positive=True)
        if self.token_count_reservation_usd is not None:
            validate_cost(self.token_count_reservation_usd, positive=True)
        if self.compaction_reservation_usd is not None:
            validate_cost(self.compaction_reservation_usd, positive=True)
        if not self.cost_basis.strip():
            raise ValueError("An explicit cost basis is required")
        if self.model is not None and not self.model.strip():
            raise ValueError("An explicit accounting model cannot be empty")

    @classmethod
    def from_text_pricing(
        cls,
        pricing: TextResponsePricing,
        *,
        reserved_cost_usd: Decimal,
        token_count_reservation_usd: Decimal | None = None,
        compaction_reservation_usd: Decimal | None = None,
    ) -> ModelRequestAccounting:
        """Bind the researched Standard rates; reserves remain explicit administrative limits."""
        return cls(
            cost_basis=pricing.cost_basis,
            reserved_cost_usd=reserved_cost_usd,
            observed_cost=pricing.estimate_response_cost,
            token_count_reservation_usd=token_count_reservation_usd,
            compaction_reservation_usd=compaction_reservation_usd,
            observed_compaction_cost=pricing.estimate_compaction_cost,
            model=pricing.model,
        )


class PriorAttemptRecovery(StrEnum):
    """App reconciliation of local originals, not a statement about remote billing."""

    ORIGINAL_AVAILABLE = "original_available"
    IN_FLIGHT_OR_UNKNOWN = "in_flight_or_unknown"
    LOCAL_ORIGINAL_UNRECOVERABLE = "local_original_unrecoverable"


class PriorOutboundAttemptError(RuntimeError):
    """Keep the original result/recovery route distinct from permission for a new send."""

    def __init__(
        self,
        message: str,
        *,
        attempts: tuple[OutboundAttempt, ...] = (),
        recovery: PriorAttemptRecovery = PriorAttemptRecovery.IN_FLIGHT_OR_UNKNOWN,
    ) -> None:
        self.attempts = attempts
        self.recovery = recovery
        super().__init__(message)


class PriorModelAttemptError(PriorOutboundAttemptError):
    """The logical request has a prior send; reconcile it rather than blindly sending again."""


class ModelUsageUnavailableError(RuntimeError):
    """Keep the original reservation when no reliable observed cost can be calculated."""


class ModelRequestFailedError(RuntimeError):
    """Safe Graph/log boundary; never retain provider bodies or the SDK exception as data."""

    def __init__(self, failure: ResponseFailure) -> None:
        self.failure = failure
        super().__init__(f"Outbound model request stopped: {failure.kind.value}")


class PriorInputCountAttemptError(PriorOutboundAttemptError):
    """Reconcile the original counting attempt; do not blindly repeat a remote count."""


class PriorCompactionAttemptError(PriorOutboundAttemptError):
    """Reconcile the original compaction attempt; an admission never permits a resend."""


class _RetryNotReadyError(Exception):
    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        super().__init__("The saved server/backoff delay has not elapsed")


@dataclass(frozen=True, slots=True)
class ModelRequestExecutor:
    sessions: async_sessionmaker[AsyncSession]
    writer: ExecutionWriter
    client: AsyncOpenAI
    accounting: ModelRequestAccounting
    retry_policy: ResponseRetryPolicy = ResponseRetryPolicy()
    # Trusted App-only seam. The owner must inspect native checkpoint/pending writes
    # and retained R/C/count handoffs, and establish the original producers are no
    # longer capable of returning a result before reporting UNRECOVERABLE. A writer
    # takeover, empty checkpoint, or acquired process lock alone is insufficient.
    # Consult outside DB locks; uncertain/failed checks must never authorize a send.
    reconcile_prior_attempts: (
        Callable[[ExecutionWriter, tuple[OutboundAttempt, ...]], Awaitable[PriorAttemptRecovery]]
        | None
    ) = None
    on_commentary: Callable[[PublicCommentaryUpdate], None] | None = None

    async def request_model(
        self, request: ResponseRequest, request_id: UUID
    ) -> ReceivedModelResponse:
        response, attempt_id = await self._send(
            request_id,
            OutboundKind.MODEL,
            request.create_payload(),
            self.accounting.reserved_cost_usd,
            lambda: create_response(self.client, request, on_commentary=self.on_commentary),
        )
        # No DB or cost calculation after the HTTP await: hand intact R to Graph first.
        return ReceivedModelResponse(response, attempt_id)

    async def count_input(self, request: ResponseRequest, request_id: UUID) -> ReceivedInputCount:
        reservation = self.accounting.token_count_reservation_usd
        if reservation is None:
            raise ValueError("Configure a positive reservation before remote token counting")
        response, attempt_id = await self._send(
            request_id,
            OutboundKind.TOKEN_COUNT,
            request.count_payload(),
            reservation,
            lambda: count_response_input(self.client, request),
        )
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
        response, attempt_id = await self._send(
            request_id,
            OutboundKind.COMPACTION,
            payload,
            reservation,
            lambda: compact_context(
                self.client, model=payload["model"], input_items=payload["input"]
            ),
        )
        # Hand intact C to Graph before any DB work or fallible cost calculation.
        return ReceivedCompaction(response, attempt_id)

    async def _send[T](
        self,
        request_id: UUID,
        kind: OutboundKind,
        payload: dict[str, object],
        reservation: Decimal,
        send: Callable[[], Awaitable[T]],
    ) -> tuple[T, UUID]:
        """One retry owner for local-function Responses/count/compact, never for tool effects.

        Caught transient failures use the existing retry policy. Unknown attempts stop
        unless the App explicitly establishes that their local originals are lost.
        """
        if self.accounting.model is not None and payload.get("model") != self.accounting.model:
            raise BudgetConflictError("The request model does not match its pinned pricing")
        reconciled = False
        unrecoverable: tuple[OutboundAttempt, ...] = ()
        while True:
            try:
                attempt_id = await self._reserve_request(
                    request_id, kind, payload, reservation, unrecoverable=unrecoverable
                )
            except PriorOutboundAttemptError as prior:
                reconcile = self.reconcile_prior_attempts
                if reconciled or reconcile is None or not prior.attempts:
                    raise
                reconciled = True
                disposition = await reconcile(self.writer, prior.attempts)
                if disposition is not PriorAttemptRecovery.LOCAL_ORIGINAL_UNRECOVERABLE:
                    raise type(prior)(
                        "Recover the original result or keep the unresolved request stopped",
                        attempts=prior.attempts,
                        recovery=(
                            PriorAttemptRecovery.ORIGINAL_AVAILABLE
                            if disposition is PriorAttemptRecovery.ORIGINAL_AVAILABLE
                            else PriorAttemptRecovery.IN_FLIGHT_OR_UNKNOWN
                        ),
                    ) from None
                # Scoped to the exact immutable observations, not a reusable request-wide
                # permit. Never re-probe a newly admitted competitor in this invocation.
                unrecoverable = prior.attempts
                continue
            except _RetryNotReadyError as delay:
                # No DB transaction across waiting. Recheck cancellation/writer/deadline;
                # the persisted timestamp, not this process's timer, authorizes sending.
                await sleep(min(delay.seconds, 1.0))
                continue
            try:
                response = await send()
            except ResponseStreamCancelledError as error:
                raise ReceivedModelResponseCancelledError(
                    ReceivedModelResponse(error.response, attempt_id)
                ) from None
            except ResponseStreamCleanupError as error:
                raise ReceivedModelResponseError(
                    ReceivedModelResponse(error.response, attempt_id)
                ) from None
            except APIError as error:
                try:
                    retryable = await self._record_failure(attempt_id, error)
                except (Exception, CancelledError) as save_error:
                    # Keep the local failure's type and stop. Its default traceback must
                    # not chain the provider body that happened to precede the DB error.
                    # Cancellation still propagates, including while awaiting a connection.
                    raise save_error from None
                if not retryable:
                    raise ModelRequestFailedError(classify_response_failure(error)) from None
                continue
            return response, attempt_id

    async def _record_failure(self, attempt_id: UUID, error: APIError) -> bool:
        async with self.sessions.begin() as session:
            now = await budgets.read_execution_time(session, self.writer.scope)
            attempt = await budgets.read_outbound_attempt(session, self.writer.scope, attempt_id)
            if attempt is None:
                raise BudgetConflictError("Cannot record an unadmitted provider failure")
            prior = await budgets.read_request_attempts(
                session, self.writer.scope, attempt.request.request_id
            )
            delay = self.retry_policy.delay_seconds(
                error, attempt_number=len(prior), now=now, random_fraction=random()
            )
            retry_at = None
            if delay is not None:
                try:
                    retry_at = now + timedelta(seconds=delay)
                except OverflowError:
                    pass  # Too large to represent means stop, never retry sooner.
            await budgets.record_attempt_failure(
                session,
                self.writer.scope,
                attempt_id,
                failure=OutboundFailure(classify_response_failure(error).kind.value, retry_at),
            )
        return retry_at is not None

    async def _reserve_request(
        self,
        request_id: UUID,
        kind: OutboundKind,
        request_payload: dict[str, object],
        reservation: Decimal,
        *,
        unrecoverable: tuple[OutboundAttempt, ...] = (),
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
            policy = await self._require_cost_basis(session)
            prior = await budgets.read_request_attempts(session, self.writer.scope, request_id)
            if any(attempt.request != outbound for attempt in prior):
                raise BudgetConflictError("An outbound request cannot change its saved payload")
            retry_times = []
            for attempt in prior:
                if attempt.failure is None:
                    continue
                if attempt.failure.retry_not_before is None:
                    raise prior_error("A terminal provider failure cannot be readmitted")
                retry_times.append(attempt.failure.retry_not_before)
            unresolved = tuple(attempt for attempt in prior if attempt.failure is None)
            if frozenset(unresolved) != frozenset(unrecoverable):
                raise prior_error(
                    "Reconcile the original outbound attempt before retrying",
                    attempts=unresolved,
                )
            if retry_times:
                now = await budgets.read_execution_time(session, self.writer.scope)
                retry_at = max(retry_times)
                if now >= policy.deadline_at or retry_at >= policy.deadline_at:
                    raise BudgetExceededError(BudgetLimit.DEADLINE)
                if retry_at > now:
                    # Reuse admission's budget rules; don't spend a server delay waiting
                    # when cost or attempt limits already preclude another request.
                    await budgets.check_outbound_capacity(
                        session, self.writer, request=outbound, reserved_cost_usd=reservation
                    )
                    raise _RetryNotReadyError((retry_at - now).total_seconds())
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

    async def _require_cost_basis(self, session: AsyncSession) -> ExecutionBudget:
        policy = await budgets.read_execution_budget(session, self.writer.scope)
        if policy is None or policy.cost_basis != self.accounting.cost_basis:
            raise BudgetConflictError("The accounting policy does not match this execution")
        return policy
