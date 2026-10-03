"""Official rate configuration + actual budget transactions; synthetic SDK transport only."""

import json
from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import httpx2
import pytest

from caliburn.adapters.openai_pricing import GPT_6_LUNA_STANDARD_2026_09_30
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.features.executions import budgets
from caliburn.features.executions.budget_models import (
    BudgetConflictError,
    BudgetExceededError,
    BudgetLimit,
)
from caliburn.workflows.model_requests import ModelRequestAccounting, ModelUsageUnavailableError
from tests.integration.test_compaction_accounting import admitted_executor
from tests.integration.test_compaction_accounting import file_id as file_id
from tests.integration.test_compaction_accounting import runner as runner
from tests.unit.test_openai_pricing import response_fixture

pytestmark = pytest.mark.postgres
PRICING = GPT_6_LUNA_STANDARD_2026_09_30


def accounting_fixture() -> ModelRequestAccounting:
    return ModelRequestAccounting.from_text_pricing(
        PRICING,
        token_count_reservation_usd=Decimal("0.001"),
        compaction_reservation_usd=Decimal("0.01"),
    )


def request_fixture(*, model="gpt-6-luna", max_output_tokens=100) -> ResponseRequest:
    return ResponseRequest(
        model=model,
        instructions="synthetic",
        input_items=[],
        tools=[],
        reasoning_effort="low",
        max_output_tokens=max_output_tokens,
    )


@pytest.mark.parametrize("compact", [False, True])
def test_original_usage_settles_once_after_database_reentry(
    database_settings, file_id, runner, compact
) -> None:
    async def scenario():
        sends = []
        raw = response_fixture().model_dump()
        if compact:
            raw = {
                "id": "cmp_synthetic",
                "object": "response.compaction",
                "created_at": 1,
                "output": [],
                "usage": raw["usage"],
            }

        def respond(request):
            sends.append(json.loads(request.content))
            return httpx2.Response(200, json=raw)

        accounting = accounting_fixture()
        async with admitted_executor(database_settings, file_id, respond, accounting) as executor:
            request_id = uuid4()
            received = await (
                executor.request_compaction(request_fixture(), request_id)
                if compact
                else executor.request_model(request_fixture(), request_id, 1000)
            )
            settle = executor.account_compaction if compact else executor.account_response
            await settle(received)
            # A new executor over the same owner models re-entry, not a new request.
            restarted = replace(executor, accounting=accounting_fixture())
            await (
                restarted.account_compaction(received)
                if compact
                else restarted.account_response(received)
            )
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == Decimal("0.000119")
            assert usage.outbound_attempts == len(sends) == 1
            assert sends[0]["service_tier"] == "default"

    runner.run(scenario())


def test_missing_usage_leaves_original_reservation_and_does_not_resend(
    database_settings, file_id, runner
) -> None:
    async def scenario():
        sends = []
        raw = response_fixture().model_dump()
        del raw["usage"]["input_tokens_details"]["cache_write_tokens"]

        def respond(request):
            sends.append(request)
            return httpx2.Response(200, json=raw)

        accounting = accounting_fixture()
        async with admitted_executor(database_settings, file_id, respond, accounting) as executor:
            received = await executor.request_model(request_fixture(), uuid4(), 1000)
            with pytest.raises(ModelUsageUnavailableError):
                await executor.account_response(received)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.accounted_cost_usd == Decimal("0.000175")
            assert usage.outbound_attempts == len(sends) == 1

    runner.run(scenario())


@pytest.mark.parametrize("kind", ["model", "compaction", "count"])
def test_configured_model_mismatch_stops_before_admission_or_http(
    database_settings, file_id, runner, kind
) -> None:
    async def scenario():
        def respond(_):
            pytest.fail("Mismatched price/model must stop before HTTP")

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture()
        ) as executor:
            send = {
                "model": executor.request_model,
                "compaction": executor.request_compaction,
                "count": executor.count_input,
            }[kind]
            with pytest.raises(BudgetConflictError, match="model"):
                arguments = (1000,) if kind == "model" else ()
                await send(request_fixture(model="gpt-6-sol"), uuid4(), *arguments)
            async with executor.sessions.begin() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 0

    runner.run(scenario())


def test_rate_change_cannot_settle_an_old_execution(database_settings, file_id, runner) -> None:
    async def scenario():
        raw = response_fixture().model_dump()
        async with admitted_executor(
            database_settings,
            file_id,
            lambda _: httpx2.Response(200, json=raw),
            accounting_fixture(),
        ) as executor:
            received = await executor.request_model(request_fixture(), uuid4(), 1000)
            changed = replace(PRICING, source_revision="changed-revision")
            wrong_accounting = ModelRequestAccounting.from_text_pricing(changed)
            with pytest.raises(BudgetConflictError, match="policy"):
                await replace(executor, accounting=wrong_accounting).account_response(received)
            await executor.account_response(received)

    runner.run(scenario())


def test_each_request_reserves_its_count_and_output_limit(
    database_settings, file_id, runner
) -> None:
    async def scenario():
        raw = response_fixture().model_dump()
        async with admitted_executor(
            database_settings,
            file_id,
            lambda _: httpx2.Response(200, json=raw),
            accounting_fixture(),
        ) as executor:
            for input_tokens, output_limit, expected in [
                (1000, 100, "0.000175"),
                (2000, 200, "0.000350"),
                (273_000, 100, "0.068325"),
            ]:
                result = await executor.request_model(
                    request_fixture(max_output_tokens=output_limit), uuid4(), input_tokens
                )
                async with executor.sessions() as session:
                    attempt = await budgets.read_outbound_attempt(
                        session, executor.writer.scope, result.attempt_id
                    )
                assert attempt.reserved_cost_usd == Decimal(expected)

    runner.run(scenario())


def test_counted_request_still_stops_before_http_when_over_budget(
    database_settings, file_id, runner
) -> None:
    async def scenario():
        def respond(_):
            pytest.fail("An over-budget request must not reach the provider")

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(), max_cost_usd=Decimal("0.01")
        ) as executor:
            with pytest.raises(BudgetExceededError) as failure:
                await executor.request_model(request_fixture(), uuid4(), 100_000)
            assert failure.value.limit == BudgetLimit.COST
            async with executor.sessions() as session:
                usage = await budgets.read_budget_usage(session, executor.writer.scope)
            assert usage.outbound_attempts == 0

    runner.run(scenario())


@pytest.mark.parametrize("compact", [False, True])
def test_product_missing_billing_usage_does_not_block_saved_result(
    database_settings, file_id, runner, compact
) -> None:
    async def scenario():
        sends = []
        raw = response_fixture().model_dump()
        if compact:
            raw = {
                "id": "cmp_synthetic",
                "object": "response.compaction",
                "created_at": 1,
                "output": [],
                "usage": raw["usage"],
            }
        del raw["usage"]["input_tokens_details"]["cache_write_tokens"]

        def respond(request):
            sends.append(request)
            return httpx2.Response(200, json=raw)

        async with admitted_executor(
            database_settings, file_id, respond, accounting_fixture(), max_cost_usd=None
        ) as executor:
            received = await (
                executor.request_compaction(request_fixture(), uuid4())
                if compact
                else executor.request_model(request_fixture(), uuid4(), 1000)
            )
            settle = executor.account_compaction if compact else executor.account_response
            await settle(received)
            async with executor.sessions() as session:
                attempt = await budgets.read_outbound_attempt(
                    session, executor.writer.scope, received.attempt_id
                )
            assert attempt.reported_cost_usd is None  # Unknown, not invented zero billing.
            assert len(sends) == 1

    runner.run(scenario())
