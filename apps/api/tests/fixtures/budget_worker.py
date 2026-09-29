"""Fresh-process budget check using only synthetic test scope identifiers."""

import asyncio
import json
import os
import sys
from decimal import Decimal
from uuid import UUID, uuid4

from caliburn.adapters.database import Database
from caliburn.features.executions import budgets
from caliburn.features.executions.budget_models import (
    BudgetExceededError,
    OutboundKind,
    OutboundRequest,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.settings import DatabaseSettings


async def run() -> None:
    settings = DatabaseSettings(url=os.environ["CALIBURN_TEST_DATABASE_URL"], schema=sys.argv[1])
    scope = ExecutionScope(UUID(sys.argv[2]), UUID(sys.argv[3]), ExecutionKind.CONSULTANT_TURN)
    writer = ExecutionWriter(scope, UUID(sys.argv[4]))
    database = Database(settings)
    try:
        async with database.sessions.begin() as session:
            policy = await budgets.read_execution_budget(session, scope)
            usage = await budgets.read_budget_usage(session, scope)
            assert policy is not None and policy.max_outbound_attempts == 1
            assert usage.outbound_attempts == 1
        try:
            async with database.sessions.begin() as session:
                await budgets.reserve_outbound_attempt(
                    session,
                    writer,
                    request=OutboundRequest(uuid4(), OutboundKind.MODEL, "a" * 64),
                    attempt_id=uuid4(),
                    reserved_cost_usd=Decimal("0.1"),
                )
        except BudgetExceededError as error:
            print(json.dumps({"denied": error.limit.value, "attempts": usage.outbound_attempts}))
        else:
            raise AssertionError("Restart must not reset the existing budget")
    finally:
        await database.close()


if __name__ == "__main__":
    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
