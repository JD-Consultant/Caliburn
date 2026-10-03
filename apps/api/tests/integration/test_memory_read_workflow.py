"""Real PostgreSQL reads honor role, fixed scope and current candidate identity."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
)
from caliburn.features.interviews.models import InterviewReadError, InterviewSpeaker
from caliburn.features.work_memory import read_queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryBatchPosition,
    MemoryCandidateStateError,
    MemoryPermissionError,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryContentChanges,
    MemoryMapEntry,
    MemoryTargetNotFoundError,
)
from caliburn.features.work_memory.read_models import MemoryReadView
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.memory_reads import MemoryReadTools
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import (
    CandidateMemoryRead,
    MemoryReadWorkflow,
    PublishedMemoryRead,
)

pytestmark = pytest.mark.postgres
SITUATION = MemoryLayer.WORK_SITUATION
UNDERSTANDING = MemoryLayer.WORK_UNDERSTANDING


def execute[T](settings: DatabaseSettings, operation: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            return await operation(database)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


@pytest.fixture
def source(database_connection: psycopg.Connection) -> tuple[UUID, UUID]:
    file_id, source_id = uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'讀取','讀取','合成人員')",
        (file_id, uuid4()),
    )
    for sequence, message_id, speaker, text in [
        (1, uuid4(), "app", "請描述工作。"),
        (2, source_id, "employee", "每月盤點\n並回報差異。"),
        (3, uuid4(), "consultant", "哪些差異？"),
        (4, uuid4(), "employee", "補充的新訪談"),
    ]:
        database_connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,%s)",
            (file_id, message_id, speaker, text),
        )
        database_connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "VALUES (%s,%s,%s)",
            (file_id, sequence, message_id),
        )
    return file_id, source_id


async def start(
    database: Database, source: tuple[UUID, UUID]
) -> tuple[MemoryCandidateWorkflow, ExecutionWriter, MemoryBatchPosition]:
    scope = ExecutionScope(source[0], uuid4(), ExecutionKind.MEMORY_BATCH)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
    workflow = MemoryCandidateWorkflow(database.sessions)
    stage = await workflow.start(writer, source[1])
    assert stage is not None
    return workflow, writer, stage


def test_candidate_map_includes_changes_after_its_stage_started(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, writer, stage = await start(database, source)
        reads = MemoryReadWorkflow(database.sessions)
        binding = CandidateMemoryRead(writer.scope, stage)
        assert await reads.read_map(binding, SITUATION) == ()
        await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(), stage, SITUATION, MemoryContent("盤點", "每月庫存", "核對實物。")
            ),
        )
        assert [item.title for item in await reads.read_map(binding, SITUATION)] == ["盤點"]

    execute(database_settings, scenario)


async def consultant(database: Database, file_id: UUID) -> ExecutionWriter:
    scope = ExecutionScope(file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        return await executions.claim_writer(session, scope, writer_id=uuid4())


def test_navigation_follows_candidate_identity_but_consultant_stays_on_published_snapshot(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, writer, stage = await start(database, source)
        case = await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                SITUATION,
                MemoryContent("盤點", "每月庫存", "舊正文"),
                frozenset({source[1]}),
            ),
        )
        stage_b2 = await workflow.handoff(writer, case.position, uuid4())
        understanding = await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage_b2,
                UNDERSTANDING,
                MemoryContent("管理", "庫存管理", "理解正文"),
                frozenset({case.object_id}),
            ),
        )
        first = await workflow.publish(writer, understanding.position, uuid4())
        advisor = await consultant(database, source[0])
        pinned = PublishedMemoryRead(advisor.scope, first.snapshot_id, 4)
        reads = MemoryReadWorkflow(database.sessions)
        old_read = await reads.read_object(pinned, UNDERSTANDING, "管理")
        assert [item.title for item in old_read.work_situation_references] == ["盤點"]
        assert (await reads.read_object(pinned, SITUATION, "盤點")).interview_references == (2,)

        later_source = (await reads.read_interview_messages(pinned, (4,)))[0].source_id
        workflow, writer, stage = await start(database, (source[0], later_source))
        renamed = await workflow.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                SITUATION,
                case.object_id,
                MemoryContentChanges(title="月末盤點", body="新版正文"),
            ),
        )
        reused = await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(), renamed.position, SITUATION, MemoryContent("盤點", "新物件", "另一個物件")
            ),
        )
        stage_b2 = await workflow.handoff(writer, reused.position, uuid4())
        current = CandidateMemoryRead(writer.scope, stage_b2)
        latest_read = await reads.read_object(current, UNDERSTANDING, "管理")
        assert [item.title for item in latest_read.work_situation_references] == ["月末盤點"]
        assert (await reads.read_object(current, SITUATION, "盤點")).content.body == "另一個物件"
        assert (await reads.read_object(current, SITUATION, "月末盤點")).content.body == "新版正文"
        await workflow.publish(writer, stage_b2, uuid4())
        assert await reads.read_object(pinned, UNDERSTANDING, "管理") == old_read
        assert (await reads.read_object(pinned, SITUATION, "盤點")).content.body == "舊正文"
        with pytest.raises(MemoryTargetNotFoundError):
            await reads.read_object(pinned, SITUATION, "月末盤點")

    execute(database_settings, scenario)


def test_candidate_reads_enforce_role_stage_and_fixed_interview_frontier(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, writer, stage = await start(database, source)
        reads = MemoryReadWorkflow(database.sessions)
        b1 = CandidateMemoryRead(writer.scope, stage)
        with pytest.raises(MemoryPermissionError):
            await reads.read_map(b1, UNDERSTANDING)
        with pytest.raises(MemoryPermissionError):
            await reads.read_object(b1, UNDERSTANDING, "不存在")
        messages = await reads.read_interview_messages(b1, (2, 1, 2))
        assert [message.interview_sequence for message in messages] == [1, 2]
        assert messages[0].speaker == InterviewSpeaker.APP
        assert messages[1].interview_text == "每月盤點\n並回報差異。"
        with pytest.raises(InterviewReadError):
            await reads.read_interview_range(b1, start_sequence=1, end_sequence=3)
        stage_b2 = await workflow.handoff(writer, stage, uuid4())
        b2 = CandidateMemoryRead(writer.scope, stage_b2)
        assert await reads.read_map(b2, UNDERSTANDING) == ()
        assert len(await reads.read_interview_range(b2, start_sequence=1, end_sequence=2)) == 2
        with pytest.raises(InterviewReadError):
            await reads.read_interview_messages(b2, (2, 3))
        with pytest.raises(MemoryCandidateStateError):
            await reads.read_map(b1, SITUATION)
        with pytest.raises(MemoryCandidateStateError):
            await reads.read_interview_messages(b1, (1,))

    execute(database_settings, scenario)


def test_absent_pinned_snapshot_stays_empty_and_cancelled_turn_cannot_read(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        advisor = await consultant(database, source[0])
        pinned = PublishedMemoryRead(advisor.scope, None, 3)
        reads = MemoryReadWorkflow(database.sessions)
        assert await reads.read_map(pinned, SITUATION) == ()
        workflow, writer, stage = await start(database, source)
        created = await workflow.edit(
            writer,
            CreateMemoryObject(uuid4(), stage, SITUATION, MemoryContent("盤點", "庫存", "正文")),
        )
        stage_b2 = await workflow.handoff(writer, created.position, uuid4())
        await workflow.publish(writer, stage_b2, uuid4())
        assert await reads.read_map(pinned, SITUATION) == ()
        with pytest.raises(MemoryTargetNotFoundError):
            await reads.read_object(pinned, SITUATION, "盤點")
        with pytest.raises(InterviewReadError):
            await reads.read_interview_messages(pinned, (4,))
        assert len(await reads.read_interview_range(pinned, start_sequence=1, end_sequence=3)) == 3
        async with database.sessions.begin() as session:
            await executions.finish_execution(session, advisor, ExecutionStatus.CANCELLED)
        with pytest.raises(ExecutionStateError):
            await reads.read_map(pinned, SITUATION)
        with pytest.raises(ExecutionStateError):
            await reads.read_interview_messages(pinned, (1,))

    execute(database_settings, scenario)


def test_title_selection_and_body_remain_in_one_read_position_during_a_new_edit(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario(database: Database) -> None:
        workflow, writer, stage = await start(database, source)
        created = await workflow.edit(
            writer,
            CreateMemoryObject(uuid4(), stage, SITUATION, MemoryContent("盤點", "庫存", "原物件")),
        )
        original_read_map = read_queries.read_map

        async def change_after_selection(
            session: AsyncSession, view: MemoryReadView
        ) -> tuple[MemoryMapEntry, ...]:
            entries = await original_read_map(session, view)
            removed = await workflow.edit(
                writer, DeleteMemoryObject(uuid4(), created.position, SITUATION, created.object_id)
            )
            await workflow.edit(
                writer,
                CreateMemoryObject(
                    uuid4(), removed.position, SITUATION, MemoryContent("盤點", "新庫存", "新物件")
                ),
            )
            return entries

        monkeypatch.setattr(read_queries, "read_map", change_after_selection)
        reads = MemoryReadWorkflow(database.sessions)
        result = await reads.read_object(
            CandidateMemoryRead(writer.scope, stage), SITUATION, "盤點"
        )
        assert result.content.body == "原物件"
        monkeypatch.setattr(read_queries, "read_map", original_read_map)
        result = await reads.read_object(
            CandidateMemoryRead(writer.scope, stage), SITUATION, "盤點"
        )
        assert result.content.body == "新物件"

    execute(database_settings, scenario)


def test_model_tools_navigate_real_sources_without_exposing_internal_coordinates(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, writer, stage = await start(database, source)
        case = await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                SITUATION,
                MemoryContent("盤點", "庫存", "# 詳細\n原文保留"),
                frozenset({source[1]}),
            ),
        )
        reader = MemoryReadWorkflow(database.sessions)
        b1 = MemoryReadTools(reader, CandidateMemoryRead(writer.scope, stage))
        assert json.loads(await b1.invoke("read_work_situation_map", "{}")) == {
            "items": [{"target_title": "盤點", "description": "庫存"}]
        }
        assert json.loads(await b1.invoke("read_work_situation", '{"target_title":"盤點"}')) == {
            "title": "盤點",
            "description": "庫存",
            "body": "# 詳細\n原文保留",
            "interview_references": [2],
        }
        assert json.loads(
            await b1.invoke("read_interview", '{"query":{"kind":"messages","sequences":[2,1,2]}}')
        ) == {
            "data_kind": "historical_interview",
            "messages": [
                {"interview_sequence": 1, "speaker": "app", "text": "請描述工作。"},
                {"interview_sequence": 2, "speaker": "employee", "text": "每月盤點\n並回報差異。"},
            ],
        }
        phase = await workflow.handoff(writer, case.position, uuid4())
        await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                phase,
                UNDERSTANDING,
                MemoryContent("庫存管理", "責任", "理解正文"),
                frozenset({case.object_id}),
            ),
        )
        b2 = MemoryReadTools(reader, CandidateMemoryRead(writer.scope, phase))
        assert json.loads(
            await b2.invoke("read_work_understanding", '{"target_title":"庫存管理"}')
        ) == {
            "title": "庫存管理",
            "description": "責任",
            "body": "理解正文",
            "work_situation_references": [{"target_title": "盤點", "description": "庫存"}],
        }
        assert set(b1.names) == {"read_work_situation_map", "read_work_situation", "read_interview"}
        assert set(b2.names) == {
            *b1.names,
            "read_work_understanding_map",
            "read_work_understanding",
        }

    execute(database_settings, scenario)


def test_model_read_rejections_are_actionable_not_partial_or_false_empty_success(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        workflow, writer, stage = await start(database, source)
        reader = MemoryReadWorkflow(database.sessions)
        tools = MemoryReadTools(reader, CandidateMemoryRead(writer.scope, stage))
        for name, arguments, code in [
            ("read_work_understanding", '{"target_title":"管理"}', "scope_not_allowed"),
            ("read_work_situation_map", '{"snapshot_id":"forged"}', "invalid_arguments"),
            ("read_work_situation", '{"target_title":"不存在"}', "target_not_found"),
            ("read_work_situation", '{"target_title":" "}', "invalid_arguments"),
            (
                "read_interview",
                '{"query":{"kind":"messages","sequences":[2,3]}}',
                "scope_not_allowed",
            ),
            (
                "read_interview",
                '{"query":{"kind":"range","start_sequence":2,"end_sequence":1}}',
                "invalid_arguments",
            ),
        ]:
            rejected = json.loads(await tools.invoke(name, arguments))
            assert rejected["status"] == "rejected"
            assert rejected["code"] == code
            assert set(rejected) == {"status", "code", "message", "next_action"}
        tiny = MemoryReadTools(reader, tools.binding, max_result_characters=1)
        assert (
            json.loads(
                await tiny.invoke("read_interview", '{"query":{"kind":"messages","sequences":[1]}}')
            )["code"]
            == "read_limit_exceeded"
        )
        await workflow.handoff(writer, stage, uuid4())
        assert (
            json.loads(await tools.invoke("read_work_situation_map", "{}"))["code"]
            == "target_stale"
        )

    execute(database_settings, scenario)
