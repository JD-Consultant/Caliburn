"""Real admission deadlines stop network waits while the original attempt stays unknown."""

import asyncio
from uuid import uuid4

import pytest

from caliburn.features.executions import budgets
from caliburn.features.executions.budget_models import BudgetExceededError, BudgetLimit
from caliburn.workflows.executions.model_requests import PriorOutboundAttemptError
from tests.integration.test_outbound_retry import request_fixture, retry_executor

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("kind", ["model", "count", "compact"])
def test_deadline_uses_persisted_policy_and_blocks_another_outbound(
    database_settings, database_connection, kind
):
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'期限','期限','合成人員')",
        (file_id,),
    )

    async def scenario():
        calls = 0

        async def respond(_request):
            nonlocal calls
            calls += 1
            await asyncio.Event().wait()

        async with retry_executor(
            database_settings, file_id, respond, deadline_seconds=0.5
        ) as executor:
            request_id = uuid4()

            async def send():
                if kind == "model":
                    return await executor.request_model(request_fixture(), request_id, 100)
                if kind == "count":
                    return await executor.count_input(request_fixture(), request_id)
                return await executor.request_compaction(request_fixture(), request_id)

            with pytest.raises(BudgetExceededError) as stopped:
                await asyncio.wait_for(send(), 2)
            assert stopped.value.limit == BudgetLimit.DEADLINE
            assert calls == 1
            async with executor.sessions() as session:
                attempts = await budgets.read_request_attempts(
                    session, executor.writer.scope, request_id
                )
            assert len(attempts) == 1
            assert attempts[0].failure is None
            if kind == "count":
                # 未保存計數可重算，但原 deadline 仍先阻止新外送。
                with pytest.raises(BudgetExceededError) as readmission:
                    await send()
                assert readmission.value.limit == BudgetLimit.DEADLINE
            else:
                with pytest.raises(PriorOutboundAttemptError):
                    await send()
            assert calls == 1
            async with executor.sessions() as session:
                assert (
                    await budgets.read_request_attempts(session, executor.writer.scope, request_id)
                    == attempts
                )

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
