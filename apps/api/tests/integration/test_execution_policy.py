"""A role fixes its allowance once; a restart keeps it and cannot swap the pricing basis."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.openai_models import model_profile
from caliburn.features.executions import budgets, service
from caliburn.features.executions.budget_models import BudgetConflictError, ExecutionBudget
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.settings import ModelSettings
from caliburn.workflows.model_runtime import fix_execution_policy

pytestmark = pytest.mark.postgres

SETTINGS = ModelSettings(api_key="synthetic")


def admitted_writer(client: TestClient) -> ExecutionWriter:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "合成額度", "employee_name": "合成員工"},
    )
    scope = ExecutionScope(
        UUID(created.json()["job_file_id"]), uuid4(), ExecutionKind.CONSULTANT_TURN
    )

    async def admit() -> ExecutionWriter:
        async with client.app.state.database.sessions.begin() as session:
            await service.admit_execution(session, scope)
            return await service.claim_writer(session, scope, writer_id=uuid4())

    return client.portal.call(admit)


def fix(client: TestClient, writer: ExecutionWriter, settings: ModelSettings) -> ExecutionBudget:
    return client.portal.call(
        fix_execution_policy, client.app.state.database.sessions, writer, settings
    )


def test_first_call_fixes_the_allowance_from_the_settings(client: TestClient) -> None:
    writer = admitted_writer(client)

    policy = fix(client, writer, replace(SETTINGS, max_model_steps=7, max_compactions=2))

    assert (policy.max_model_steps, policy.max_compactions) == (7, 2)
    assert policy.max_outbound_attempts == SETTINGS.max_outbound_attempts
    assert policy.max_attempts_per_request == SETTINGS.max_attempts_per_request
    assert policy.cost_basis == model_profile(SETTINGS.model).pricing.cost_basis
    assert policy.deadline_at > datetime.now(UTC) + timedelta(
        seconds=SETTINGS.turn_timeout_seconds - 60
    )


def test_a_restart_keeps_the_original_allowance_even_if_the_settings_change(
    client: TestClient,
) -> None:
    writer = admitted_writer(client)
    original = fix(client, writer, replace(SETTINGS, max_model_steps=7))

    restarted = fix(client, writer, replace(SETTINGS, max_model_steps=99, max_compactions=1))

    assert restarted == original


def test_a_stored_pricing_basis_that_differs_is_a_conflict(client: TestClient) -> None:
    writer = admitted_writer(client)

    async def store_other_basis() -> None:
        async with client.app.state.database.sessions.begin() as session:
            await budgets.fix_execution_budget(
                session,
                writer,
                ExecutionBudget(
                    8,
                    4,
                    32,
                    3,
                    datetime.now(UTC) + timedelta(hours=1),
                    Decimal("1"),
                    "an-older-rate-record",
                ),
            )

    client.portal.call(store_other_basis)

    with pytest.raises(BudgetConflictError):
        fix(client, writer, SETTINGS)
