"""Direct JD evidence keeps fixed IDs, scope and order in caller-owned transactions."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.exc import IntegrityError

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.persistence import JdOperationRecord, JdRevisionRecord
from caliburn.features.job_description.source_persistence import (
    insert_source_references,
    read_source_references,
)
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)
from caliburn.features.work_memory.candidates import CreateMemoryObject
from caliburn.features.work_memory.models import MemoryContent, MemorySourceWindow
from caliburn.features.work_memory.revision_service import write_object_revision
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionReference
from caliburn.settings import DatabaseSettings
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow

pytestmark = pytest.mark.postgres


def execute[T](settings: DatabaseSettings, operation: Callable[[Database], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            return await operation(database)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


@dataclass(frozen=True)
class SourceFile:
    file_id: UUID
    initial_revision_id: UUID
    formal_source_id: UUID
    pending_source_id: UUID


def seed_file(connection: psycopg.Connection) -> SourceFile:
    file = SourceFile(uuid4(), uuid4(), uuid4(), uuid4())
    connection.execute(
        "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,%s,'來源保存','來源保存','合成人')",
        (file.file_id, uuid4()),
    )
    connection.execute(
        "INSERT INTO jd_revisions (job_file_id,revision_id) VALUES (%s,%s)",
        (file.file_id, file.initial_revision_id),
    )
    connection.execute(
        "INSERT INTO job_descriptions (job_file_id,initial_revision_id,current_revision_id) "
        "VALUES (%s,%s,%s)",
        (file.file_id, file.initial_revision_id, file.initial_revision_id),
    )
    for sequence, speaker, source_id in (
        (1, "app", uuid4()),
        (2, "employee", file.formal_source_id),
        (None, "employee", file.pending_source_id),
    ):
        connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,'合成訪談原文')",
            (file.file_id, source_id, speaker),
        )
        if sequence is not None:
            connection.execute(
                "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
                "VALUES (%s,%s,%s)",
                (file.file_id, sequence, source_id),
            )
    return file


@pytest.fixture
def source_file(database_connection: psycopg.Connection) -> SourceFile:
    return seed_file(database_connection)


async def publish_sources(database: Database, file: SourceFile) -> tuple[MemorySource, ...]:
    scope = ExecutionScope(file.file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
    async with database.sessions.begin() as session:
        await executions.admit_execution(session, scope)
        writer = await executions.claim_writer(session, scope, writer_id=uuid4())
    workflow = MemoryCandidateWorkflow(database.sessions)
    position = await workflow.start(writer, file.formal_source_id)
    assert position is not None
    situation = await workflow.edit(
        writer,
        CreateMemoryObject(
            uuid4(), position, MemoryLayer.WORK_SITUATION, MemoryContent("同名", "情境", "原文")
        ),
    )
    position = await workflow.handoff(writer, situation.position, uuid4())
    understanding = await workflow.edit(
        writer,
        CreateMemoryObject(
            uuid4(), position, MemoryLayer.WORK_UNDERSTANDING, MemoryContent("同名", "理解", "正文")
        ),
    )
    snapshot = await workflow.publish(writer, understanding.position, uuid4())
    sources = []
    for layer, object_id in (
        (MemorySourceLayer.WORK_SITUATION, situation.object_id),
        (MemorySourceLayer.WORK_UNDERSTANDING, understanding.object_id),
    ):
        revision = await workflow.read_snapshot_object(
            file.file_id, snapshot.snapshot_id, object_id
        )
        sources.append(MemorySource(layer, snapshot.snapshot_id, object_id, revision.revision_id))
    return tuple(sources)


def test_roundtrip_keeps_order_precise_targets_pending_input_and_fixed_memory_ids(
    database_settings: DatabaseSettings, source_file: SourceFile
) -> None:
    async def scenario(database: Database) -> None:
        situation, understanding = await publish_sources(database, source_file)
        references = (
            JdSourceReference(
                uuid4(),
                JdSourceTarget(SourceTargetKind.TASK_CAPABILITY, item_id=uuid4(), task_id=uuid4()),
                understanding,
            ),
            JdSourceReference(
                uuid4(),
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
                InterviewSource(source_file.pending_source_id),
                needs_review=True,
            ),
            JdSourceReference(
                uuid4(),
                JdSourceTarget(SourceTargetKind.DETAIL, item_id=uuid4(), task_id=uuid4()),
                situation,
            ),
            JdSourceReference(
                uuid4(),
                JdSourceTarget(SourceTargetKind.TASK, item_id=uuid4()),
                InterviewSource(source_file.formal_source_id),
            ),
        )
        revision_id, next_revision_id = uuid4(), uuid4()
        stored = tuple(
            replace(reference, reviewed_revision_id=revision_id) for reference in references
        )
        async with database.sessions.begin() as session:
            session.add(JdRevisionRecord(job_file_id=source_file.file_id, revision_id=revision_id))
            await session.flush()
            await insert_source_references(session, source_file.file_id, revision_id, references)
        async with database.sessions.begin() as session:
            assert await read_source_references(session, source_file.file_id, revision_id) == stored
            assert await read_source_references(session, uuid4(), revision_id) == ()
            assert await read_source_references(session, source_file.file_id, uuid4()) == ()
            session.add(
                JdRevisionRecord(
                    job_file_id=source_file.file_id,
                    revision_id=next_revision_id,
                    parent_revision_id=revision_id,
                )
            )
            await session.flush()
            carried = tuple(replace(reference, needs_review=True) for reference in stored)
            await insert_source_references(session, source_file.file_id, next_revision_id, carried)
        async with database.sessions.begin() as session:
            assert await read_source_references(session, source_file.file_id, revision_id) == stored
            assert (
                await read_source_references(session, source_file.file_id, next_revision_id)
                == carried
            )

    execute(database_settings, scenario)


def test_foreign_file_cannot_supply_jd_review_baseline_interview_or_memory_ids(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_file: SourceFile,
) -> None:
    foreign = seed_file(database_connection)

    async def scenario(database: Database) -> None:
        local_memory, _ = await publish_sources(database, source_file)
        foreign_memory, _ = await publish_sources(database, foreign)
        target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE)
        local_reference = JdSourceReference(
            uuid4(), target, InterviewSource(source_file.pending_source_id)
        )
        revision_id = uuid4()
        async with database.sessions.begin() as session:
            session.add(JdRevisionRecord(job_file_id=source_file.file_id, revision_id=revision_id))
            await session.flush()
            for selected_revision, reference, constraint in (
                (
                    foreign.initial_revision_id,
                    replace(local_reference, reviewed_revision_id=source_file.initial_revision_id),
                    "fk_jd_source_references_revision",
                ),
                (
                    revision_id,
                    replace(local_reference, reviewed_revision_id=foreign.initial_revision_id),
                    "fk_jd_source_references_reviewed_revision",
                ),
                (
                    revision_id,
                    replace(local_reference, source=InterviewSource(foreign.pending_source_id)),
                    "fk_jd_source_references_interview",
                ),
                (
                    revision_id,
                    replace(
                        local_reference,
                        source=replace(local_memory, snapshot_id=foreign_memory.snapshot_id),
                    ),
                    "fk_jd_source_references_memory_snapshot",
                ),
                (
                    revision_id,
                    replace(
                        local_reference,
                        source=replace(foreign_memory, snapshot_id=local_memory.snapshot_id),
                    ),
                    "fk_jd_source_references_memory_revision",
                ),
            ):
                with pytest.raises(IntegrityError, match=constraint) as caught:
                    async with session.begin_nested():
                        await insert_source_references(
                            session, source_file.file_id, selected_revision, (reference,)
                        )
                assert caught.value.orig.sqlstate == "23503"
            assert await read_source_references(session, source_file.file_id, revision_id) == ()

    execute(database_settings, scenario)


def test_duplicate_identity_cannot_be_readded_as_a_different_memory_revision(
    database_settings: DatabaseSettings, source_file: SourceFile
) -> None:
    async def scenario(database: Database) -> None:
        memory, _ = await publish_sources(database, source_file)
        revision_id = uuid4()
        target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE)
        interview = JdSourceReference(
            uuid4(), target, InterviewSource(source_file.pending_source_id)
        )
        original = JdSourceReference(uuid4(), target, memory)
        async with database.sessions.begin() as session:
            newer = await write_object_revision(
                session,
                MemorySourceWindow(source_file.file_id, source_file.formal_source_id, 0, 2),
                layer=MemoryLayer.WORK_SITUATION,
                previous=MemoryRevisionReference(memory.object_id, memory.revision_id),
                content=MemoryContent("同名", "修訂描述", "修訂正文"),
            )
            session.add(JdRevisionRecord(job_file_id=source_file.file_id, revision_id=revision_id))
            await session.flush()
            # Membership in the pinned snapshot is a workflow concern. Storage must
            # still reject the duplicate identity even when the fixed revision differs.
            duplicate = replace(
                original,
                citation_id=uuid4(),
                source=replace(memory, revision_id=newer.revision_id),
            )
            for references in (
                (interview, replace(interview, citation_id=uuid4())),
                (original, duplicate),
            ):
                with pytest.raises(IntegrityError, match="uq_jd_source_references_identity"):
                    async with session.begin_nested():
                        await insert_source_references(
                            session, source_file.file_id, revision_id, references
                        )
            # The same source may support two distinct targets; neither is deduplicated.
            distinct = replace(
                interview,
                citation_id=uuid4(),
                target=JdSourceTarget(SourceTargetKind.TASK, item_id=uuid4()),
            )
            await insert_source_references(
                session, source_file.file_id, revision_id, (interview, distinct)
            )
            with pytest.raises(IntegrityError, match="uq_jd_source_references_position"):
                async with session.begin_nested():
                    await insert_source_references(
                        session, source_file.file_id, revision_id, (original,)
                    )
            saved = await read_source_references(session, source_file.file_id, revision_id)
            assert tuple(reference.citation_id for reference in saved) == (
                interview.citation_id,
                distinct.citation_id,
            )

    execute(database_settings, scenario)


def test_fixed_reference_rejects_mutation_and_late_append_after_operation_adoption(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source_file: SourceFile,
) -> None:
    revision_id = uuid4()
    reference = JdSourceReference(
        uuid4(),
        JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
        InterviewSource(source_file.pending_source_id),
    )

    async def save(database: Database) -> None:
        async with database.sessions.begin() as session:
            session.add(JdRevisionRecord(job_file_id=source_file.file_id, revision_id=revision_id))
            await session.flush()
            await insert_source_references(session, source_file.file_id, revision_id, (reference,))
            session.add(
                JdOperationRecord(
                    job_file_id=source_file.file_id,
                    command_id=uuid4(),
                    kind="edit_sources",
                    expected_revision_id=source_file.initial_revision_id,
                    result_revision_id=revision_id,
                    request_payload={},
                )
            )

    execute(database_settings, save)
    for statement in (
        "UPDATE jd_source_references SET needs_review=true",
        "DELETE FROM jd_source_references",
    ):
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
            database_connection.execute(statement)
    for adopted_revision in (revision_id, source_file.initial_revision_id):
        with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append"):
            database_connection.execute(
                "INSERT INTO jd_source_references "
                "(job_file_id,revision_id,citation_id,target_kind,target_field,source_kind,"
                "interview_source_id,needs_review,reviewed_revision_id,position) "
                "VALUES (%s,%s,%s,'profile_field','job_title','interview',%s,false,%s,1)",
                (
                    source_file.file_id,
                    adopted_revision,
                    uuid4(),
                    source_file.pending_source_id,
                    adopted_revision,
                ),
            )

    async def check(database: Database) -> None:
        async with database.sessions.begin() as session:
            assert await read_source_references(session, source_file.file_id, revision_id) == (
                replace(reference, reviewed_revision_id=revision_id),
            )

    execute(database_settings, check)


def test_caller_rollback_removes_both_revision_and_references(
    database_settings: DatabaseSettings, source_file: SourceFile
) -> None:
    async def scenario(database: Database) -> None:
        revision_id = uuid4()
        reference = JdSourceReference(
            uuid4(),
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
            InterviewSource(source_file.pending_source_id),
        )
        with pytest.raises(RuntimeError, match="before commit"):
            async with database.sessions.begin() as session:
                session.add(
                    JdRevisionRecord(job_file_id=source_file.file_id, revision_id=revision_id)
                )
                await session.flush()
                await insert_source_references(
                    session, source_file.file_id, revision_id, (reference,)
                )
                assert await read_source_references(session, source_file.file_id, revision_id)
                raise RuntimeError("interrupted before commit")
        async with database.sessions.begin() as session:
            assert await session.get(JdRevisionRecord, (source_file.file_id, revision_id)) is None
            assert await read_source_references(session, source_file.file_id, revision_id) == ()
            await insert_source_references(session, source_file.file_id, revision_id, ())
            assert await read_source_references(session, source_file.file_id, revision_id) == ()

    execute(database_settings, scenario)


def test_database_rejects_missing_or_mixed_source_and_target_shapes(
    database_connection: psycopg.Connection, source_file: SourceFile
) -> None:
    revision_id = uuid4()
    database_connection.execute(
        "INSERT INTO jd_revisions (job_file_id,revision_id) VALUES (%s,%s)",
        (source_file.file_id, revision_id),
    )
    row = {
        "job_file_id": source_file.file_id,
        "revision_id": revision_id,
        "citation_id": uuid4(),
        "target_kind": "profile_field",
        "target_field": "purpose",
        "source_kind": "interview",
        "interview_source_id": source_file.pending_source_id,
        "needs_review": False,
        "reviewed_revision_id": revision_id,
        "position": 0,
    }
    for changes, constraint in (
        ({"target_field": None}, "target_shape"),
        ({"target_kind": "task", "target_item_id": uuid4()}, "target_shape"),
        ({"source_kind": "memory", "interview_source_id": None}, "source_shape"),
        ({"memory_snapshot_id": uuid4()}, "source_shape"),
        ({"position": -1}, "position"),
    ):
        values = row | changes
        with pytest.raises(psycopg.errors.CheckViolation, match=constraint):
            database_connection.execute(
                psycopg.sql.SQL("INSERT INTO jd_source_references ({}) VALUES ({})").format(
                    psycopg.sql.SQL(",").join(map(psycopg.sql.Identifier, values)),
                    psycopg.sql.SQL(",").join(psycopg.sql.Placeholder() for _ in values),
                ),
                tuple(values.values()),
            )
    assert database_connection.execute("SELECT count(*) FROM jd_source_references").fetchone() == (
        0,
    )
