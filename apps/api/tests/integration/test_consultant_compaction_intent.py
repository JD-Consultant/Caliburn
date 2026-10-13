"""A's tool intent survives completed work, but adopted preparation is not repeated."""

import asyncio
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.adapters.response_serialization import NativeItems, NativeSnapshot
from caliburn.agent_execution.response_runtime import PausedResponseLoop
from caliburn.agent_execution.tool_steps import read_completed_response_history, read_response_pause
from caliburn.agents.job_consultant.context_binding import read_saved_turn_context
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole, HistoryConflictError
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.transport.model_tools.context_compaction import ContextCompactionTools
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_turns.controls import (
    ConsultantControlWorkflow,
    run_consultant_with_controls,
)
from caliburn.workflows.consultant_turns.supervisor import ConsultantSupervisor
from caliburn.workflows.executions.context_history import RoleContextHistory
from caliburn.workflows.interview_plans import InterviewPlanReadWorkflow, InterviewPlanWorkflow
from tests.fixtures.response_loop import response_at
from tests.integration.test_consultant_context_binding import publish_memory, start
from tests.integration.test_context_histories import admit_writer, prepare, transact

pytestmark = pytest.mark.postgres


class WindowTransport:
    """只替代 SDK I/O；128K 是注入條件，並非合成文字的實測 token。"""

    def __init__(self) -> None:
        self.events: list[tuple[str, NativeSnapshot]] = []
        self.sent: list[NativeSnapshot] = []
        self.large_history: NativeItems | None = None
        self.pause: Callable[[], Awaitable[None]] | None = None
        self.paused_plan: str | None = None
        self.compacted_items: NativeItems = [
            {"role": "user", "content": "RETAINED_COMPACTED_USER"},
            {"type": "compaction", "id": "cmp_window", "encrypted_content": "synthetic-opaque"},
        ]

    async def respond(self, request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        operation = request.url.path.rsplit("/", 1)[-1]
        self.events.append((operation, payload))
        if operation == "input_tokens":
            count = 128_000 if payload["input"] == self.large_history else 500
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": count}
            )
        if operation == "compact":
            return httpx2.Response(
                200,
                json={
                    "id": "cmp_synthetic",
                    "object": "response.compaction",
                    "created_at": 1,
                    "output": self.compacted_items,
                    "usage": {
                        "input_tokens": 128_000,
                        "output_tokens": 30,
                        "total_tokens": 128_030,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    },
                },
            )
        assert operation == "responses"
        self.sent.append(payload)
        ordinal = len(self.sent)
        # 首輪與稍後暫停的 Step 都經正式工具保存壓縮意圖。
        requested = ordinal in (1, 3)
        edit_plan = ordinal == 3 and self.paused_plan is not None
        raw = response_at(
            ordinal, final=not requested, tools=int(requested) + int(edit_plan)
        ).model_dump(mode="json")
        raw["service_tier"] = "default"
        if requested:
            raw["output"][2].update(name="request_context_compaction", arguments="{}")
        if edit_plan:
            raw["output"][3].update(
                name="edit_interview_plan",
                arguments=json.dumps({"diff": f"@@\n+{self.paused_plan}\n*** End of File"}),
            )
        if ordinal == 3:
            assert self.pause is not None
            await self.pause()
        return httpx2.Response(200, json=raw)


@asynccontextmanager
async def open_window_runner(
    database: Database, settings: DatabaseSettings, transport: WindowTransport
) -> AsyncIterator[tuple[AsyncPostgresSaver, ConsultantRunner]]:
    """每次重開官方 PG saver 與 SDK，離開時關閉本次資源。"""
    dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
    async with AsyncPostgresSaver.from_conn_string(dsn, serde=create_graph_serializer()) as saver:
        await saver.setup()
        sdk = create_responses_client(
            api_key="synthetic",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(transport.respond)),
        )
        try:
            yield (
                saver,
                ConsultantRunner(database.sessions, saver, sdk, ModelSettings(api_key="synthetic")),
            )
        finally:
            await sdk.close()


def supervise_window_runner(
    database: Database, saver: AsyncPostgresSaver, consultant: ConsultantRunner
) -> tuple[ConsultantSupervisor, ConsultantControlWorkflow, asyncio.Queue[object]]:
    """結果佇列只供測試同步；持久准入與控制仍由正式 supervisor 負責。"""
    results: asyncio.Queue[object] = asyncio.Queue()

    async def run(writer: ExecutionWriter) -> object:
        result = await run_consultant_with_controls(
            writer, sessions=database.sessions, checkpointer=saver, run=consultant.run
        )
        await results.put(result)
        return result

    supervisor = ConsultantSupervisor(
        sessions=database.sessions,
        run=run,
        process_lock=PostgresProcessLock(database.settings),
    )
    return supervisor, ConsultantControlWorkflow(database.sessions, saver, supervisor), results


async def completed_window_with_intent(
    database: Database,
    saver: AsyncPostgresSaver,
    consultant: ConsultantRunner,
    writer: ExecutionWriter,
) -> tuple[FormalInterviewExchange, NativeItems]:
    """走正式顧問完成交易，再核對可供下輪採用的工具意圖與原生窗口。"""
    exchange = await consultant.run(writer)
    assert isinstance(exchange, FormalInterviewExchange)
    async with database.sessions() as session:
        binding = await history.read_context_history(
            session, writer.scope, AgentRole.JOB_CONSULTANT
        )
        assert binding is not None and binding.completed is not None
        assert await history.read_completed_compaction_request(
            session, writer.scope.job_file_id, AgentRole.JOB_CONSULTANT, binding.completed
        )
    window = await read_completed_response_history(
        saver,
        thread_id=binding.completed.thread_id,
        checkpoint_id=binding.completed.checkpoint_id,
    )
    outputs = [item for item in window.items if item.get("type") == "function_call_output"]
    assert [json.loads(item["output"]) for item in outputs] == [{"status": "requested"}]
    return exchange, window.items


def test_publication_precedes_requested_compaction_and_cancelled_turn_rebuilds(
    client: TestClient, database_settings: DatabaseSettings
) -> None:
    async def scenario() -> None:
        database = client.app.state.database
        transport = WindowTransport()
        transport.paused_plan = "CANCELLED_PLAN_CANDIDATE"
        async with open_window_runner(database, database_settings, transport) as (saver, runner):
            first = await start(database, "COVERED_FIRST_INPUT")
            exchange, old_window = await completed_window_with_intent(
                database, saver, runner, first
            )
            transport.large_history = old_window
            plans = InterviewPlanReadWorkflow(database.sessions)
            adopted_plan = await plans.read_adopted(first.scope.job_file_id)
            # 既有 owner fixture 合法發布固定快照；B 的模型分析不在本測例範圍。
            published = await publish_memory(
                database, first.scope.job_file_id, exchange.employee_input.source_id, "新版工作"
            )
            boundary = len(transport.events)
            cancelled = await start(database, "CANCELLED_NEW_VERSION", first.scope.job_file_id)
            supervisor, controls, results = supervise_window_runner(database, saver, runner)

            async def pause() -> None:
                await controls.pause(cancelled.scope)

            transport.pause = pause
            try:
                await supervisor.start()
                paused = await asyncio.wait_for(results.get(), 10)
                assert isinstance(paused, PausedResponseLoop)
                context = await read_saved_turn_context(saver, cancelled.scope)
                assert context.reset_history
                assert context.memory_binding.snapshot_id == published.snapshot_id
                renewed = transport.sent[2]["input"]
                assert renewed == context.request.create_payload()["input"]
                reference = json.loads(renewed[0]["content"])
                assert reference["work_situation_map"]["items"] == [
                    {"target_title": "新版工作", "description": "固定導覽描述"}
                ]
                assert [
                    (message["interview_sequence"], message["speaker"])
                    for message in reference["historical_interview"]["messages"]
                ] == [(3, "consultant")]
                assert "COVERED_FIRST_INPUT" not in json.dumps(renewed)
                assert json.loads(renewed[-1]["content"])["interview_sequence"] == 4
                plan_candidate = await InterviewPlanWorkflow(database.sessions).read_current(
                    cancelled.scope
                )
                assert plan_candidate is not None
                assert plan_candidate.body == transport.paused_plan
                assert await plans.read_adopted(first.scope.job_file_id) == adopted_plan
                assert (await controls.cancel(cancelled.scope)).status == ExecutionStatus.CANCELLED
                assert await plans.read_adopted(first.scope.job_file_id) == adopted_plan
            finally:
                await supervisor.close()
            replacement = await start(database, "REPLACEMENT_NEW_VERSION", first.scope.job_file_id)
            result = await runner.run(replacement)
            assert isinstance(result, FormalInterviewExchange)
            assert result.employee_input.interview_sequence == 4
            replacement_context = await read_saved_turn_context(saver, replacement.scope)
            assert replacement_context.reset_history
            assert replacement_context.memory_binding.snapshot_id == published.snapshot_id
            assert replacement_context.memory_binding.interview_through_sequence == 3
            replaced = transport.sent[3]["input"]
            assert replaced[:-1] == renewed[:-1]
            assert json.loads(replaced[-1]["content"]) == {
                "interview_sequence": 4,
                "speaker": "employee",
                "text": "REPLACEMENT_NEW_VERSION",
            }
            assert "CANCELLED_PLAN_CANDIDATE" not in json.dumps(replaced)
            replacement_plan = await plans.read_adopted(first.scope.job_file_id)
            assert replacement_plan is not None and replacement_plan.body is None
            # 新請求仍計數；即使有完成意圖與 128K 條件，舊窗及取消後綴都不外送。
            assert [
                (operation, payload["input"]) for operation, payload in transport.events[boundary:]
            ] == [
                ("input_tokens", renewed),
                ("responses", renewed),
                ("input_tokens", replaced),
                ("responses", replaced),
            ]
            async with database.sessions() as session:
                formal = await interviews.read_interview_history(session, first.scope.job_file_id)
                assert [message.interview_sequence for message in formal] == [1, 2, 3, 4, 5]
                assert "CANCELLED_NEW_VERSION" not in [message.interview_text for message in formal]
                assert (
                    await executions.read_execution(session, replacement.scope)
                ).status == ExecutionStatus.COMPLETED

    client.portal.call(scenario)


def test_paused_compacted_window_resumes_original_capture_after_publication(
    client: TestClient, database_settings: DatabaseSettings
) -> None:
    async def scenario() -> None:
        database = client.app.state.database
        transport = WindowTransport()
        async with open_window_runner(database, database_settings, transport) as (saver, runner):
            first = await start(database, "FIRST_COMPLETED_INPUT")
            exchange, old_window = await completed_window_with_intent(
                database, saver, runner, first
            )
            transport.large_history = old_window
            boundary = len(transport.events)
            second = await start(database, "PINNED_PAUSED_INPUT", first.scope.job_file_id)
            supervisor, controls, results = supervise_window_runner(database, saver, runner)

            async def pause() -> None:
                await controls.pause(second.scope)

            transport.pause = pause
            try:
                await supervisor.start()
                assert isinstance(await asyncio.wait_for(results.get(), 10), PausedResponseLoop)
                captured = await read_saved_turn_context(saver, second.scope)
                assert not captured.reset_history
                assert captured.memory_binding.snapshot_id is None
                paused_request = transport.sent[2]["input"]
                assert paused_request[:-1] == transport.compacted_items
                assert json.loads(paused_request[-1]["content"]) == {
                    "interview_sequence": 4,
                    "speaker": "employee",
                    "text": "PINNED_PAUSED_INPUT",
                }
                assert [
                    (operation, payload["input"])
                    for operation, payload in transport.events[boundary:]
                ] == [
                    ("input_tokens", old_window),
                    ("compact", old_window),
                    ("input_tokens", paused_request),
                    ("responses", paused_request),
                ]
                thread_id = RoleContextHistory(
                    database.sessions, second, AgentRole.JOB_CONSULTANT, saver
                ).response_thread_id
                original_pause = await read_response_pause(saver, thread_id=thread_id)
                assert original_pause is not None
                async with database.sessions() as session:
                    assert (
                        await executions.read_execution(session, second.scope)
                    ).status == ExecutionStatus.PAUSED
                # 正式原生 interrupt 仍在暫停時，Memory 才發布新版。
                published = await publish_memory(
                    database,
                    first.scope.job_file_id,
                    exchange.employee_input.source_id,
                    "暫停後新版",
                )
            finally:
                await supervisor.close()

        # SDK、官方 saver 與 supervisor 全部重開，恢復依據只能來自 PG 原件。
        async with open_window_runner(database, database_settings, transport) as (saver, runner):
            assert await read_response_pause(saver, thread_id=thread_id) == original_pause
            supervisor, controls, results = supervise_window_runner(database, saver, runner)
            before_resume = len(transport.events)
            try:
                await supervisor.start()
                assert (await controls.resume(second.scope)).status == ExecutionStatus.ACTIVE
                result = await asyncio.wait_for(results.get(), 10)
                assert isinstance(result, FormalInterviewExchange)
                assert result.employee_input.interview_sequence == 4
                restored = await read_saved_turn_context(saver, second.scope)
                assert restored.request.create_payload() == captured.request.create_payload()
                assert restored.memory_binding == captured.memory_binding
                assert restored.current_input_source_id == captured.current_input_source_id
                assert restored.candidate_position == captured.candidate_position
                assert restored.plan_position == captured.plan_position
                assert restored.reset_history == captured.reset_history
                resumed_request = transport.sent[3]["input"]
                assert resumed_request[: len(paused_request)] == paused_request
                outputs = [
                    item for item in resumed_request if item.get("type") == "function_call_output"
                ]
                assert [json.loads(item["output"]) for item in outputs] == [{"status": "requested"}]
                assert json.dumps(resumed_request).count("PINNED_PAUSED_INPUT") == 1
                assert "暫停後新版" not in json.dumps(resumed_request, ensure_ascii=False)
                assert [operation for operation, _ in transport.events[before_resume:]] == [
                    "input_tokens",
                    "responses",
                ]
                async with database.sessions() as session:
                    binding = await history.read_context_history(
                        session, second.scope, AgentRole.JOB_CONSULTANT
                    )
                    assert binding is not None and binding.completed is not None
                    assert await history.read_completed_compaction_request(
                        session,
                        first.scope.job_file_id,
                        AgentRole.JOB_CONSULTANT,
                        binding.completed,
                    )
                completed = await read_completed_response_history(
                    saver, thread_id=thread_id, checkpoint_id=binding.completed.checkpoint_id
                )
                transport.large_history = completed.items
            finally:
                await supervisor.close()
            boundary = len(transport.events)
            third = await start(database, "AFTER_RESUME_INPUT", first.scope.job_file_id)
            final = await runner.run(third)
            assert isinstance(final, FormalInterviewExchange)
            assert final.employee_input.interview_sequence == 6
            renewed = await read_saved_turn_context(saver, third.scope)
            assert renewed.reset_history
            assert renewed.memory_binding.snapshot_id == published.snapshot_id
            request = transport.sent[4]["input"]
            reference = json.loads(request[0]["content"])
            assert reference["work_situation_map"]["items"] == [
                {"target_title": "暫停後新版", "description": "固定導覽描述"}
            ]
            assert [
                (message["interview_sequence"], message["speaker"])
                for message in reference["historical_interview"]["messages"]
            ] == [(3, "consultant"), (4, "employee"), (5, "consultant")]
            assert json.dumps(request).count("PINNED_PAUSED_INPUT") == 1
            assert "RETAINED_COMPACTED_USER" not in json.dumps(request)
            assert [
                (operation, payload["input"]) for operation, payload in transport.events[boundary:]
            ] == [("input_tokens", request), ("responses", request)]
            async with database.sessions() as session:
                assert (
                    await executions.read_execution(session, third.scope)
                ).status == ExecutionStatus.COMPLETED

    client.portal.call(scenario)


def test_requested_compaction_runs_next_turn_once_and_excludes_new_input(
    client: TestClient,
    database_settings: DatabaseSettings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "壓縮要求", "employee_name": "合成"},
        ).json()["job_file_id"]
    )
    sent, compactions = [], []
    compacted_items = [
        {"type": "compaction", "id": "cmp_item_synthetic", "encrypted_content": "opaque"},
        {"role": "user", "content": "retained synthetic history"},
    ]

    def accept(text):
        accepted = client.post(
            f"/api/job-files/{file_id}/inputs",
            json={"command_id": str(uuid4()), "text": text},
        )
        assert accepted.status_code == 202
        return ExecutionScope(
            file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
        )

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        if request.url.path.endswith("/compact"):
            compactions.append(payload)
            return httpx2.Response(
                200,
                json={
                    "id": "cmp_synthetic",
                    "object": "response.compaction",
                    "created_at": 1,
                    "output": compacted_items,
                    "usage": {
                        "input_tokens": 500,
                        "output_tokens": 30,
                        "total_tokens": 530,
                        "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                    },
                },
            )
        assert request.url.path.endswith("/responses")
        sent.append(payload)
        first = len(sent) == 1
        raw = response_at(len(sent), final=not first, tools=2 if first else 0).model_dump(
            mode="json"
        )
        raw["service_tier"] = "default"
        if first:
            # Repeated calls are one idempotent intention, not two future compactions.
            for item in raw["output"][-2:]:
                item.update(name="request_context_compaction", arguments="{}")
        return httpx2.Response(200, json=raw)

    async def run(scope, *, fail_after_preparation=False):
        sessions = client.app.state.database.sessions
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            sdk = create_responses_client(
                api_key="synthetic",
                timeout_seconds=5,
                http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
            )
            try:
                runner = ConsultantRunner(sessions, saver, sdk, ModelSettings(api_key="synthetic"))
                if fail_after_preparation:
                    prepare_history = RoleContextHistory.prepare_history

                    async def interrupt_capture(*args, **kwargs):
                        await prepare_history(*args, **kwargs)
                        raise RuntimeError("synthetic interruption after preparation")

                    with monkeypatch.context() as patch:
                        patch.setattr(
                            RoleContextHistory,
                            "prepare_history",
                            interrupt_capture,
                        )
                        with pytest.raises(RuntimeError, match="synthetic interruption"):
                            await runner.run(writer)
                    await ConsultantCompletionWorkflow(sessions).stop(
                        writer, ExecutionStatus.CANCELLED
                    )
                else:
                    await runner.run(writer)
            finally:
                await sdk.close()

    client.portal.call(run, accept("COMPLETED_INPUT"))
    assert compactions == []  # The request never compresses the currently active Turn.
    results = [item for item in sent[1]["input"] if item.get("type") == "function_call_output"]
    assert [json.loads(item["output"]) for item in results] == [
        {"status": "requested"},
        {"status": "requested"},
    ]

    async def cancel_after_preparation(scope):
        await run(scope, fail_after_preparation=True)

    client.portal.call(cancel_after_preparation, accept("CANCELLED_INPUT"))
    assert len(compactions) == 1
    assert "COMPLETED_INPUT" in json.dumps(compactions[0]["input"])
    assert "CANCELLED_INPUT" not in json.dumps(compactions[0]["input"])
    # Reopen saver/client, replace the input: the adopted C survives cancellation.
    client.portal.call(run, accept("REPLACEMENT_INPUT"))
    assert len(compactions) == 1
    replacement = sent[-1]["input"]
    assert len(replacement) == len(compacted_items) + 1
    assert replacement[:-1] == compacted_items
    assert json.loads(replacement[-1]["content"]) == {
        "interview_sequence": 4,
        "speaker": "employee",
        "text": "REPLACEMENT_INPUT",
    }
    assert "CANCELLED_INPUT" not in json.dumps(sent[-1]["input"])
    # The previous request is consumed by preparation, not inherited forever.
    client.portal.call(run, accept("NEXT_INPUT"))
    assert len(compactions) == 1


@pytest.mark.parametrize("status", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_abandoned_compaction_request_does_not_escape_into_replacement_work(
    client: TestClient,
    status: ExecutionStatus,
) -> None:
    writer = admit_writer(client)
    role = AgentRole.JOB_CONSULTANT
    tools = ContextCompactionTools(
        RoleContextHistory(client.app.state.database.sessions, writer, role, InMemorySaver())
    )
    command = tools.prepare("{}")
    assert isinstance(command, dict)
    prepared = prepare(client, writer)
    assert json.loads(client.portal.call(tools.execute, command)) == {"status": "requested"}
    transact(client, lambda s: executions.finish_execution(s, writer, status))
    with pytest.raises(ExecutionStateError):
        client.portal.call(tools.execute, command)

    replacement = admit_writer(client, job_file_id=writer.scope.job_file_id)
    binding = transact(client, lambda s: history.bind_context_history(s, replacement, role))
    assert binding.base == prepared
    assert not transact(
        client,
        lambda s: history.read_completed_compaction_request(
            s,
            writer.scope.job_file_id,
            role,
            binding.base,
        ),
    )


def test_compaction_tool_rejects_model_scope_and_foreign_saved_intent(client: TestClient) -> None:
    writer = admit_writer(client)
    tools = ContextCompactionTools(
        RoleContextHistory(
            client.app.state.database.sessions,
            writer,
            AgentRole.JOB_CONSULTANT,
            InMemorySaver(),
        )
    )
    rejected = tools.prepare('{"execution_id":"model-must-not-select-scope"}')
    assert isinstance(rejected, str)
    assert json.loads(rejected)["code"] == "invalid_arguments"
    command = tools.prepare("{}")
    assert isinstance(command, dict)
    with pytest.raises(HistoryConflictError, match="Prepare"):
        client.portal.call(tools.execute, command)
    prepare(client, writer)
    with pytest.raises(ValueError, match="another role or execution"):
        client.portal.call(tools.execute, {**command, "execution_id": str(uuid4())})
    assert json.loads(client.portal.call(tools.execute, command)) == {"status": "requested"}
