"""Memory collection operations keep reads bounded and avoid unrelated immutable bodies."""

from contextlib import contextmanager
from time import perf_counter
from uuid import uuid4

import pytest
from sqlalchemy import event, select

from caliburn.features.interviews.persistence import InterviewTextRecord
from caliburn.features.work_memory import candidate_lifecycle
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revision_service import read_fixed_headers, write_object_revision
from caliburn.features.work_memory.revisions import MemoryRevisionReference
from caliburn.features.work_memory.stage_changes import build_situation_handoff_changes
from caliburn.workflows.memory_stage_changes import read_situation_handoff_snapshot
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.integration.test_memory_revisions import source_window as source_window
from tests.integration.test_memory_stage_changes import (
    SITUATION,
    UNDERSTANDING,
    execute,
    start,
)
from tests.integration.test_memory_stage_changes import (
    sources as sources,
)

pytestmark = pytest.mark.postgres


def test_interview_body_observer_matches_the_real_column():
    assert "interview_texts.interview_text" in str(select(InterviewTextRecord.interview_text))
    assert "interview_texts.interview_text" not in str(select(InterviewTextRecord.source_id))


@contextmanager
def measured_reads(database):
    """Observe executed driver statements and actual body rows, not mocked owner calls."""
    statements = []
    body_rows = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)
            if "memory_bodies.body" in statement:
                body_rows.append(cursor.rowcount)

    event.listen(database.engine.sync_engine, "after_cursor_execute", capture)
    started = perf_counter()
    try:
        yield statements, body_rows
    finally:
        event.remove(database.engine.sync_engine, "after_cursor_execute", capture)
        print(
            f"Memory reads: selects={len(statements)}, body_rows={body_rows}, "
            f"elapsed_ms={(perf_counter() - started) * 1000:.2f}"
        )


async def seed_snapshot(database, file_id, source_id, count):
    workflow, writer, position = await start(database, file_id, source_id)
    situations = []
    for index in range(count):
        created = await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                position,
                SITUATION,
                MemoryContent(f"情境 {index}", "固定標頭", f"固定情境正文 {index}"),
                frozenset({source_id}),
            ),
        )
        position = created.position
        situations.append(created.object_id)
    position = await workflow.handoff(writer, position, uuid4())
    # All understandings depend on the changed/deleted situation; source-only rewrites
    # must not reread each dependent's immutable body or validate its sources one by one.
    for index in range(count):
        created = await workflow.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                position,
                UNDERSTANDING,
                MemoryContent(f"理解 {index}", "固定標頭", f"固定理解正文 {index}"),
                frozenset(situations[:20]),
            ),
        )
        position = created.position
    await publish_memory_owner_fixture(workflow.sessions, writer, position, uuid4())
    return situations


@pytest.mark.parametrize("count", [1, 20, 200])
@pytest.mark.parametrize("changed", [False, True])
def test_handoff_reads_only_changed_situation_bodies(database_settings, sources, count, changed):
    file_id, first, second = sources

    async def scenario(database):
        situations = await seed_snapshot(database, file_id, first, count)
        workflow, writer, position = await start(database, file_id, second)
        if changed:
            result = await workflow.edit(
                writer,
                ReviseMemoryObject(
                    uuid4(),
                    position,
                    SITUATION,
                    situations[0],
                    MemoryContentChanges(body="修改後正文"),
                ),
            )
            position = result.position
        position = await workflow.handoff(writer, position, uuid4())
        async with database.sessions() as session:
            with measured_reads(database) as (statements, body_rows):
                snapshot = await read_situation_handoff_snapshot(session, position)
        result = build_situation_handoff_changes(snapshot)
        assert len(result) == int(changed)
        assert statements, "The observer must see the actual operation"
        assert body_rows == ([2] if changed else [])
        # Stage/membership (5), headers (3), changed revisions (4), formal sources (1).
        assert len(statements) <= 13

    execute(database_settings, scenario)


@pytest.mark.parametrize("count", [1, 20, 200])
@pytest.mark.parametrize("changed", [False, True])
def test_publication_rebinds_sources_without_loading_bodies(
    database_settings, sources, count, changed
):
    file_id, first, second = sources

    async def scenario(database):
        situations = await seed_snapshot(database, file_id, first, count)
        workflow, writer, position = await start(database, file_id, second)
        if changed:
            result = await workflow.edit(
                writer,
                ReviseMemoryObject(
                    uuid4(),
                    position,
                    SITUATION,
                    situations[0],
                    MemoryContentChanges(body="修改後正文"),
                ),
            )
            position = result.position
        position = await workflow.handoff(writer, position, uuid4())
        async with database.sessions.begin() as session:
            with measured_reads(database) as (statements, body_rows):
                published = await candidate_lifecycle.publish(session, position, uuid4())
        assert published.covered_through_sequence == 4
        assert body_rows == []
        assert 0 < len(statements) <= 16

    execute(database_settings, scenario)


@pytest.mark.parametrize("count", [1, 20, 200])
def test_deletion_updates_bindings_without_loading_dependent_bodies(
    database_settings, sources, count
):
    file_id, first, second = sources

    async def scenario(database):
        situations = await seed_snapshot(database, file_id, first, count)
        workflow, writer, position = await start(database, file_id, second)
        with measured_reads(database) as (statements, body_rows):
            await workflow.edit(
                writer, DeleteMemoryObject(uuid4(), position, SITUATION, situations[0])
            )
        # The edited target is the only complete revision needed by command processing.
        assert body_rows == [1]
        # The remaining-source validation adds four bounded reads when sources remain.
        assert 0 < len(statements) <= 21

    execute(database_settings, scenario)


@pytest.mark.parametrize("count", [1, 20, 200])
def test_understanding_source_validation_reads_a_set_without_source_bodies(
    database_settings, sources, count
):
    file_id, first, _second = sources

    async def scenario(database):
        workflow, writer, position = await start(database, file_id, first)
        selected = []
        for index in range(count):
            result = await workflow.edit(
                writer,
                CreateMemoryObject(
                    uuid4(),
                    position,
                    SITUATION,
                    MemoryContent(f"情境 {index}", "描述", "正文"),
                    frozenset({first}),
                ),
            )
            selected.append(result.object_id)
            position = result.position
        position = await workflow.handoff(writer, position, uuid4())
        with measured_reads(database) as (statements, body_rows):
            await workflow.edit(
                writer,
                CreateMemoryObject(
                    uuid4(),
                    position,
                    UNDERSTANDING,
                    MemoryContent("理解", "描述", "正文"),
                    frozenset(selected),
                ),
            )
        assert body_rows == []
        assert all("interview_texts.interview_text" not in sql for sql in statements)
        assert 0 < len(statements) <= 12

    execute(database_settings, scenario)


def test_fixed_header_sql_plan_selects_only_requested_revisions(database_settings, source_window):
    async def scenario(database):
        async with database.sessions.begin() as session:
            selected = []
            for index in range(50):
                revision = await write_object_revision(
                    session,
                    source_window,
                    layer=SITUATION,
                    content=MemoryContent(f"情境 {index}", "描述", "正文"),
                    interview_references=frozenset({source_window.through_source_id}),
                )
                if index < 2:
                    selected.append(
                        MemoryRevisionReference(revision.object_id, revision.revision_id)
                    )
            statements = []

            def capture(connection, cursor, statement, parameters, context, executemany):
                statements.append((statement, parameters))

            event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
            try:
                result = await read_fixed_headers(
                    session, job_file_id=source_window.job_file_id, references=frozenset(selected)
                )
            finally:
                event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
            assert set(result) == set(selected)
            assert len(statements) == 3
            connection = await session.connection()
            for statement, parameters in statements:
                plan = (
                    await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + statement, parameters
                    )
                ).scalar_one()[0]
                assert "memory_bodies" not in statement
                assert plan["Plan"]["Actual Rows"] in (0, 2)
                print(f"Header SQL: {statement}")
                print(f"Header plan: {plan}")

    execute(database_settings, scenario)


def test_source_only_rebindings_flush_as_one_owner_batch(database_settings, sources):
    file_id, first, second = sources

    async def scenario(database):
        situations = await seed_snapshot(database, file_id, first, 20)
        workflow, writer, position = await start(database, file_id, second)
        result = await workflow.edit(
            writer,
            ReviseMemoryObject(
                uuid4(), position, SITUATION, situations[0], MemoryContentChanges(body="修改後正文")
            ),
        )
        position = await workflow.handoff(writer, result.position, uuid4())
        writes = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
                writes.append(statement)

        async with database.sessions.begin() as session:
            event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
            try:
                await candidate_lifecycle.publish(session, position, uuid4())
            finally:
                event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
        print(f"Publication batched driver writes: {len(writes)}")
        # Real row work still grows; ORM executemany/bulk INSERT avoids one flush per revision.
        assert 0 < len(writes) <= 12

    execute(database_settings, scenario)
