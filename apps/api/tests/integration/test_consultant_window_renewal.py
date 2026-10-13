"""A rebuilds on publication, retains native history otherwise; real PG, scripted model."""

import asyncio
import json
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agent_execution.context_compaction import CompactionRuntime
from caliburn.agent_execution.request_capacity import ReceivedInputCount
from caliburn.agent_execution.tool_steps import read_completed_response_history
from caliburn.agents.job_consultant.context_binding import TurnContext, capture_turn_context
from caliburn.features.executions.history_models import AgentRole
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import candidate_service
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.work_memory import candidate_queries as memory
from caliburn.features.work_memory import read_queries
from caliburn.settings import DatabaseSettings
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_turns.context import ConsultantContextWorkflow
from caliburn.workflows.executions.context_history import RoleContextHistory
from tests.fixtures.native_response_runtime import run_response_loop
from tests.fixtures.response_capacity import synthetic_capacity_limits
from tests.fixtures.response_loop import LoopProbe, response_at
from tests.integration.test_compaction_accounting import runner as runner
from tests.integration.test_consultant_context_binding import publish_memory, start, template
from tests.unit.test_context_preparation import PreparationProbe

pytestmark = pytest.mark.postgres


async def capture(
    database: Database, work: RoleContextHistory, probe: PreparationProbe
) -> TurnContext:
    return await capture_turn_context(
        work,
        data=ConsultantContextWorkflow(database.sessions),
        template=template(),
        count_input=probe.count,
        runtime=CompactionRuntime(
            probe.compact, probe.account, work.ensure_active, synthetic_capacity_limits()
        ),
    )


async def complete(
    database: Database, work: RoleContextHistory, context: TurnContext, ordinal: int
) -> UUID:
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
        plan_position=context.plan_position,
    )
    return exchange.employee_input.source_id


@pytest.mark.parametrize("new_memory", [False, True])
def test_manual_net_is_complete_before_input_and_window_preparation(
    database_settings: DatabaseSettings, runner: asyncio.Runner, new_memory: bool
) -> None:
    from caliburn.features.job_description.conditions import (
        ConditionKind,
        CreateCondition,
        EditJdConditions,
    )
    from caliburn.features.job_description.models import (
        ProfileField,
        ReviseJdProfile,
        SetProfileField,
    )
    from caliburn.workflows.job_description.manual_editing import JdEditingWorkflow

    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as saver:
                await saver.setup()
                first = await start(database, "已完成原話")
                work = RoleContextHistory(database.sessions, first, AgentRole.JOB_CONSULTANT, saver)
                initial = await capture(database, work, PreparationProbe())
                await work.request_compaction()
                source_id = await complete(database, work, initial, 1)
                editing = JdEditingWorkflow(database.sessions)
                base = await editing.read_profile(first.scope.job_file_id)
                changed = await editing.revise_profile(
                    first.scope.job_file_id,
                    ReviseJdProfile(
                        uuid4(),
                        base.revision_id,
                        (
                            SetProfileField(ProfileField.PURPOSE, "人工跨欄使命"),
                            SetProfileField(ProfileField.REPORTS_TO, "人工新主管"),
                        ),
                    ),
                )
                await editing.edit_conditions(
                    first.scope.job_file_id,
                    EditJdConditions(
                        uuid4(),
                        changed.revision_id,
                        CreateCondition(ConditionKind.WORK_ENVIRONMENT, "人工機房條件"),
                    ),
                )
                if new_memory:
                    await publish_memory(database, first.scope.job_file_id, source_id, "新記憶")
                second = await start(database, "本輪另談薪資", first.scope.job_file_id)
                following = RoleContextHistory(
                    database.sessions, second, AgentRole.JOB_CONSULTANT, saver
                )
                probe = PreparationProbe(128_000)
                captured = await capture(database, following, probe)
                items = captured.request.create_payload()["input"]
                net = items[-2]["content"]
                assert "人工最終差異" in net
                assert all(text in net for text in ("人工跨欄使命", "人工新主管", "人工機房條件"))
                assert json.loads(items[-1]["content"])["text"] == "本輪另談薪資"
                assert captured.reset_history is new_memory
                assert len(probe.compact_requests) == (0 if new_memory else 1)
                if not new_memory:
                    assert all(
                        "人工跨欄使命" not in json.dumps(payload, ensure_ascii=False)
                        for _, payload in probe.count_requests
                    )
        finally:
            await database.close()

    runner.run(scenario())


@pytest.mark.parametrize(
    "bootstrap_operation", ["interview_range", "memory_map", "jd_preview", "jd_alias"]
)
def test_first_window_contains_opening_once_and_same_publication_skips_bootstrap_io(
    database_settings: DatabaseSettings,
    runner: asyncio.Runner,
    monkeypatch: pytest.MonkeyPatch,
    bootstrap_operation: str,
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
                first = await start(database, "  首輪原話\n保留空白。 ")
                work = RoleContextHistory(database.sessions, first, AgentRole.JOB_CONSULTANT, saver)
                first_probe = PreparationProbe(128_000)
                initial = await capture(database, work, first_probe)
                items = initial.request.create_payload()["input"]
                assert initial.reset_history is True
                assert len(items) == 2
                reference = json.loads(items[0]["content"])
                assert reference["data_kind"] == "consultant_turn_reference"
                opening = reference["historical_interview"]["messages"]
                assert len(opening) == 1
                assert opening[0]["interview_sequence"] == 1
                assert opening[0]["speaker"] == "app"
                assert reference["work_situation_map"]["items"] == []
                assert reference["work_understanding_map"]["items"] == []
                assert reference["jd_map"]["responsibility_areas"] == []
                assert reference["jd_map"]["unassigned_work_tasks"] == []
                assert json.loads(items[-1]["content"]) == {
                    "interview_sequence": 2,
                    "speaker": "employee",
                    "text": "  首輪原話\n保留空白。 ",
                }
                assert first_probe.count_requests == []
                assert first_probe.compact_requests == []
                await complete(database, work, initial, 1)
                completed = await read_completed_response_history(
                    saver, thread_id=work.response_thread_id
                )

                second = await start(database, "第二輪原話", first.scope.job_file_id)
                following = RoleContextHistory(
                    database.sessions, second, AgentRole.JOB_CONSULTANT, saver
                )
                second_probe = PreparationProbe()

                async def reject_bootstrap_io(*_args: object, **_kwargs: object) -> None:
                    raise AssertionError(
                        f"Same-publication capture must not perform {bootstrap_operation}"
                    )

                # Restrict the guard to capture: completion and other owners may read
                # these sources, while this retained window already contains them.
                with monkeypatch.context() as capture_io:
                    owner, operation = {
                        "interview_range": (interviews, "read_interview_range"),
                        "memory_map": (read_queries, "read_map"),
                        "jd_preview": (candidate_service, "read_preview"),
                        "jd_alias": (JdModelReferences, "assign"),
                    }[bootstrap_operation]
                    capture_io.setattr(owner, operation, reject_bootstrap_io)
                    next_turn = await capture(database, following, second_probe)
                next_items = next_turn.request.create_payload()["input"]
                assert next_turn.reset_history is False
                assert next_items[:-1] == completed.items
                assert json.loads(next_items[-1]["content"]) == {
                    "interview_sequence": 4,
                    "speaker": "employee",
                    "text": "第二輪原話",
                }
                assert len(second_probe.count_requests) == 1
                assert second_probe.count_requests[0][1]["input"] == completed.items
                assert second_probe.compact_requests == []
                assert next_turn.candidate_position.scope != initial.candidate_position.scope
        finally:
            await database.close()

    runner.run(scenario())


def test_interrupted_preparation_resumes_captured_version_after_memory_publication(
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
            role = AgentRole.JOB_CONSULTANT
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                first = await start(database, "已完成的月盤點原話")
                first_work = RoleContextHistory(database.sessions, first, role, saver)
                initial = await capture(database, first_work, PreparationProbe())
                first_source = await complete(database, first_work, initial, 1)
                completed = await read_completed_response_history(
                    saver, thread_id=first_work.response_thread_id
                )

                from caliburn.features.job_description.models import (
                    ProfileField,
                    ReviseJdProfile,
                    SetProfileField,
                )
                from caliburn.workflows.job_description.manual_editing import JdEditingWorkflow

                editing = JdEditingWorkflow(database.sessions)
                base = await editing.read_profile(first.scope.job_file_id)
                await editing.revise_profile(
                    first.scope.job_file_id,
                    ReviseJdProfile(
                        uuid4(),
                        base.revision_id,
                        (SetProfileField(ProfileField.PURPOSE, "中斷前固定的完整人工使命"),),
                    ),
                )
                second = await start(database, "  中斷前固定的本次原話\n ", first.scope.job_file_id)
                second_work = RoleContextHistory(database.sessions, second, role, saver)
                interrupted_probe = PreparationProbe()
                original_count = interrupted_probe.count

                async def interrupt_count(
                    request: ResponseRequest, request_id: UUID
                ) -> ReceivedInputCount:
                    await original_count(request, request_id)
                    raise RuntimeError("synthetic preparation interruption")

                # Count starts only after capture's data node has durably saved.
                with monkeypatch.context() as interruption:
                    interruption.setattr(interrupted_probe, "count", interrupt_count)
                    with pytest.raises(RuntimeError, match="synthetic preparation interruption"):
                        await capture(database, second_work, interrupted_probe)
                assert len(interrupted_probe.count_requests) == 1
                assert interrupted_probe.count_requests[0][1]["input"] == completed.items
                assert interrupted_probe.compact_requests == []

            published = await publish_memory(
                database, first.scope.job_file_id, first_source, "月盤點"
            )

            # Rebuild both saver and work; a resumed Turn cannot reconsider publication.
            async with AsyncPostgresSaver.from_conn_string(dsn) as rebuilt_saver:
                rebuilt_saver.serde = create_graph_serializer()
                rebuilt_work = RoleContextHistory(database.sessions, second, role, rebuilt_saver)
                resumed_probe = PreparationProbe()

                async def reject_latest_read(*_args: object, **_kwargs: object) -> None:
                    raise AssertionError("A captured Turn must not reread latest Memory")

                with monkeypatch.context() as resume_io:
                    resume_io.setattr(memory, "read_latest_snapshot", reject_latest_read)
                    restored = await capture(database, rebuilt_work, resumed_probe)
                items = restored.request.create_payload()["input"]
                assert restored.reset_history is False
                assert restored.memory_binding.snapshot_id == initial.memory_binding.snapshot_id
                assert restored.memory_binding.snapshot_id != published.snapshot_id
                assert items[:-2] == completed.items
                assert "人工最終差異" in items[-2]["content"]
                assert "中斷前固定的完整人工使命" in items[-2]["content"]
                assert json.loads(items[-1]["content"]) == {
                    "interview_sequence": 4,
                    "speaker": "employee",
                    "text": "  中斷前固定的本次原話\n ",
                }
                assert len(resumed_probe.count_requests) == 1
                assert resumed_probe.count_requests[0][1]["input"] == completed.items
                assert resumed_probe.compact_requests == []
        finally:
            await database.close()

    runner.run(scenario())


def test_new_publication_rebuilds_strict_tail_without_counting_or_compacting_discarded_history(
    database_settings: DatabaseSettings, runner: asyncio.Runner
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
                role = AgentRole.JOB_CONSULTANT
                first = await start(database, "已涵蓋的月盤點原話")
                work = RoleContextHistory(database.sessions, first, role, saver)
                first_context = await capture(database, work, PreparationProbe())
                first_source = await complete(database, work, first_context, 1)
                second = await start(database, "未涵蓋的季補貨原話", first.scope.job_file_id)
                second_work = RoleContextHistory(database.sessions, second, role, saver)
                second_context = await capture(database, second_work, PreparationProbe())
                await complete(database, second_work, second_context, 2)
                published = await publish_memory(
                    database, first.scope.job_file_id, first_source, "月盤點"
                )

                third = await start(database, "新版後新輸入", first.scope.job_file_id)
                third_work = RoleContextHistory(database.sessions, third, role, saver)
                # An old window at the threshold would compact if read before reset.
                probe = PreparationProbe(128_000)
                renewed = await capture(database, third_work, probe)
                items = renewed.request.create_payload()["input"]
                assert renewed.reset_history is True
                assert renewed.memory_binding.snapshot_id == published.snapshot_id
                assert renewed.memory_binding.interview_through_sequence == 5
                assert len(items) == 2
                reference = json.loads(items[0]["content"])
                assert reference["data_kind"] == "consultant_turn_reference"
                assert reference["work_situation_map"]["items"] == [
                    {"target_title": "月盤點", "description": "固定導覽描述"}
                ]
                messages = reference["historical_interview"]["messages"]
                assert [(m["interview_sequence"], m["speaker"]) for m in messages] == [
                    (3, "consultant"),
                    (4, "employee"),
                    (5, "consultant"),
                ]
                assert messages[1]["text"] == "未涵蓋的季補貨原話"
                assert reference["interview_read_boundary"]["covered_through_sequence"] == 2
                assert reference["interview_read_boundary"]["through_sequence"] == 5
                assert reference["jd_map"]["responsibility_areas"] == []
                assert reference["jd_map"]["unassigned_work_tasks"] == []
                assert json.loads(items[-1]["content"]) == {
                    "interview_sequence": 6,
                    "speaker": "employee",
                    "text": "新版後新輸入",
                }
                assert all("type" not in item for item in items)
                assert "已涵蓋的月盤點原話" not in json.dumps(items, ensure_ascii=False)
                assert probe.count_requests == []
                assert probe.compact_requests == []
                assert probe.accounts == []
        finally:
            await database.close()

    runner.run(scenario())


def test_cancelled_first_turn_on_new_publication_rebuilds_again_and_reuses_input_sequence(
    database_settings: DatabaseSettings, runner: asyncio.Runner
) -> None:
    from caliburn.features.job_description.models import (
        ProfileField,
        ReviseJdProfile,
        SetProfileField,
    )
    from caliburn.workflows.job_description.manual_editing import JdEditingWorkflow

    async def scenario() -> None:
        database = Database(database_settings)
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
                saver.serde = create_graph_serializer()
                await saver.setup()
                role = AgentRole.JOB_CONSULTANT
                first = await start(database, "已完成的工作原話")
                work = RoleContextHistory(database.sessions, first, role, saver)
                initial = await capture(database, work, PreparationProbe())
                await work.request_compaction()
                source = await complete(database, work, initial, 1)
                editing = JdEditingWorkflow(database.sessions)
                profile = await editing.read_profile(first.scope.job_file_id)
                await editing.revise_profile(
                    first.scope.job_file_id,
                    ReviseJdProfile(
                        uuid4(),
                        profile.revision_id,
                        (SetProfileField(ProfileField.PURPOSE, "取消仍留下完整人工使命"),),
                    ),
                )
                published = await publish_memory(
                    database, first.scope.job_file_id, source, "固定工作"
                )
                cancelled = await start(database, "取消輪不應接到後輪", first.scope.job_file_id)
                cancelled_work = RoleContextHistory(database.sessions, cancelled, role, saver)
                cancelled_context = await capture(database, cancelled_work, PreparationProbe())
                assert cancelled_context.reset_history is True
                cancelled_items = cancelled_context.request.create_payload()["input"]
                assert "人工最終差異" in cancelled_items[-2]["content"]
                assert "取消仍留下完整人工使命" in cancelled_items[-2]["content"]
                cancelled_sequence = json.loads(cancelled_items[-1]["content"])[
                    "interview_sequence"
                ]
                # Save native output without formalizing the Turn, then cancel its owner.
                # The next Turn must ignore this suffix as well as the captured input.
                await run_response_loop(
                    saver,
                    thread_id=cancelled_work.response_thread_id,
                    request=cancelled_context.request,
                    runtime=LoopProbe([response_at(2, final=True)]).runtime(),
                    max_tool_calls=4,
                    max_model_steps=2,
                )
                await ConsultantCompletionWorkflow(database.sessions).stop(
                    cancelled, ExecutionStatus.CANCELLED
                )

                next_writer = await start(database, "取消後新原話", first.scope.job_file_id)
                next_work = RoleContextHistory(database.sessions, next_writer, role, saver)
                probe = PreparationProbe(128_000)
                rebuilt = await capture(database, next_work, probe)
                items = rebuilt.request.create_payload()["input"]
                assert rebuilt.reset_history is True
                assert rebuilt.memory_binding.snapshot_id == published.snapshot_id
                assert rebuilt.current_input_source_id != cancelled_context.current_input_source_id
                assert len(items) == 3
                assert items[:-1] == cancelled_items[:-1]
                assert json.loads(items[-1]["content"]) == {
                    "interview_sequence": cancelled_sequence,
                    "speaker": "employee",
                    "text": "取消後新原話",
                }
                assert "取消輪不應接到後輪" not in json.dumps(items, ensure_ascii=False)
                assert probe.count_requests == []
                assert probe.compact_requests == []
                await complete(database, next_work, rebuilt, 3)
        finally:
            await database.close()

    runner.run(scenario())


def test_same_publication_compaction_retains_complete_output_without_app_reprojection(
    database_settings: DatabaseSettings, runner: asyncio.Runner
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
                first = await start(database, "已完成原話")
                work = RoleContextHistory(database.sessions, first, AgentRole.JOB_CONSULTANT, saver)
                initial = await capture(database, work, PreparationProbe())
                await complete(database, work, initial, 1)
                next_writer = await start(database, "壓縮後新輸入", first.scope.job_file_id)
                next_work = RoleContextHistory(
                    database.sessions, next_writer, AgentRole.JOB_CONSULTANT, saver
                )
                probe = PreparationProbe(128_000)
                context = await capture(database, next_work, probe)
                items = context.request.create_payload()["input"]
                assert context.reset_history is False
                assert items[:-1] == probe.window
                assert json.loads(items[-1]["content"]) == {
                    "interview_sequence": 4,
                    "speaker": "employee",
                    "text": "壓縮後新輸入",
                }
                assert len(probe.count_requests) == 1
                assert len(probe.compact_requests) == 1
                assert len(probe.accounts) == 1
        finally:
            await database.close()

    runner.run(scenario())
