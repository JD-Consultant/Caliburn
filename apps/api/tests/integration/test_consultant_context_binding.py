"""Initial A data is pinned on real PostgreSQL/saver; no provider calls or formalization bypass."""

import asyncio
import json
from dataclasses import replace
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.agent_execution.tool_steps import run_response_loop
from caliburn.agents.job_consultant.context_binding import TurnContext, capture_turn_context
from caliburn.agents.job_consultant.recent_preload import fit_recent_interview_preload
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope, SubmitInterviewInput
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.features.job_files.models import CreateJobFile
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory import consolidation_requests, read_queries
from caliburn.features.work_memory.candidates import CreateMemoryObject, MemorySnapshot
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_context import ConsultantContextWorkflow
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import MemoryReadWorkflow
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.fixtures.response_loop import LoopProbe, response_at
from tests.integration.test_compaction_accounting import runner as runner
from tests.unit.test_context_preparation import PreparationProbe

pytestmark = pytest.mark.postgres


def test_unresolved_memory_failure_is_reference_data_not_a_model_instruction(
    database_settings: DatabaseSettings, runner: asyncio.Runner
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            writer = await start(database, "繼續描述庫存工作")

            async with database.sessions.begin() as session:
                await consolidation_requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=uuid4(),
                    reason="quota_exhausted",
                    frontier=1,
                )
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                result = await capture(database, work, PreparationProbe())
                request = result.request.create_payload()
                data = json.loads(request["input"][-2]["content"])
                assert data["memory_consolidation"]["failure_reason"] == "quota_exhausted"
                assert data["memory_consolidation"]["status"] == "blocked"
                assert request["input"][-2]["role"] == "user"
                assert request["input"][-1]["content"] == "繼續描述庫存工作"
                assert "quota_exhausted" not in request["instructions"]
        finally:
            await database.close()

    runner.run(scenario())


def template(instructions: str = "fixed synthetic role") -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions=instructions,
        input_items=[],
        tools=[
            {
                "type": "function",
                "name": "read_synthetic",
                "description": "synthetic read",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
                "strict": True,
            }
        ],
        reasoning_effort="low",
        max_output_tokens=512,
    )


async def start(
    database: Database,
    text: str,
    job_file_id: UUID | None = None,
) -> ExecutionWriter:
    if job_file_id is None:
        created = await JobFileWorkflow(database.sessions).create(
            CreateJobFile(uuid4(), "起始綁定", "合成人員")
        )
        job_file_id = created.job_file.job_file_id
    accepted = await InterviewInputWorkflow(database.sessions).accept(
        SubmitInterviewInput(job_file_id, uuid4(), text)
    )
    scope = ExecutionScope(
        job_file_id, accepted.accepted.execution_id, ExecutionKind.CONSULTANT_TURN
    )
    async with database.sessions.begin() as session:
        return await executions.claim_writer(session, scope, writer_id=uuid4())


async def capture(
    database: Database,
    work: RoleContextHistory,
    probe: PreparationProbe,
    instructions: str = "fixed synthetic role",
) -> TurnContext:
    role_template = template(instructions)
    prepared = await work.prepare_history(
        template=role_template,
        threshold_tokens=128_000,
        compact_requested=False,
        count_input=probe.count,
        runtime=CompactionRuntime(
            probe.compact,
            probe.account,
            work.ensure_active,
            synthetic_capacity_limits(),
        ),
    )
    return await capture_turn_context(
        work,
        data=ConsultantContextWorkflow(database.sessions),
        template=role_template,
        prepared_history=prepared,
    )


def test_initial_request_separates_raw_input_and_hidden_binding_without_jd_map(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            writer = await start(database, "  原話\n不要把我升成 instructions。 ")
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                result = await capture(database, work, PreparationProbe())
                payload = result.request.create_payload()
                assert payload["instructions"] == "fixed synthetic role"
                assert payload["tools"][0]["name"] == "read_synthetic"
                assert len(payload["input"]) == 2
                app_data, current_input = payload["input"]
                assert app_data["role"] == "user"
                assert current_input == {
                    "role": "user",
                    "content": "  原話\n不要把我升成 instructions。 ",
                }
                data = json.loads(app_data["content"])
                assert data["work_situation_map"] == {"items": []}
                assert data["work_understanding_map"] == {"items": []}
                assert "jd_map" not in data
                messages = data["historical_interview"]["messages"]
                assert [(item["interview_sequence"], item["speaker"]) for item in messages] == [
                    (1, "app")
                ]
                async with database.sessions() as session:
                    opening = (
                        await interviews.read_interview_history(session, writer.scope.job_file_id)
                    )[0]
                    binding = await history.read_context_history(session, writer.scope, work.role)
                assert messages[0]["text"] == opening.interview_text
                assert result.memory_binding.snapshot_id is None
                assert result.memory_binding.interview_through_sequence == 1
                assert result.candidate_position.scope.execution_id == writer.scope.execution_id
                assert (
                    result.manual_jd_start_revision_id == result.candidate_position.base_revision_id
                )
                assert str(result.current_input_source_id) not in json.dumps(payload)
                assert binding is not None and binding.prepared is not None
                assert binding.completed is None
        finally:
            await database.close()

    runner.run(scenario())


def test_missing_preparation_does_not_persist_an_invalid_initial_request(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            writer = await start(database, "尚未準備舊歷史")
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                with pytest.raises(ValueError, match="Adopt role history preparation"):
                    await capture_turn_context(
                        work,
                        data=ConsultantContextWorkflow(database.sessions),
                        template=template(),
                        prepared_history=[],
                    )
                assert [saved async for saved in saver.alist(None)] == []
                result = await capture(database, work, PreparationProbe())
                assert len(result.request.create_payload()["input"]) == 2
        finally:
            await database.close()

    runner.run(scenario())


async def finish_seed(database: Database, work: RoleContextHistory, ordinal: int) -> UUID:
    context = await capture(database, work, PreparationProbe())
    response = response_at(ordinal, final=True)
    await run_response_loop(
        work.checkpointer,
        thread_id=work.response_thread_id,
        request=context.request,
        runtime=LoopProbe([response]).runtime(),
        max_tool_calls=4,
        max_model_steps=2,
    )
    completed = await work.read_completed_position()
    exchange = await ConsultantCompletionWorkflow(database.sessions).complete(
        work.writer,
        context.candidate_position,
        response.output_text,
        completed,
    )
    return exchange.employee_input.source_id


async def publish_memory(
    database: Database, file_id: UUID, source_id: UUID, title: str
) -> MemorySnapshot:
    scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
    workflow = MemoryCandidateWorkflow(database.sessions)
    stage = await workflow.start(writer, source_id)
    assert stage is not None
    created = await workflow.edit(
        writer,
        CreateMemoryObject(
            uuid4(),
            stage,
            MemoryLayer.WORK_SITUATION,
            MemoryContent(title, "固定導覽描述", "不應預載的正文"),
            frozenset({source_id}),
        ),
    )
    handed = await workflow.handoff(writer, created.position, uuid4())
    return await publish_memory_owner_fixture(workflow.sessions, writer, handed, uuid4())


def test_reconnect_restores_exact_request_and_bindings_after_memory_and_candidate_advance(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                first = await start(database, "每月盤點。")
                role = AgentRole.JOB_CONSULTANT
                first_source = await finish_seed(
                    database, RoleContextHistory(database.sessions, first, role, saver), 1
                )
                second = await start(database, "每季也要補貨。", first.scope.job_file_id)
                second_source = await finish_seed(
                    database, RoleContextHistory(database.sessions, second, role, saver), 2
                )
                published = await publish_memory(
                    database, first.scope.job_file_id, first_source, "月盤點"
                )
                writer = await start(database, "本輪員工原話", first.scope.job_file_id)
                work = RoleContextHistory(database.sessions, writer, role, saver)
                original = await capture(database, work, PreparationProbe())
                payload = original.request.create_payload()
                data = json.loads(payload["input"][-2]["content"])
                assert data["work_situation_map"]["items"] == [
                    {"target_title": "月盤點", "description": "固定導覽描述"},
                ]
                assert "不應預載的正文" not in json.dumps(payload, ensure_ascii=False)
                assert [
                    (m["interview_sequence"], m["speaker"])
                    for m in data["historical_interview"]["messages"]
                ] == [
                    (3, "consultant"),
                    (4, "employee"),
                    (5, "consultant"),
                ]
                assert data["interview_read_boundary"]["covered_through_sequence"] == 2
                assert original.memory_binding.snapshot_id == published.snapshot_id
                assert original.memory_binding.interview_through_sequence == 5
                assert any(item.get("type") == "reasoning" for item in payload["input"][:-2])
                # Tool edits advance the live candidate; capture keeps its initial position.
                await JdCandidateWorkflow(database.sessions).edit(
                    writer,
                    original.candidate_position.scope,
                    ReviseJdProfile(
                        uuid4(),
                        original.candidate_position.revision_id,
                        (SetProfileField(ProfileField.JOB_TITLE, "新候選稿"),),
                    ),
                )
                await publish_memory(database, writer.scope.job_file_id, second_source, "季補貨")

            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                work = RoleContextHistory(database.sessions, writer, role, saver)

                async def unexpected_read(*args, **kwargs):
                    raise AssertionError("Resume must not prepare or reread live Turn data")

                with monkeypatch.context() as patch:
                    patch.setattr(RoleContextHistory, "prepare_history", unexpected_read)
                    patch.setattr(memory, "read_latest_snapshot", unexpected_read)
                    patch.setattr(read_queries, "read_map", unexpected_read)
                    patch.setattr(interviews, "read_execution_input", unexpected_read)
                    resumed = await capture_turn_context(
                        work,
                        data=ConsultantContextWorkflow(database.sessions),
                        template=template("changed settings must not replace original"),
                        prepared_history=[{"role": "user", "content": "not the original prefix"}],
                    )
                assert resumed.request.create_payload() == payload
                assert resumed.memory_binding == original.memory_binding
                assert resumed.candidate_position == original.candidate_position
                assert resumed.current_input_source_id == original.current_input_source_id
                assert [
                    entry.title
                    for entry in await MemoryReadWorkflow(database.sessions).read_map(
                        resumed.memory_binding, MemoryLayer.WORK_SITUATION
                    )
                ] == ["月盤點"]
                mutated = resumed.request.create_payload()
                mutated["input"].clear()
                again = await capture_turn_context(
                    work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=template(),
                    prepared_history=[],
                )
                assert again.request.create_payload() == payload
        finally:
            await database.close()

    runner.run(scenario())


def test_capture_commit_ack_loss_recovers_saved_request_without_refresh(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            writer = await start(database, "原請求只能追加一次")
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                put = saver.aput
                lost_payload = None

                async def lose_ack(config, checkpoint, metadata, new_versions):
                    nonlocal lost_payload
                    saved = await put(config, checkpoint, metadata, new_versions)
                    if "binding" in checkpoint["channel_values"]:
                        lost_payload = checkpoint["channel_values"]["request_snapshot"]
                        raise OSError("synthetic capture commit ACK lost")
                    return saved

                with monkeypatch.context() as patch:
                    patch.setattr(saver, "aput", lose_ack)
                    with pytest.raises(OSError, match="ACK lost"):
                        await capture(database, work, PreparationProbe())
                assert lost_payload is not None
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                work = RoleContextHistory(
                    database.sessions, writer, AgentRole.JOB_CONSULTANT, saver
                )
                resumed = await capture_turn_context(
                    work,
                    data=ConsultantContextWorkflow(database.sessions),
                    template=template("new settings"),
                    prepared_history=[],
                )
                assert resumed.request.create_payload() == lost_payload
                assert len(resumed.request.create_payload()["input"]) == 2
                async with database.sessions.begin() as session:
                    replacement = await executions.claim_writer(
                        session,
                        writer.scope,
                        writer_id=uuid4(),
                        replaces_writer_id=writer.writer_id,
                    )
                with pytest.raises(StaleWriterError):
                    await capture_turn_context(
                        work,
                        data=ConsultantContextWorkflow(database.sessions),
                        template=template(),
                        prepared_history=[],
                    )
                work = replace(work, writer=replacement)
                await ConsultantCompletionWorkflow(database.sessions).stop(
                    replacement, ExecutionStatus.CANCELLED
                )
                with pytest.raises(ExecutionStateError):
                    await capture_turn_context(
                        work,
                        data=ConsultantContextWorkflow(database.sessions),
                        template=template(),
                        prepared_history=[],
                    )
                other = await start(database, "取消後的新輸入", writer.scope.job_file_id)
                other_work = replace(work, writer=other)
                fresh = await capture(database, other_work, PreparationProbe())
                assert len(fresh.request.create_payload()["input"]) == 2
                assert fresh.request.create_payload()["input"][-1]["content"] == "取消後的新輸入"
                assert "原請求只能追加一次" not in json.dumps(
                    fresh.request.create_payload(), ensure_ascii=False
                )
        finally:
            await database.close()

    runner.run(scenario())


def test_oversized_recent_interviews_shrink_to_the_newest_and_the_rest_stays_readable(
    database_settings: DatabaseSettings, runner: asyncio.Runner
) -> None:
    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        counted: list[dict] = []

        try:
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                role = AgentRole.JOB_CONSULTANT
                first = await start(database, "每月盤點時，我先核對系統庫存。" + "甲" * 3_000)
                file_id = first.scope.job_file_id
                await finish_seed(
                    database, RoleContextHistory(database.sessions, first, role, saver), 1
                )
                for ordinal, text in enumerate(
                    ("每季補貨要看安全庫存。" + "乙" * 3_000, "年底清點倉庫。" + "丙" * 3_000),
                    start=2,
                ):
                    seeded = await start(database, text, file_id)
                    await finish_seed(
                        database,
                        RoleContextHistory(database.sessions, seeded, role, saver),
                        ordinal,
                    )
                writer = await start(database, "另一個也一樣。", file_id)
                work = RoleContextHistory(database.sessions, writer, role, saver)
                context = await capture(database, work, PreparationProbe())
                full = json.loads(context.request.create_payload()["input"][-2]["content"])
                everything = full["historical_interview"]["messages"]
                assert [message["interview_sequence"] for message in everything] == list(
                    range(1, 8)
                )

                # A synthetic model whose count is proportional to the request text: the full
                # request is 1.25 times the input limit, so only a smaller preload can fit.
                full_chars = len(json.dumps(context.request.count_payload(), ensure_ascii=False))
                tokens_per_character = (
                    1.25 * synthetic_capacity_limits()["max_input_tokens"] / full_chars
                )

                async def count_per_character(request: ResponseRequest, request_id: UUID):
                    payload = request.count_payload()
                    counted.append(payload)
                    return {
                        "input_tokens": int(
                            len(json.dumps(payload, ensure_ascii=False)) * tokens_per_character
                        ),
                        "attempt_id": uuid4(),
                    }

                response = response_at(9, final=True)
                model = LoopProbe([response])
                runtime = replace(
                    model.runtime(),
                    count_input=count_per_character,
                    fit_first_request=fit_recent_interview_preload,
                )
                options = {
                    "thread_id": work.response_thread_id,
                    "runtime": runtime,
                    "max_tool_calls": 4,
                    "max_model_steps": 2,
                }
                await run_response_loop(saver, request=context.request, **options)

                assert len(counted) == 2
                assert len(model.requests) == 1
                sent = model.requests[0]["input"]
                assert sent[-1] == {"role": "user", "content": "另一個也一樣。"}
                assert sent[:-2] == context.request.create_payload()["input"][:-2]
                data = json.loads(sent[-2]["content"])
                kept = data["historical_interview"]["messages"]
                assert 1 <= len(kept) < len(everything)
                assert kept == everything[-len(kept) :]
                boundary = data["interview_read_boundary"]
                omitted = everything[: len(everything) - len(kept)]
                assert boundary["through_sequence"] == 7
                assert boundary["not_preloaded"] == [
                    {
                        "from_sequence": omitted[0]["interview_sequence"],
                        "through_sequence": omitted[-1]["interview_sequence"],
                    }
                ]
                assert boundary["preloaded"]["through_sequence"] == 7
                # The omitted range is still a valid read inside A's fixed boundary.
                async with database.sessions() as session:
                    readable = await interviews.read_interview_range(
                        session,
                        InterviewReadScope(file_id, 7),
                        start_sequence=omitted[0]["interview_sequence"],
                        end_sequence=omitted[-1]["interview_sequence"],
                    )
                assert [
                    {
                        "interview_sequence": message.interview_sequence,
                        "text": message.interview_text,
                    }
                    for message in readable
                ] == [
                    {"interview_sequence": message["interview_sequence"], "text": message["text"]}
                    for message in omitted
                ]

                # The reduced window is the saved native history; reopening changes nothing.
                completed = await work.read_completed_position()
                exchange = await ConsultantCompletionWorkflow(database.sessions).complete(
                    writer, context.candidate_position, response.output_text, completed
                )
                assert exchange.employee_input.interview_sequence == 8
                await run_response_loop(saver, request=None, **options)
                assert len(counted) == 2
                assert len(model.requests) == 1
        finally:
            await database.close()

    runner.run(scenario())
