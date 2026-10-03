"""Real candidate transactions behind model-selected names and controlled body patches."""

import asyncio
import json
from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import psycopg
import pytest

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.interviews.models import InterviewScopeError
from caliburn.features.work_memory.body_matching import BodyEditError
from caliburn.features.work_memory.candidates import (
    MemoryCandidateStateError,
    MemoryEdit,
    MemoryEditResult,
    MemoryPermissionError,
)
from caliburn.features.work_memory.edit_intents import (
    CreateMemoryIntent,
    InterviewReferenceChange,
    InterviewSourceSelection,
    MemoryBodyChange,
    MemoryTextChange,
    ReviseMemoryIntent,
    SituationReferenceChange,
    SituationSourceSelection,
)
from caliburn.features.work_memory.edit_preparation import MemoryStatusPreview, MemoryUpdatePreview
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryReferenceNotFoundError,
    MemoryTitleConflictError,
)
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.memory_writes import MemoryWriteTools, PreparedMemoryToolCall
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import CandidateMemoryRead, MemoryReadWorkflow
from caliburn.workflows.memory_writes import MemoryWritePreparation

pytestmark = pytest.mark.postgres
SITUATION = MemoryLayer.WORK_SITUATION
UNDERSTANDING = MemoryLayer.WORK_UNDERSTANDING
BODY = "# 庫存\n每月核對。\n回報主管。"
PATCH = "@@\n # 庫存\n-每月核對。\n+每週核對。\n 回報主管。"


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
        "display_name,employee_name) VALUES (%s,%s,'寫入','寫入','合成人員')",
        (file_id, uuid4()),
    )
    for sequence, identity, speaker in [(1, uuid4(), "app"), (2, source_id, "employee")]:
        database_connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,'合成的盤點訪談')",
            (file_id, identity, speaker),
        )
        database_connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "VALUES (%s,%s,%s)",
            (file_id, sequence, identity),
        )
    return file_id, source_id


async def start(
    database: Database, source: tuple[UUID, UUID]
) -> tuple[ExecutionWriter, CandidateMemoryRead]:
    scope = ExecutionScope(source[0], uuid4(), ExecutionKind.MEMORY_BATCH)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
    stage = await MemoryCandidateWorkflow(database.sessions).start(writer, source[1])
    assert stage is not None
    return writer, CandidateMemoryRead(scope, stage)


async def create_situation(
    database: Database, writer: ExecutionWriter, binding: CandidateMemoryRead, title: str = "盤點"
) -> UUID:
    prepared = await MemoryWritePreparation(database.sessions).prepare(
        binding,
        command_id=uuid4(),
        layer=SITUATION,
        intent=CreateMemoryIntent(
            MemoryContent(title, "庫存核對", BODY), InterviewSourceSelection((2,))
        ),
    )
    assert prepared.preview == MemoryStatusPreview("created")
    return (
        await MemoryCandidateWorkflow(database.sessions).edit(writer, prepared.command)
    ).object_id


def test_prepare_and_apply_all_fields_and_sources_as_one_candidate_change(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        identity = await create_situation(database, writer, binding)
        reads = MemoryReadWorkflow(database.sessions)
        prepared = await MemoryWritePreparation(database.sessions).prepare(
            binding,
            command_id=uuid4(),
            layer=SITUATION,
            intent=ReviseMemoryIntent(
                "盤點",
                (
                    MemoryTextChange("title", "月末盤點"),
                    MemoryTextChange("description", "核對庫存並回報"),
                    MemoryBodyChange(PATCH),
                    InterviewReferenceChange(add=(1, 1), remove=(2,)),
                ),
            ),
        )
        assert (await reads.read_object(binding, SITUATION, "盤點")).content.body == BODY
        assert isinstance(prepared.preview, MemoryUpdatePreview)
        assert prepared.preview.changed_fields == ("title", "description")
        assert prepared.preview.added == (1,)
        assert prepared.preview.removed == (2,)
        assert (
            prepared.preview.body_diff is not None and "-每月核對。" in prepared.preview.body_diff
        )
        assert prepared.preview.body_diff != PATCH
        result = await MemoryCandidateWorkflow(database.sessions).edit(writer, prepared.command)
        assert result.object_id == identity
        after = await reads.read_object(binding, SITUATION, "月末盤點")
        assert after.content.body == BODY.replace("每月", "每週")
        assert after.content.description == "核對庫存並回報"
        assert after.interview_references == (1,)

    execute(database_settings, scenario)


def test_rejected_preparation_leaves_existing_candidate_and_source_unchanged(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        await create_situation(database, writer, binding)
        prepare = MemoryWritePreparation(database.sessions)
        with pytest.raises(BodyEditError):
            await prepare.prepare(
                binding,
                command_id=uuid4(),
                layer=SITUATION,
                intent=ReviseMemoryIntent(
                    "盤點",
                    (
                        MemoryTextChange("title", "不應採用"),
                        MemoryBodyChange(PATCH + "\n@@\n-不存在的原文\n+後段失敗"),
                        InterviewReferenceChange(add=(1,), remove=(2,)),
                    ),
                ),
            )
        with pytest.raises(InterviewScopeError):
            await prepare.prepare(
                binding,
                command_id=uuid4(),
                layer=SITUATION,
                intent=ReviseMemoryIntent(
                    "盤點",
                    (
                        MemoryBodyChange(PATCH),
                        InterviewReferenceChange(add=(3,)),
                    ),
                ),
            )
        with pytest.raises(MemoryReferenceNotFoundError):
            await prepare.prepare(
                binding,
                command_id=uuid4(),
                layer=SITUATION,
                intent=ReviseMemoryIntent("盤點", (InterviewReferenceChange(remove=(1,)),)),
            )
        await create_situation(database, writer, binding, "已有名稱")
        with pytest.raises(MemoryTitleConflictError):
            await prepare.prepare(
                binding,
                command_id=uuid4(),
                layer=SITUATION,
                intent=ReviseMemoryIntent("盤點", (MemoryTextChange("title", "已有名稱"),)),
            )
        original = await MemoryReadWorkflow(database.sessions).read_object(
            binding, SITUATION, "盤點"
        )
        assert original.content.body == BODY
        assert original.interview_references == (2,)

    execute(database_settings, scenario)


def test_original_prepared_command_replays_after_title_is_reused_without_retargeting(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        original_id = await create_situation(database, writer, binding)
        prepare = MemoryWritePreparation(database.sessions)
        prepared = await prepare.prepare(
            binding,
            command_id=uuid4(),
            layer=SITUATION,
            intent=ReviseMemoryIntent(
                "盤點", (MemoryTextChange("title", "月末盤點"), MemoryBodyChange(PATCH))
            ),
        )
        edits = MemoryCandidateWorkflow(database.sessions)
        first = await edits.edit(writer, prepared.command)
        new_id = await create_situation(database, writer, binding)
        assert new_id != original_id
        assert await edits.edit(writer, prepared.command) == first
        assert (
            await MemoryReadWorkflow(database.sessions).read_object(binding, SITUATION, "盤點")
        ).content.body == BODY
        next_prepared = await prepare.prepare(
            binding,
            command_id=uuid4(),
            layer=SITUATION,
            intent=ReviseMemoryIntent("盤點", (MemoryTextChange("description", "新的物件"),)),
        )
        assert (await edits.edit(writer, next_prepared.command)).object_id == new_id

    execute(database_settings, scenario)


def test_stale_prepared_write_cannot_silently_apply_against_new_position(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        await create_situation(database, writer, binding)
        prepared = await MemoryWritePreparation(database.sessions).prepare(
            binding,
            command_id=uuid4(),
            layer=SITUATION,
            intent=ReviseMemoryIntent("盤點", (MemoryBodyChange(PATCH),)),
        )
        await create_situation(database, writer, binding, "其他工作")
        with pytest.raises(MemoryCandidateStateError):
            await MemoryCandidateWorkflow(database.sessions).edit(writer, prepared.command)
        assert (
            await MemoryReadWorkflow(database.sessions).read_object(binding, SITUATION, "盤點")
        ).content.body == BODY

    execute(database_settings, scenario)


def test_b2_changes_its_own_relationships_without_duplicate_add_effect(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        await create_situation(database, writer, binding)
        edits = MemoryCandidateWorkflow(database.sessions)
        prepare = MemoryWritePreparation(database.sessions)
        # A role switch uses the latest position, not the original stage start.
        latest = await prepare.prepare(
            binding,
            command_id=uuid4(),
            layer=SITUATION,
            intent=ReviseMemoryIntent("盤點", (MemoryTextChange("description", "庫存核對"),)),
        )
        same = await edits.edit(writer, latest.command)
        phase = await edits.handoff(writer, same.position, uuid4())
        b2 = CandidateMemoryRead(writer.scope, phase)
        created = await prepare.prepare(
            b2,
            command_id=uuid4(),
            layer=UNDERSTANDING,
            intent=CreateMemoryIntent(
                MemoryContent("庫存管理", "核對責任", "依情境理解。"),
                SituationSourceSelection(("盤點", "盤點")),
            ),
        )
        await edits.edit(writer, created.command)
        unchanged = await prepare.prepare(
            b2,
            command_id=uuid4(),
            layer=UNDERSTANDING,
            intent=ReviseMemoryIntent("庫存管理", (SituationReferenceChange(add=("盤點",)),)),
        )
        assert unchanged.preview == MemoryStatusPreview("unchanged")
        await edits.edit(writer, unchanged.command)
        removed = await prepare.prepare(
            b2,
            command_id=uuid4(),
            layer=UNDERSTANDING,
            intent=ReviseMemoryIntent("庫存管理", (SituationReferenceChange(remove=("盤點",)),)),
        )
        assert isinstance(removed.preview, MemoryUpdatePreview)
        assert removed.preview.removed == ("盤點",)
        await edits.edit(writer, removed.command)
        assert not (
            await MemoryReadWorkflow(database.sessions).read_object(b2, UNDERSTANDING, "庫存管理")
        ).work_situation_references
        with pytest.raises(MemoryPermissionError):
            await prepare.prepare(
                b2,
                command_id=uuid4(),
                layer=SITUATION,
                intent=ReviseMemoryIntent("盤點", (MemoryBodyChange(PATCH),)),
            )
        with pytest.raises(MemoryPermissionError):
            await prepare.prepare(
                b2,
                command_id=uuid4(),
                layer=UNDERSTANDING,
                intent=ReviseMemoryIntent("庫存管理", (InterviewReferenceChange(add=(1,)),)),
            )

    execute(database_settings, scenario)


def tools_for(
    database: Database,
    writer: ExecutionWriter,
    binding: CandidateMemoryRead,
    *,
    capacity: int = 1_000_000,
) -> MemoryWriteTools:
    return MemoryWriteTools(
        MemoryWritePreparation(database.sessions),
        MemoryCandidateWorkflow(database.sessions),
        binding,
        writer,
        max_result_characters=capacity,
    )


def test_large_markdown_fuzzy_update_reports_actual_context_and_rejects_ambiguity(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        tools = tools_for(database, writer, binding)
        paragraph = "保留其餘完整工作細節與條件，不應被局部編輯改寫。"
        surrounding = "".join(f"## 記錄 {number}\n{paragraph * 5}\n" for number in range(1000))
        original_line = "庫存核對流程是先觀察完整倉庫資料再進行每個月的核對。"
        approximate_line = original_line.replace("資料", "信息")
        body = surrounding + "  # 月末工作\n" + original_line + "\n# 重複\n相同\n# 重複\n相同\n"
        assert len(body) > 100_000
        created = await tools.prepare(
            "create_work_situation",
            json.dumps(
                {
                    "title": "長文盤點",
                    "description": "完整細節",
                    "body": body,
                    "interview_references": [2],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(created, PreparedMemoryToolCall)
        await tools.execute(created)
        proposed = "@@\n # 月末工作\n-" + approximate_line + "\n+改為每週核對並回報。\n # 重複"
        updated = await tools.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "長文盤點",
                    "changes": [{"field": "body", "diff": proposed}],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(updated, PreparedMemoryToolCall)
        outcome = json.loads(await tools.execute(updated))
        observed = outcome["applied_changes"][0]["diff"]
        assert "-" + original_line in observed
        assert approximate_line not in observed
        current = await MemoryReadWorkflow(database.sessions).read_object(
            binding, SITUATION, "長文盤點"
        )
        assert current.content.body == body.replace(original_line, "改為每週核對並回報。")
        ambiguous = await tools.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "長文盤點",
                    "changes": [
                        {"field": "title", "value": "不該改名"},
                        {"field": "body", "diff": "@@\n # 重複\n-相同\n+不同"},
                        {"field": "interview_references", "remove": [2]},
                    ],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(ambiguous, str)
        rejected = json.loads(ambiguous)
        assert rejected["code"] == "ambiguous_patch_context"
        assert rejected["message"].count("候選行") == 2
        assert (
            await MemoryReadWorkflow(database.sessions).read_object(binding, SITUATION, "長文盤點")
            == current
        )

    execute(database_settings, scenario)


def test_model_create_update_delete_reports_real_effects_and_isolates_permission(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        tools = tools_for(database, writer, binding)
        assert tools.names == (
            "create_work_situation",
            "update_work_situation",
            "delete_work_situation",
        )
        assert all(item["strict"] is True for item in tools.definitions())
        create = await tools.prepare(
            "create_work_situation",
            json.dumps(
                {
                    "title": "盤點",
                    "description": "庫存核對",
                    "body": BODY,
                    "interview_references": [2],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(create, PreparedMemoryToolCall)
        assert await MemoryReadWorkflow(database.sessions).read_map(binding, SITUATION) == ()
        assert json.loads(await tools.execute(create)) == {"status": "created"}
        update = await tools.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "盤點",
                    "changes": [
                        {"field": "title", "value": "月末盤點"},
                        {"field": "body", "diff": PATCH},
                        {"field": "interview_references", "add": [1, 2]},
                    ],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(update, PreparedMemoryToolCall)
        result = json.loads(await tools.execute(update))
        assert result["title"] == "月末盤點"
        assert result["applied_changes"][-1] == {"field": "interview_references", "added": [1]}
        assert "-每月核對。" in result["applied_changes"][1]["diff"]
        assert "stage" not in result and "body" not in result
        unchanged = await tools.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "月末盤點",
                    "changes": [{"field": "interview_references", "add": [2]}],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(unchanged, PreparedMemoryToolCall)
        assert json.loads(await tools.execute(unchanged)) == {"status": "unchanged"}
        rejected = await tools.prepare("update_work_understanding", "{}", command_id=uuid4())
        assert isinstance(rejected, str) and json.loads(rejected)["code"] == "scope_not_allowed"
        deleted = await tools.prepare(
            "delete_work_situation", '{"target_title":"月末盤點"}', command_id=uuid4()
        )
        assert isinstance(deleted, PreparedMemoryToolCall)
        assert json.loads(await tools.execute(deleted)) == {"status": "deleted"}
        assert json.loads(await tools.execute(deleted)) == {"status": "deleted"}
        assert await MemoryReadWorkflow(database.sessions).read_map(binding, SITUATION) == ()

    execute(database_settings, scenario)


def test_tool_capacity_or_patch_failure_rejects_before_any_adoption(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        await create_situation(database, writer, binding)
        limited = tools_for(database, writer, binding, capacity=40)
        rejected = await limited.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "盤點",
                    "changes": [{"field": "body", "diff": PATCH}],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(rejected, str)
        assert json.loads(rejected)["code"] == "write_result_limit_exceeded"
        tools = tools_for(database, writer, binding)
        rejected = await tools.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "盤點",
                    "changes": [
                        {"field": "title", "value": "新名"},
                        {"field": "body", "diff": PATCH + "\n@@\n-不存在\n+新資料"},
                    ],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(rejected, str)
        assert json.loads(rejected)["code"] == "patch_context_not_found"
        assert "Hunk 2" in json.loads(rejected)["message"]
        unchanged = await MemoryReadWorkflow(database.sessions).read_object(
            binding, SITUATION, "盤點"
        )
        assert unchanged.content.body == BODY
        assert unchanged.interview_references == (2,)

    execute(database_settings, scenario)


def test_tool_replays_after_commit_ack_loss_without_repreparing_or_rechecking_output_capacity(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        await create_situation(database, writer, binding)
        tools = tools_for(database, writer, binding)
        prepared = await tools.prepare(
            "update_work_situation",
            json.dumps(
                {
                    "target_title": "盤點",
                    "changes": [
                        {"field": "title", "value": "月末盤點"},
                        {"field": "body", "diff": PATCH},
                    ],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(prepared, PreparedMemoryToolCall)
        edit = tools.candidates.edit

        async def acknowledgement_lost(
            writer: ExecutionWriter, command: MemoryEdit
        ) -> MemoryEditResult:
            await edit(writer, command)
            raise TimeoutError("synthetic acknowledgement lost after commit")

        monkeypatch.setattr(tools.candidates, "edit", acknowledgement_lost)
        with pytest.raises(TimeoutError):
            await tools.execute(prepared)
        await create_situation(database, writer, binding)
        # The saved prepared command/output is reused; today's lower cap cannot
        # turn an already committed operation into 'rejected, nothing changed'.
        resumed = tools_for(database, writer, binding, capacity=1)
        assert await resumed.execute(prepared) == prepared.success_output
        reads = MemoryReadWorkflow(database.sessions)
        assert (await reads.read_object(binding, SITUATION, "盤點")).content.body == BODY
        assert (
            await reads.read_object(binding, SITUATION, "月末盤點")
        ).content.body == BODY.replace("每月", "每週")

    execute(database_settings, scenario)


def test_understanding_tool_roundtrip_with_own_reference_branch_and_empty_sources(
    database_settings: DatabaseSettings, source: tuple[UUID, UUID]
) -> None:
    async def scenario(database: Database) -> None:
        writer, binding = await start(database, source)
        prepare = MemoryWritePreparation(database.sessions)
        case = await prepare.prepare(
            binding,
            command_id=uuid4(),
            layer=SITUATION,
            intent=CreateMemoryIntent(
                MemoryContent("盤點", "庫存", BODY), InterviewSourceSelection(())
            ),
        )
        candidates = MemoryCandidateWorkflow(database.sessions)
        result = await candidates.edit(writer, case.command)
        phase = await candidates.handoff(writer, result.position, uuid4())
        b2 = CandidateMemoryRead(writer.scope, phase)
        tools = tools_for(database, writer, b2)
        assert len(tools.definitions()) == 3
        created = await tools.prepare(
            "create_work_understanding",
            json.dumps(
                {
                    "title": "庫存管理",
                    "description": "管理責任",
                    "body": "已知理解。",
                    "work_situation_references": [],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(created, PreparedMemoryToolCall)
        await tools.execute(created)
        updated = await tools.prepare(
            "update_work_understanding",
            json.dumps(
                {
                    "target_title": "庫存管理",
                    "changes": [{"field": "work_situation_references", "add": ["盤點"]}],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(updated, PreparedMemoryToolCall)
        assert json.loads(await tools.execute(updated))["applied_changes"] == [
            {
                "field": "work_situation_references",
                "added": ["盤點"],
            }
        ]
        forbidden = await tools.prepare(
            "update_work_understanding",
            json.dumps(
                {
                    "target_title": "庫存管理",
                    "changes": [{"field": "interview_references", "add": [2]}],
                }
            ),
            command_id=uuid4(),
        )
        assert isinstance(forbidden, str) and json.loads(forbidden)["code"] == "invalid_arguments"

    execute(database_settings, scenario)
