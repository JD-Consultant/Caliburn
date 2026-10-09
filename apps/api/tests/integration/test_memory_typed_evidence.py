"""Typed consolidation evidence preserves source and command identity without JSON."""

from uuid import uuid4

import pytest
from sqlalchemy import event, insert, select, text
from sqlalchemy.exc import IntegrityError

from caliburn.features.executions.persistence import ExecutionRecord
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.persistence import (
    FormalInterviewRecord,
    InterviewInputRecord,
    InterviewReplyRecord,
    InterviewTextRecord,
)
from caliburn.features.work_memory import consolidation_requests as requests
from caliburn.features.work_memory.batch_persistence import MemoryOperationRecord
from caliburn.features.work_memory.candidates import MemoryCommandConflictError
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.integration.test_memory_batch_orchestration import complete_turn, execute, start_turn
from tests.integration.test_memory_evidence_isolation import replace_evidence

pytestmark = pytest.mark.postgres


def test_intent_is_typed_before_formal_completion(database_settings):
    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        command = uuid4()
        assert await flow.request(writer, command) == await flow.request(writer, command)
        async with database.sessions() as session:
            row = (
                await session.execute(
                    text(
                        "SELECT intent_source_id, request_payload, result_payload "
                        "FROM memory_operations "
                        "WHERE command_id=:command"
                    ),
                    {"command": command},
                )
            ).one()
        assert row.intent_source_id is not None
        assert row.request_payload is None
        assert row.result_payload is None
        assert (await flow.discover()).ready_file_ids == ()

    execute(database_settings, scenario)


@pytest.mark.parametrize("other_file", [False, True])
def test_intent_fk_requires_original_input_tuple(database_settings, other_file):
    async def scenario(database):
        first = await start_turn(database)
        await complete_turn(database, first)
        other = await start_turn(database, None if other_file else first.scope.job_file_id)
        async with database.sessions() as session:
            source = await interviews.read_execution_input_source_id(
                session, job_file_id=other.scope.job_file_id, execution_id=other.scope.execution_id
            )
        with pytest.raises(IntegrityError, match="intent_input"):
            async with database.sessions.begin() as session:
                await requests.record_intent(
                    session,
                    job_file_id=first.scope.job_file_id,
                    execution_id=first.scope.execution_id,
                    command_id=uuid4(),
                    source_id=source,
                )

    execute(database_settings, scenario)


@pytest.mark.parametrize(
    "values",
    [
        {"kind": "consolidation_intent"},
        {"kind": "batch_failure", "failure_reason": "missing"},
        {"kind": "batch_failure", "failure_reason": "", "failure_frontier": 0},
        {"kind": "batch_failure", "failure_reason": "x" * 101, "failure_frontier": 0},
        {"kind": "batch_failure", "failure_reason": "negative", "failure_frontier": -1},
        {
            "kind": "batch_failure",
            "failure_reason": "json",
            "failure_frontier": 0,
            "result_payload": {"formal_frontier": 0},
        },
        {"kind": "other", "failure_frontier": 0, "request_payload": {}, "result_payload": {}},
    ],
)
def test_database_rejects_incomplete_or_mixed_variants(database_settings, values):
    async def scenario(database):
        writer = await start_turn(database)
        with pytest.raises(IntegrityError, match="evidence_shape"):
            async with database.sessions.begin() as session:
                session.add(
                    MemoryOperationRecord(
                        job_file_id=writer.scope.job_file_id,
                        execution_id=writer.scope.execution_id,
                        command_id=uuid4(),
                        **values,
                    )
                )

    execute(database_settings, scenario)


def test_original_failure_frontier_and_command_namespace_survive_replay(database_settings):
    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        intent_command = uuid4()
        await flow.request(writer, intent_command)
        await complete_turn(database, writer)
        work = await flow.claim(writer.scope.job_file_id, writer_id=uuid4())
        assert work is not None
        await flow.fail(work.writer, reason="synthetic")
        for _ in range(2):
            await complete_turn(database, await start_turn(database, writer.scope.job_file_id))
        # Replaying after four new messages must not move the original failure frontier.
        await flow.fail(work.writer, reason="synthetic")
        assert await flow.failure_reason(writer.scope.job_file_id) == "synthetic"
        with pytest.raises(MemoryCommandConflictError):
            await flow.fail(work.writer, reason="different")
        await complete_turn(database, await start_turn(database, writer.scope.job_file_id))
        assert await flow.failure_reason(writer.scope.job_file_id) is None
        async with database.sessions.begin() as session:
            failure = (
                await session.execute(
                    select(
                        MemoryOperationRecord.failure_frontier,
                        MemoryOperationRecord.request_payload,
                        MemoryOperationRecord.result_payload,
                    ).where(MemoryOperationRecord.kind == "batch_failure")
                )
            ).one()
            assert tuple(failure) == (3, None, None)
            with pytest.raises(MemoryCommandConflictError):
                await requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=intent_command,
                    reason="synthetic",
                    frontier=9,
                )
            with pytest.raises(MemoryCommandConflictError):
                await requests.record_operation(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=intent_command,
                    kind="stage_completion",
                    payload={},
                    result={},
                )

    execute(database_settings, scenario)


async def publish_ready(database, flow, writer):
    work = await flow.claim(writer.scope.job_file_id, writer_id=uuid4())
    assert work is not None
    position = await MemoryCandidateWorkflow(database.sessions).handoff(
        work.writer, work.position, uuid4()
    )
    return await publish_memory_owner_fixture(database.sessions, work.writer, position, uuid4())


async def seed_completed_exchanges(database, file_id, count):
    """Bulk owner data for cost measurement; no model or completion-quality claim."""
    identities = [(uuid4(), uuid4(), uuid4()) for _ in range(count)]
    async with database.sessions.begin() as session:
        await session.execute(
            insert(ExecutionRecord),
            [
                dict(
                    job_file_id=file_id,
                    execution_id=execution,
                    kind="consultant_turn",
                    status="completed",
                )
                for execution, _, _ in identities
            ],
        )
        await session.execute(
            insert(InterviewTextRecord),
            [
                dict(
                    job_file_id=file_id,
                    source_id=source,
                    speaker=speaker,
                    interview_text="synthetic",
                )
                for _, source, reply in identities
                for source, speaker in [(source, "employee"), (reply, "consultant")]
            ],
        )
        await session.execute(
            insert(InterviewInputRecord),
            [
                dict(
                    job_file_id=file_id,
                    execution_id=execution,
                    source_id=source,
                    command_id=uuid4(),
                )
                for execution, source, _ in identities
            ],
        )
        await session.execute(
            insert(InterviewReplyRecord),
            [
                dict(job_file_id=file_id, execution_id=execution, source_id=reply)
                for execution, _, reply in identities
            ],
        )
        await session.execute(
            insert(FormalInterviewRecord),
            [
                dict(job_file_id=file_id, interview_sequence=sequence, source_id=source)
                for index, (_, source, reply) in enumerate(identities)
                for sequence, source in [(4 + index * 2, source), (5 + index * 2, reply)]
            ],
        )
        await session.execute(
            insert(MemoryOperationRecord),
            [
                dict(
                    job_file_id=file_id,
                    execution_id=execution,
                    command_id=uuid4(),
                    kind="consolidation_intent",
                    intent_source_id=source,
                )
                for execution, source, _ in identities
            ],
        )


def test_already_covered_corruption_is_still_reported(database_settings):
    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        command = uuid4()
        await flow.request(writer, command)
        await complete_turn(database, writer)
        await publish_ready(database, flow, writer)
        assert (await flow.discover()).ready_file_ids == ()
        await replace_evidence(database, command, {"intent_source_id": uuid4()})
        discovery = await flow.discover()
        assert discovery.ready_file_ids == ()
        assert [(issue.command_id, issue.reason) for issue in discovery.issues] == [
            (command, "formal_source_mismatch")
        ]

    execute(database_settings, scenario)


@pytest.mark.parametrize("history_count", [100, 10_000])
@pytest.mark.parametrize("pending_count", [0, 1])
def test_history_stays_in_sql_and_only_pending_rows_cross_to_python(
    database_settings, history_count, pending_count, record_property
):
    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        await flow.request(writer, uuid4())
        await complete_turn(database, writer)
        # Independent matched exchanges exercise growing source/execution history too.
        await seed_completed_exchanges(database, writer.scope.job_file_id, history_count - 1)
        snapshot = await publish_ready(database, flow, writer)
        assert snapshot.covered_through_sequence == history_count * 2
        for index in range(3):
            later = await start_turn(database, writer.scope.job_file_id)
            if pending_count and index == 2:
                await flow.request(later, uuid4())
            await complete_turn(database, later)
        async with database.sessions.begin() as session:
            await session.execute(
                insert(MemoryOperationRecord),
                [
                    dict(
                        job_file_id=writer.scope.job_file_id,
                        execution_id=writer.scope.execution_id,
                        command_id=uuid4(),
                        kind="batch_failure",
                        failure_reason="expired",
                        failure_frontier=history_count * 2 + 1,
                    )
                    for _ in range(history_count)
                ],
            )
            for table in (
                "memory_operations",
                "executions",
                "interview_inputs",
                "interview_replies",
                "formal_interviews",
                "interview_texts",
            ):
                await session.execute(text(f"ANALYZE {table}"))
        captured = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            if statement.lstrip().startswith(("SELECT", "WITH")):
                captured.append((statement, parameters, cursor.rowcount))

        event.listen(database.engine.sync_engine, "after_cursor_execute", capture)
        try:
            result = await flow.discover()
        finally:
            event.remove(database.engine.sync_engine, "after_cursor_execute", capture)
        assert len(result.ready_files) == pending_count
        assert not result.issues
        assert sum(count for _, _, count in captured) == pending_count
        assert all(
            "request_payload" not in sql
            and "result_payload" not in sql
            and "interview_text " not in sql
            for sql, _, _ in captured
        )
        plans = []
        async with database.engine.connect() as connection:
            for sql, parameters, returned in captured:
                plan = (
                    await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql,
                        parameters,
                    )
                ).scalar_one()[0]
                plans.append(dict(returned=returned, plan=plan))
        # JUnit properties preserve the complete measured plans/buffers for this run.
        import json

        record_property("history_count", history_count)
        record_property("pending_count", pending_count)
        record_property("query_plans", json.dumps(plans))

    execute(database_settings, scenario)
