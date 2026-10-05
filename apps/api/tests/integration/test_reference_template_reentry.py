"""New reference tools must not replace a Turn's already saved preparation template."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems, snapshot_compaction
from caliburn.agent_execution.context_compaction import (
    CompactionRuntime,
    CompactionSaveError,
    HeldCompaction,
    HeldPreparationCount,
    PreparationCountSaveError,
    prepare_context_history,
)
from caliburn.agents.job_consultant.context_binding import capture_turn_context
from caliburn.features.executions import history
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionStatus, ExecutionWriter
from caliburn.settings import DatabaseSettings
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.integration.test_occupation_reference_workflow import new_writer
from tests.unit.test_context_preparation import PreparationProbe

pytestmark = pytest.mark.postgres


def template(instructions: str, tool_name: str) -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions=instructions,
        input_items=[],
        tools=[
            {
                "type": "function",
                "name": tool_name,
                "description": "Synthetic offline read",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                "strict": True,
            }
        ],
        reasoning_effort="high",
        max_output_tokens=1024,
    )


@asynccontextmanager
async def saved_history(
    client: TestClient, settings: DatabaseSettings, writer: ExecutionWriter
) -> AsyncIterator[RoleContextHistory]:
    dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
    async with AsyncPostgresSaver.from_conn_string(dsn, serde=create_graph_serializer()) as saver:
        await saver.setup()
        yield RoleContextHistory(
            client.app.state.database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
        )


async def prepare(work: RoleContextHistory, request: ResponseRequest) -> NativeItems:
    probe = PreparationProbe()
    return await work.prepare_history(
        template=request,
        threshold_tokens=128_000,
        count_input=probe.count,
        runtime=CompactionRuntime(
            probe.compact, probe.account, work.ensure_active, synthetic_capacity_limits()
        ),
    )


@pytest.mark.parametrize("adoption_interrupted", [False, True])
def test_saved_template_survives_upgrade_before_or_after_adoption_and_before_context_capture(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
    adoption_interrupted: bool,
) -> None:
    writer = new_writer(client)
    old = template("Original role instructions", "original_read")
    new = template("New role instructions with references", "search_occupation_references")

    async def interrupted_adoption(*args, **kwargs):
        raise RuntimeError("synthetic adoption interruption")

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            if adoption_interrupted:
                with monkeypatch.context() as patch:
                    patch.setattr(history, "adopt_prepared_context", interrupted_adoption)
                    with pytest.raises(RuntimeError, match="adoption interruption"):
                        await prepare(work, old)
            else:
                await prepare(work, old)
        # A new saver and workflow instance must still find the original template.
        async with saved_history(client, database_settings, writer) as rebuilt:
            restored = await rebuilt.resolve_template(new)
            assert restored.create_payload() == old.create_payload()
            prepared = await prepare(rebuilt, restored)
            context = await capture_turn_context(
                rebuilt, template=restored, prepared_history=prepared
            )
            payload = context.request.create_payload()
            assert payload["instructions"] == "Original role instructions"
            assert [item["name"] for item in payload["tools"]] == ["original_read"]
            assert len(payload["input"]) == 2
            assert new.create_payload()["instructions"] == "New role instructions with references"

    client.portal.call(scenario)


def test_fresh_turn_uses_new_template_even_when_another_role_has_preparation(
    client: TestClient, database_settings: DatabaseSettings
) -> None:
    writer = new_writer(client)
    old = template("Original role instructions", "original_read")
    new = template("New role instructions", "search_occupation_references")

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            probe = PreparationProbe()
            await prepare_context_history(
                work.checkpointer,
                thread_id=context_thread_id(
                    writer.scope,
                    AgentRole.WORK_SITUATION_ANALYST,
                    HistoryWindowKind.PREPARED_HISTORY,
                ),
                history_request=old,
                threshold_tokens=128_000,
                compact_requested=False,
                count_input=probe.count,
                runtime=CompactionRuntime(
                    probe.compact, probe.account, work.ensure_active, synthetic_capacity_limits()
                ),
            )
            restored = await work.resolve_template(new)
            assert restored.create_payload() == new.create_payload()

    client.portal.call(scenario)


@pytest.mark.parametrize("kind", ["count", "compaction"])
def test_preparation_handoff_without_its_saved_boundary_is_rejected(
    client: TestClient, database_settings: DatabaseSettings, kind: str
) -> None:
    writer = new_writer(client)

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            old = template("Original role instructions", "original_read")
            payload = {
                **old.create_payload(),
                "input": [{"role": "user", "content": "old history"}],
            }
            request_id = uuid4()
            thread_id = context_thread_id(
                writer.scope, work.role, HistoryWindowKind.PREPARED_HISTORY
            )
            if kind == "count":
                held = HeldPreparationCount(
                    thread_id,
                    request_id,
                    payload,
                    {"input_count": {"input_tokens": 100, "attempt_id": uuid4()}},
                )
            else:
                received = await PreparationProbe().compact(
                    ResponseRequest.from_snapshot(payload), request_id
                )
                held = HeldCompaction(
                    thread_id,
                    request_id,
                    payload,
                    {
                        "compaction_snapshot": snapshot_compaction(received.response),
                        "compaction_attempt_id": received.attempt_id,
                    },
                )
            try:
                await work.resolve_template(
                    template("New role instructions", "search_occupation_references"),
                    recovery=held,
                )
            except ValueError as error:
                assert "saved preparation boundary" in str(error)
            else:
                raise AssertionError("A handoff without its saved request was accepted")
            assert held.request_snapshot["input"] == [{"role": "user", "content": "old history"}]

    client.portal.call(scenario)


@pytest.mark.parametrize("kind", ["count", "compaction"])
def test_reused_prepared_base_cannot_accept_unverified_handoff_instructions_or_tools(
    client: TestClient, database_settings: DatabaseSettings, kind: str
) -> None:
    cancelled = new_writer(client)
    original = template("Original instructions", "original_read")

    async def prepare_cancelled() -> None:
        async with saved_history(client, database_settings, cancelled) as work:
            await prepare(work, original)
            await ConsultantCompletionWorkflow(work.sessions).stop(
                cancelled, ExecutionStatus.CANCELLED
            )

    client.portal.call(prepare_cancelled)
    replacement = new_writer(client, cancelled.scope.job_file_id)
    current = template("Current legitimate instructions", "current_read")

    async def scenario() -> None:
        async with saved_history(client, database_settings, replacement) as work:
            prepared = await prepare(work, current)
            async with work.sessions() as session:
                binding = await history.read_context_history(session, replacement.scope, work.role)
            assert binding is not None and binding.prepared is not None
            assert binding.prepared.thread_id == context_thread_id(
                cancelled.scope, work.role, HistoryWindowKind.PREPARED_HISTORY
            )
            thread_id = context_thread_id(
                replacement.scope, work.role, HistoryWindowKind.PREPARED_HISTORY
            )
            assert (
                await work.checkpointer.aget_tuple({"configurable": {"thread_id": thread_id}})
                is None
            )
            payload = template("Unverified instructions", "unverified_write").create_payload()
            request_id = uuid4()
            if kind == "count":
                held = HeldPreparationCount(
                    thread_id,
                    request_id,
                    payload,
                    {"input_count": {"input_tokens": 100, "attempt_id": uuid4()}},
                )
            else:
                result = await PreparationProbe().compact(
                    ResponseRequest.from_snapshot(payload), request_id
                )
                held = HeldCompaction(
                    thread_id,
                    request_id,
                    payload,
                    {
                        "compaction_snapshot": snapshot_compaction(result.response),
                        "compaction_attempt_id": result.attempt_id,
                    },
                )
            try:
                await work.resolve_template(current, recovery=held)
            except ValueError as error:
                assert "saved preparation boundary" in str(error)
            else:
                raise AssertionError("A reused base accepted unverified instructions and tools")
            resolved = await work.resolve_template(current)
            context = await capture_turn_context(work, template=resolved, prepared_history=prepared)
            actual = context.request.create_payload()
            assert actual["instructions"] == "Current legitimate instructions"
            assert [item["name"] for item in actual["tools"]] == ["current_read"]

    client.portal.call(scenario)


@pytest.mark.parametrize("kind", ["count", "compaction"])
def test_real_held_result_retains_its_saved_request_and_recovers_without_repeating_calls(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    writer = new_writer(client)
    original = template("Original instructions", "original_read")

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            thread_id = context_thread_id(
                writer.scope, work.role, HistoryWindowKind.PREPARED_HISTORY
            )
            request = ResponseRequest.from_snapshot(
                {**original.create_payload(), "input": [{"role": "user", "content": "old history"}]}
            )
            probe = PreparationProbe(128_000)
            runtime = CompactionRuntime(
                probe.compact, probe.account, work.ensure_active, synthetic_capacity_limits()
            )
            field = "input_count" if kind == "count" else "compaction_snapshot"
            original_put = work.checkpointer.aput
            original_writes = work.checkpointer.aput_writes

            async def fail_result(config, checkpoint, metadata, new_versions):
                if checkpoint["channel_values"].get(field) is not None:
                    raise RuntimeError("synthetic result save interruption")
                return await original_put(config, checkpoint, metadata, new_versions)

            async def fail_pending_result(config, writes, task_id, task_path=""):
                if any(key == field for key, _ in writes):
                    raise RuntimeError("synthetic pending result save interruption")
                return await original_writes(config, writes, task_id, task_path)

            failure_type = PreparationCountSaveError if kind == "count" else CompactionSaveError
            with monkeypatch.context() as patch:
                patch.setattr(work.checkpointer, "aput", fail_result)
                patch.setattr(work.checkpointer, "aput_writes", fail_pending_result)
                with pytest.raises(failure_type) as failed:
                    await prepare_context_history(
                        work.checkpointer,
                        thread_id=thread_id,
                        history_request=request,
                        threshold_tokens=128_000,
                        compact_requested=False,
                        count_input=probe.count,
                        runtime=runtime,
                    )
            held = failed.value.recovery
            resolved = await work.resolve_template(
                template("New instructions", "new_read"), recovery=held
            )
            assert resolved.create_payload() == original.create_payload()
            recovered = await prepare_context_history(
                work.checkpointer,
                thread_id=thread_id,
                history_request=request,
                threshold_tokens=128_000,
                compact_requested=False,
                count_input=probe.count,
                runtime=runtime,
                recovery=held,
            )
            assert recovered == probe.window
            assert len(probe.count_requests) == 1
            assert len(probe.compact_requests) == 1

    client.portal.call(scenario)


@pytest.mark.parametrize("boundary", ["other_execution", "other_role", "window_compaction"])
def test_handoff_from_another_boundary_cannot_supply_the_template(
    client: TestClient, database_settings: DatabaseSettings, boundary: str
) -> None:
    writer = new_writer(client)

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            scope = (
                replace(writer.scope, execution_id=uuid4())
                if boundary == "other_execution"
                else writer.scope
            )
            role = AgentRole.WORK_SITUATION_ANALYST if boundary == "other_role" else work.role
            thread_id = context_thread_id(scope, role, HistoryWindowKind.PREPARED_HISTORY)
            if boundary == "window_compaction":
                thread_id = f"{work.response_thread_id}:compact:{uuid4()}"
            held = HeldPreparationCount(
                thread_id,
                uuid4(),
                template("Foreign instructions", "foreign_read").create_payload(),
                {"input_count": {"input_tokens": 100, "attempt_id": uuid4()}},
            )
            with pytest.raises(ValueError):
                await work.resolve_template(template("New instructions", "new_read"), recovery=held)

    client.portal.call(scenario)


@pytest.mark.parametrize("mismatch", ["request_id", "request_snapshot"])
def test_handoff_must_match_the_already_saved_preparation_request(
    client: TestClient, database_settings: DatabaseSettings, mismatch: str
) -> None:
    writer = new_writer(client)
    old = template("Original role instructions", "original_read")

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            await prepare(work, old)
            thread_id = context_thread_id(
                writer.scope, work.role, HistoryWindowKind.PREPARED_HISTORY
            )
            saved = await work.checkpointer.aget_tuple({"configurable": {"thread_id": thread_id}})
            assert saved is not None
            values = saved.checkpoint["channel_values"]
            request_id = uuid4() if mismatch == "request_id" else values["request_id"]
            payload = values["request_snapshot"]
            if mismatch == "request_snapshot":
                payload = {**payload, "instructions": "Forged instructions"}
            held = HeldPreparationCount(
                thread_id,
                request_id,
                payload,
                {"input_count": {"input_tokens": 100, "attempt_id": uuid4()}},
            )
            with pytest.raises(ValueError):
                await work.resolve_template(template("New instructions", "new_read"), recovery=held)

    client.portal.call(scenario)


def test_initial_start_checkpoint_keeps_template_before_the_first_expanded_state(
    client: TestClient, database_settings: DatabaseSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    writer = new_writer(client)
    old = template("Original role instructions", "original_read")

    async def scenario() -> None:
        async with saved_history(client, database_settings, writer) as work:
            original_put = work.checkpointer.aput

            async def fail_expanded_state(config, checkpoint, metadata, new_versions):
                if "request_snapshot" in checkpoint["channel_values"]:
                    raise RuntimeError("synthetic first state interruption")
                return await original_put(config, checkpoint, metadata, new_versions)

            with monkeypatch.context() as patch:
                patch.setattr(work.checkpointer, "aput", fail_expanded_state)
                with pytest.raises(RuntimeError, match="first state interruption"):
                    await prepare(work, old)
            restored = await work.resolve_template(template("New instructions", "new_read"))
            assert restored.create_payload() == old.create_payload()
            assert await prepare(work, restored) == []

    client.portal.call(scenario)
