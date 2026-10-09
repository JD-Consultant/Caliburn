"""B2 sees what B1 changed since the batch began, including what no understanding cites yet."""

import asyncio
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import psycopg
import pytest

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    MemoryPermissionError,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.features.work_memory.stage_changes import build_situation_handoff_changes
from caliburn.settings import DatabaseSettings
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_stage_changes import read_situation_handoff_snapshot
from tests.fixtures.memory_owner import publish_memory_owner_fixture

pytestmark = pytest.mark.postgres
SITUATION = MemoryLayer.WORK_SITUATION
UNDERSTANDING = MemoryLayer.WORK_UNDERSTANDING
UNCHANGED_BODY = "每日下班前現場複點。"


def execute[T](settings: DatabaseSettings, operation: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            return await operation(database)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


def add_interview(
    connection: psycopg.Connection, file_id: UUID, source_id: UUID, sequence: int, speaker: str
) -> None:
    connection.execute(
        "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
        "VALUES (%s,%s,%s,'合成盤點訪談')",
        (file_id, source_id, speaker),
    )
    connection.execute(
        "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
        "VALUES (%s,%s,%s)",
        (file_id, sequence, source_id),
    )


@pytest.fixture
def sources(database_connection: psycopg.Connection) -> tuple[UUID, UUID, UUID]:
    """A file whose first batch covers employee source 2 and whose second covers source 4."""
    file_id, first, second = uuid4(), uuid4(), uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'差異','差異','合成員工')",
        (file_id,),
    )
    add_interview(database_connection, file_id, uuid4(), 1, "app")
    add_interview(database_connection, file_id, first, 2, "employee")
    add_interview(database_connection, file_id, uuid4(), 3, "consultant")
    add_interview(database_connection, file_id, second, 4, "employee")
    return file_id, first, second


async def start(database: Database, file_id: UUID, source_id: UUID):
    scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        runner = await executions.claim_writer(session, scope, writer_id=uuid4())
    workflow = MemoryCandidateWorkflow(database.sessions)
    position = await workflow.start(runner, source_id)
    assert position is not None
    return workflow, runner, position


def test_b2_handoff_names_added_removed_renamed_edited_and_changed_back_situations(
    database_settings: DatabaseSettings, sources: tuple[UUID, UUID, UUID]
) -> None:
    file_id, first, second = sources

    async def scenario(database: Database) -> None:
        # Batch one publishes five situations and one understanding citing two of them.
        workflow, runner, position = await start(database, file_id, first)
        ids: dict[str, UUID] = {}
        for key, title, body in (
            ("inventory", "每月盤點", "每月核對實物。"),
            ("returns", "客戶退貨", "檢查外觀與數量後入庫。"),
            ("inspection", "設備巡檢", "每週巡檢設備。"),
            ("packing", "包裝檢查", "出貨前檢查包裝。"),
            ("stable", "現場複點", UNCHANGED_BODY),
        ):
            created = await workflow.edit(
                runner,
                CreateMemoryObject(
                    uuid4(),
                    position,
                    SITUATION,
                    MemoryContent(title, "說明", body),
                    frozenset({first}),
                ),
            )
            ids[key], position = created.object_id, created.position
        stage = await workflow.handoff(runner, position, uuid4())
        understanding = await workflow.edit(
            runner,
            CreateMemoryObject(
                uuid4(),
                stage,
                UNDERSTANDING,
                MemoryContent("庫存管理", "盤點與退貨", "依約定範圍盤點並處理退貨。"),
                frozenset({ids["inventory"], ids["returns"]}),
            ),
        )
        published = await publish_memory_owner_fixture(
            workflow.sessions, runner, understanding.position, uuid4()
        )
        assert published.covered_through_sequence == 2

        # Batch two: B1 edits situations, then B2 receives what changed.
        workflow, runner, position = await start(database, file_id, second)

        async def revise(key: str, changes: MemoryContentChanges) -> None:
            nonlocal position
            result = await workflow.edit(
                runner, ReviseMemoryObject(uuid4(), position, SITUATION, ids[key], changes)
            )
            position = result.position

        await revise("inventory", MemoryContentChanges(body="每月核對實物並回報差異。"))
        await revise("returns", MemoryContentChanges(title="客戶退貨處理"))
        await revise("packing", MemoryContentChanges(body="出貨前檢查包裝與標籤。"))
        await revise("packing", MemoryContentChanges(body="出貨前檢查包裝。"))  # changed back
        deleted = await workflow.edit(
            runner, DeleteMemoryObject(uuid4(), position, SITUATION, ids["inspection"])
        )
        added = await workflow.edit(
            runner,
            CreateMemoryObject(
                uuid4(),
                deleted.position,
                SITUATION,
                MemoryContent("年度盤點", "少見的全倉盤點", "每年十二月配合財務全倉盤點。"),
                frozenset({second}),
            ),
        )
        b2 = await workflow.handoff(runner, added.position, uuid4())

        async with database.sessions() as session:
            snapshot = await read_situation_handoff_snapshot(session, b2)
        changes = build_situation_handoff_changes(snapshot)
        by_title = {change["target_title"]: change for change in changes}

        # Every kind is named exactly once; the untouched situation is not reported.
        assert set(by_title) == {"每月盤點", "客戶退貨處理", "設備巡檢", "包裝檢查", "年度盤點"}
        assert "現場複點" not in by_title

        edited = by_title["每月盤點"]
        assert edited["change"] == "modified"
        assert edited["affected_understanding_titles"] == ["庫存管理"]
        assert "-每月核對實物。" in str(edited["diff"])
        assert "+每月核對實物並回報差異。" in str(edited["diff"])

        renamed = by_title["客戶退貨處理"]
        assert renamed["change"] == "modified"
        assert renamed["previous_title"] == "客戶退貨"
        assert renamed["affected_understanding_titles"] == ["庫存管理"]

        removed = by_title["設備巡檢"]
        assert removed["change"] == "removed"
        assert removed["affected_understanding_titles"] == []
        assert "每週巡檢設備。" in str(removed["diff"])

        # Changed back: a new revision exists but the net text and sources equal the origin,
        # so B2 is told plainly instead of being shown an empty or invented diff.
        reverted = by_title["包裝檢查"]
        assert reverted["change"] == "modified"
        assert "淨文字與來源集合相同" in str(reverted["diff"])

        # An addition with no dependent understanding is still visible to B2.
        new = by_title["年度盤點"]
        assert new["change"] == "added"
        assert new["affected_understanding_titles"] == []
        assert "每年十二月配合財務全倉盤點。" in str(new["diff"])

    execute(database_settings, scenario)


def test_only_the_understanding_stage_receives_situation_changes(
    database_settings: DatabaseSettings, sources: tuple[UUID, UUID, UUID]
) -> None:
    file_id, first, _second = sources

    async def scenario(database: Database) -> None:
        _workflow, _runner, situation_stage = await start(database, file_id, first)
        async with database.sessions() as session:
            with pytest.raises(MemoryPermissionError):
                await read_situation_handoff_snapshot(session, situation_stage)

    execute(database_settings, scenario)
