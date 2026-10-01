"""Bind one role execution to its fixed allowance and to direct model I/O.

The consultant and the shared B1/B2 assembly start every execution the same way: fix the
allowance once, take the pricing and capacity of the configured model, and build the request
executor and the compaction runtime that account against that allowance. They keep their own
prompts, tools, history and completion; nothing here is a base agent or a second loop.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.openai_models import ModelCapacityLimits, model_profile
from caliburn.adapters.response_streaming import PublicCommentaryUpdate
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.features.executions import budgets
from caliburn.features.executions import service as executions
from caliburn.features.executions.budget_models import BudgetConflictError, ExecutionBudget
from caliburn.features.executions.models import ExecutionWriter
from caliburn.settings import ModelSettings
from caliburn.workflows.model_requests import ModelRequestAccounting, ModelRequestExecutor

# Held back from the allowance before the real usage of a count or compact request is known.
TOKEN_COUNT_RESERVATION_USD = Decimal("0.0001")
COMPACTION_RESERVATION_USD = Decimal("0.50")


async def fix_execution_policy(
    sessions: async_sessionmaker[AsyncSession], writer: ExecutionWriter, settings: ModelSettings
) -> ExecutionBudget:
    """Fix the allowance on the first call; later calls return it unchanged.

    A restart or a changed configuration cannot reset spent allowance or swap the pricing
    record the execution started with.
    """
    pricing = model_profile(settings.model).pricing
    async with sessions.begin() as session:
        await executions.lock_active_writer(session, writer)
        policy = await budgets.read_execution_budget(session, writer.scope)
        if policy is not None:
            if policy.cost_basis != pricing.cost_basis:
                raise BudgetConflictError("Resume requires the original pricing policy")
            return policy
        now = await budgets.read_execution_time(session, writer.scope)
        return await budgets.fix_execution_budget(
            session,
            writer,
            ExecutionBudget(
                settings.max_model_steps,
                settings.max_compactions,
                settings.max_outbound_attempts,
                settings.max_attempts_per_request,
                now + timedelta(seconds=settings.turn_timeout_seconds),
                settings.max_cost_usd,
                pricing.cost_basis,
            ),
        )


@dataclass(frozen=True, slots=True)
class ModelRuntime:
    """The accounted request executor and compaction runtime of one execution."""

    executor: ModelRequestExecutor
    compaction: CompactionRuntime
    capacity_limits: ModelCapacityLimits


def bind_model_runtime(
    sessions: async_sessionmaker[AsyncSession],
    writer: ExecutionWriter,
    client: AsyncOpenAI,
    settings: ModelSettings,
    *,
    ensure_active: Callable[[], Awaitable[None]],
    on_commentary: Callable[[PublicCommentaryUpdate], None] | None = None,
) -> ModelRuntime:
    """Build the executor and compaction runtime; `ensure_active` is the role's own eligibility."""
    profile = model_profile(settings.model)
    executor = ModelRequestExecutor(
        sessions,
        writer,
        client,
        ModelRequestAccounting.from_text_pricing(
            profile.pricing,
            token_count_reservation_usd=TOKEN_COUNT_RESERVATION_USD,
            compaction_reservation_usd=COMPACTION_RESERVATION_USD,
        ),
        on_commentary=on_commentary,
    )
    limits = profile.capacity_limits()
    compaction = CompactionRuntime(
        executor.request_compaction, executor.account_compaction, ensure_active, limits
    )
    return ModelRuntime(executor, compaction, limits)
