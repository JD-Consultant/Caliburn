"""Real PostgreSQL regressions for history-independent background/formal reads."""

import re
from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.dialects import postgresql

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews.models import InterviewReadScope
from caliburn.features.interviews.persistence import InterviewTextRecord
from caliburn.features.occupation_references import service as references
from caliburn.features.occupation_references.models import OccupationReferenceState
from caliburn.features.work_memory import consolidation_requests
from caliburn.features.work_memory.consolidation_models import MemoryEvidenceError
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_consolidation_queries import read_blocks, read_failure_reason
from caliburn.workflows.occupation_reference_reads import read_formal_reference_state
from tests.integration.test_memory_batch_orchestration import complete_turn, execute, start_turn
from tests.integration.test_memory_evidence_isolation import add_damaged_intent

pytestmark = pytest.mark.postgres


async def count_queries(database, action):
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
    try:
        result = await action()
    finally:
        event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
    return result, len(statements)


# Word-bounded so the table name interview_texts (and its aliases) is not mistaken for the column.
SELECTS_INTERVIEW_BODY = re.compile(r"\binterview_text\b")


def test_body_pattern_tells_the_body_column_from_the_text_table():
    """Control for the discovery assertion below: the pattern must be able to fail."""
    dialect = postgresql.dialect()
    body = str(select(InterviewTextRecord.interview_text).compile(dialect=dialect))
    metadata = str(select(InterviewTextRecord.source_id).compile(dialect=dialect))
    assert SELECTS_INTERVIEW_BODY.search(body)
    assert "interview_texts" in metadata
    assert not SELECTS_INTERVIEW_BODY.search(metadata)


def test_discovery_query_count_does_not_grow_with_intents_or_files(database_settings):
    async def scenario(database):
        flow = MemoryConsolidationWorkflow(database.sessions)
        first = await start_turn(database)
        await flow.request(first, uuid4())
        await complete_turn(database, first)
        ready, initial = await count_queries(database, flow.discover)
        assert ready.ready_file_ids == (first.scope.job_file_id,)
        assert initial > 0  # the counter is attached to the engine discovery really uses
        expected = {first.scope.job_file_id}
        for index in range(12):
            writer = await start_turn(database, first.scope.job_file_id if index < 8 else None)
            await flow.request(writer, uuid4())
            await complete_turn(database, writer)
            expected.add(writer.scope.job_file_id)
        ready, expanded = await count_queries(database, flow.discover)
        assert set(ready.ready_file_ids) == expected
        assert expanded == initial

    execute(database_settings, scenario)


def test_failure_read_pins_one_frontier_for_all_historical_failures(database_settings):
    async def scenario(database):
        writer = await start_turn(database)
        await complete_turn(database, writer)
        for _ in range(3):
            await complete_turn(database, await start_turn(database, writer.scope.job_file_id))

        async def add_failure():
            async with database.sessions.begin() as session:
                await consolidation_requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=uuid4(),
                    reason="synthetic",
                    frontier=0,
                )

        async def read():
            async with database.sessions() as session:
                return await read_failure_reason(session, writer.scope.job_file_id)

        await add_failure()
        value, initial = await count_queries(database, read)
        assert value is None
        for _ in range(10):
            await add_failure()
        value, expanded = await count_queries(database, read)
        assert value is None
        assert expanded == initial

    execute(database_settings, scenario)


def test_formal_reference_reads_only_final_state_and_history_independent_queries(database_settings):
    async def scenario(database):
        first = await start_turn(database)
        async with database.sessions.begin() as session:
            await references.start_candidate(
                session,
                first.scope.job_file_id,
                first.scope.execution_id,
                OccupationReferenceState(("first",), ("old",)),
            )
        await complete_turn(database, first)

        async def read(scope):
            async with database.sessions() as session:
                return await read_formal_reference_state(session, scope)

        scope = InterviewReadScope(first.scope.job_file_id, 2)
        state, initial = await count_queries(database, lambda: read(scope))
        assert state == OccupationReferenceState(("first",), ("old",))
        for index in range(8):
            writer = await start_turn(database, first.scope.job_file_id)
            async with database.sessions.begin() as session:
                await references.start_candidate(
                    session,
                    writer.scope.job_file_id,
                    writer.scope.execution_id,
                    OccupationReferenceState((str(index),), ("later",))
                    if index < 7
                    else OccupationReferenceState((), ()),
                )
            await complete_turn(database, writer)
        state, expanded = await count_queries(
            database, lambda: read(InterviewReadScope(scope.job_file_id, 18))
        )
        assert state == OccupationReferenceState((), ())
        assert expanded == initial
        assert await read(scope) == OccupationReferenceState(("first",), ("old",))

    execute(database_settings, scenario)


@pytest.mark.parametrize("formal", [False, True])
def test_completed_intent_with_missing_or_mismatched_source_is_not_hidden(
    database_settings, formal
):
    from caliburn.features.executions import service as executions
    from caliburn.features.executions.models import ExecutionStatus

    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        await add_damaged_intent(database, writer)
        if formal:
            await complete_turn(database, writer)
        else:
            async with database.sessions.begin() as session:
                await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        discovery = await flow.discover()
        assert discovery.ready_file_ids == ()
        assert len(discovery.issues) == 1
        assert discovery.issues[0].job_file_id == writer.scope.job_file_id
        assert discovery.issues[0].reason == "formal_source_mismatch"
        with pytest.raises(MemoryEvidenceError, match="formal_source_mismatch"):
            await flow.claim(writer.scope.job_file_id, writer_id=uuid4())

    execute(database_settings, scenario)


def test_claim_rechecks_failure_added_after_discovery(database_settings):
    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        await flow.request(writer, uuid4())
        await complete_turn(database, writer)
        assert (await flow.discover()).ready_file_ids == (writer.scope.job_file_id,)
        async with database.sessions.begin() as session:
            await consolidation_requests.record_failure(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=uuid4(),
                reason="new_failure",
                frontier=3,
            )
        assert await flow.claim(writer.scope.job_file_id, writer_id=uuid4()) is None

    execute(database_settings, scenario)


@pytest.mark.parametrize("frontier", [None, True, "3", [], {}])
def test_malformed_failure_frontier_is_rejected(database_settings, frontier):
    async def scenario(database):
        writer = await start_turn(database)
        with pytest.raises(ValueError, match="nonnegative"):
            async with database.sessions.begin() as session:
                await consolidation_requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=uuid4(),
                    reason="synthetic",
                    frontier=frontier,
                )

    execute(database_settings, scenario)


def test_obsolete_reference_json_does_not_load_and_latest_invalid_state_is_rejected(
    database_settings,
):
    from caliburn.features.occupation_references import persistence
    from caliburn.features.occupation_references.models import ReferenceStateError

    async def scenario(database):
        first = await start_turn(database)
        generation_id, revision_id = uuid4(), uuid4()
        async with database.sessions.begin() as session:
            session.add(
                persistence.ReferenceOperationRecord(
                    job_file_id=first.scope.job_file_id,
                    execution_id=first.scope.execution_id,
                    operation_id=uuid4(),
                    kind="start",
                    generation_id=generation_id,
                    result_generation_id=generation_id,
                    expected_revision_id=None,
                    parent_revision_id=None,
                    revision_id=revision_id,
                    state={"selected_reference_ids": [99], "excluded_work": []},
                )
            )
            await session.flush()
            session.add(
                persistence.ReferenceCandidateRecord(
                    job_file_id=first.scope.job_file_id,
                    execution_id=first.scope.execution_id,
                    generation_id=generation_id,
                    base_revision_id=revision_id,
                    current_revision_id=revision_id,
                )
            )
        await complete_turn(database, first)
        second = await start_turn(database, first.scope.job_file_id)
        async with database.sessions.begin() as session:
            await references.start_candidate(
                session,
                second.scope.job_file_id,
                second.scope.execution_id,
                OccupationReferenceState((), ()),
            )
        await complete_turn(database, second)
        async with database.sessions() as session:
            assert await read_formal_reference_state(
                session,
                InterviewReadScope(first.scope.job_file_id, 4),
            ) == OccupationReferenceState((), ())
            with pytest.raises(ReferenceStateError, match="selection"):
                await read_formal_reference_state(
                    session,
                    InterviewReadScope(first.scope.job_file_id, 2),
                )

    execute(database_settings, scenario)


@pytest.mark.parametrize("active_memory", [False, True])
def test_discovery_does_not_validate_intents_for_blocked_or_active_files(
    database_settings, active_memory
):
    async def scenario(database):
        writer = await start_turn(database)
        flow = MemoryConsolidationWorkflow(database.sessions)
        command_id = uuid4()
        await flow.request(writer, command_id)
        await complete_turn(database, writer)
        if active_memory:
            assert await flow.claim(writer.scope.job_file_id, writer_id=uuid4()) is not None
        from tests.integration.test_memory_evidence_isolation import replace_evidence

        await replace_evidence(database, command_id, {"intent_source_id": uuid4()})
        async with database.sessions.begin() as session:
            if not active_memory:
                await consolidation_requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=uuid4(),
                    reason="blocked",
                    frontier=3,
                )
        assert (await flow.discover()).ready_file_ids == (
            (writer.scope.job_file_id,) if active_memory else ()
        )

    execute(database_settings, scenario)


def test_discovery_reads_interview_positions_never_interview_bodies(database_settings):
    async def scenario(database):
        flow = MemoryConsolidationWorkflow(database.sessions)
        for _ in range(3):
            writer = await start_turn(database)
            await flow.request(writer, uuid4())
            await complete_turn(database, writer)
        statements = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
        try:
            assert len((await flow.discover()).ready_file_ids) == 3
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
        assert statements
        # Joining the text table for metadata is fine; selecting its body column is not.
        assert not [sql for sql in statements if SELECTS_INTERVIEW_BODY.search(sql)]

    execute(database_settings, scenario)


def plan_nodes(node):
    yield node
    for child in node.get("Plans", ()):
        yield from plan_nodes(child)


@pytest.mark.parametrize("failure_count", [0, 1, 12])
def test_one_files_failure_read_evaluates_its_frontier_at_most_once(
    database_settings, failure_count
):
    async def scenario(database):
        writer = await start_turn(database)
        await complete_turn(database, writer)
        async with database.sessions.begin() as session:
            for _ in range(failure_count):
                await consolidation_requests.record_failure(
                    session,
                    job_file_id=writer.scope.job_file_id,
                    execution_id=writer.scope.execution_id,
                    command_id=uuid4(),
                    reason="synthetic",
                    frontier=1,
                )
        statements = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append((statement, parameters))

        event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with database.sessions() as session:
                reason = await read_failure_reason(session, writer.scope.job_file_id)
                assert reason == ("synthetic" if failure_count else None)
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
        reads = []
        async with database.engine.connect() as connection:
            for statement, parameters in statements:
                if "formal_interviews" in statement:
                    result = await connection.exec_driver_sql(
                        "EXPLAIN (ANALYZE, VERBOSE, FORMAT JSON) " + statement, parameters
                    )
                    reads.extend(
                        node
                        for node in plan_nodes(result.scalar_one()[0]["Plan"])
                        if node.get("Relation Name") == "formal_interviews"
                    )
        assert sum(node["Actual Loops"] for node in reads) == (1 if failure_count else 0)

    execute(database_settings, scenario)


def has_job_file_index_bound(node, formal_alias):
    if node["Node Type"] in {"Index Scan", "Index Only Scan", "Bitmap Index Scan"}:
        # VERBOSE labels every column with its relation alias. Accept only this frontier
        # query's direct equality, optionally combined with max()'s sequence null guard.
        # Full matching excludes nested expressions and comparisons on another relation.
        # A new expression shape needs a reviewed control; this is not a SQL parser.
        alias = re.escape(formal_alias)
        value = r"(?:[a-z_][a-z_0-9]*\.job_file_id|'[0-9a-f-]{36}'::uuid)"
        equality = rf"\({alias}\.job_file_id = {value}\)"
        nonnull = rf"\({alias}\.interview_sequence IS NOT NULL\)"
        accepted = rf"(?:{equality}|\({equality} AND {nonnull}\)|\({nonnull} AND {equality}\))"
        return re.fullmatch(accepted, node.get("Index Cond", "")) is not None
    children = node.get("Plans", ())
    if node["Node Type"] in {"Bitmap Heap Scan", "BitmapOr"}:
        return bool(children) and all(
            has_job_file_index_bound(child, formal_alias) for child in children
        )
    if node["Node Type"] == "BitmapAnd":
        return any(has_job_file_index_bound(child, formal_alias) for child in children)
    return False


def assert_formal_reads_are_key_bounded(plan):
    frontier_reads = [
        node for node in plan_nodes(plan) if node.get("Relation Name") == "formal_interviews"
    ]
    assert frontier_reads, "The plan must actually read formal interviews"
    for node in frontier_reads:
        # Bitmap heaps obtain their bounds from the child index tree. Every OR branch must
        # stay within a file; an AND is bounded when at least one operand supplies the key.
        assert has_job_file_index_bound(node, node["Alias"]), node


@pytest.mark.parametrize("bitmap", [False, True], ids=["index", "bitmap"])
def test_failure_blocks_read_each_failed_files_frontier_by_key(database_settings, bitmap):
    """A historical failure must cost one keyed lookup, not an aggregate over every file."""

    async def scenario(database):
        failed = await start_turn(database)
        await complete_turn(database, failed)
        for _ in range(3):
            await complete_turn(database, await start_turn(database))
        async with database.sessions.begin() as session:
            await consolidation_requests.record_failure(
                session,
                job_file_id=failed.scope.job_file_id,
                execution_id=failed.scope.execution_id,
                command_id=uuid4(),
                reason="synthetic",
                frontier=1,
            )
        statements = []

        def capture(connection, cursor, statement, parameters, context, executemany):
            statements.append((statement, parameters))

        event.listen(database.engine.sync_engine, "before_cursor_execute", capture)
        try:
            async with database.sessions() as session:
                assert list((await read_blocks(session)).reasons) == [failed.scope.job_file_id]
        finally:
            event.remove(database.engine.sync_engine, "before_cursor_execute", capture)
        [(statement, parameters)] = [pair for pair in statements if "formal_interviews" in pair[0]]
        async with database.engine.connect() as connection:
            # These planner settings exercise available access paths, not default performance.
            await connection.exec_driver_sql("SET LOCAL enable_seqscan = off")
            if bitmap:
                await connection.exec_driver_sql("SET LOCAL enable_indexscan = off")
                await connection.exec_driver_sql("SET LOCAL enable_indexonlyscan = off")
            else:
                await connection.exec_driver_sql("SET LOCAL enable_bitmapscan = off")
            result = await connection.exec_driver_sql(
                "EXPLAIN (VERBOSE, FORMAT JSON) " + statement, parameters
            )
            plan = result.scalar_one()[0]["Plan"]
        if bitmap:
            assert any(
                node["Node Type"] == "Bitmap Heap Scan"
                and node.get("Relation Name") == "formal_interviews"
                for node in plan_nodes(plan)
            ), plan
        assert_formal_reads_are_key_bounded(plan)

    execute(database_settings, scenario)


@pytest.mark.parametrize(
    ("query", "bitmap", "expected_node"),
    [
        (
            "SELECT job_file_id, max(interview_sequence) FROM formal_interviews "
            "GROUP BY job_file_id",
            False,
            "Index Only Scan",
        ),
        (
            "SELECT job_file_id FROM formal_interviews "
            "WHERE job_file_id::text = '00000000-0000-0000-0000-000000000001'",
            False,
            "Index Only Scan",
        ),
        (
            "SELECT job_file_id FROM formal_interviews "
            "WHERE source_id = '00000000-0000-0000-0000-000000000001'",
            True,
            "Bitmap Heap Scan",
        ),
        (
            "SELECT job_file_id FROM formal_interviews "
            "WHERE job_file_id = '00000000-0000-0000-0000-000000000001' "
            "OR source_id = '00000000-0000-0000-0000-000000000002'",
            True,
            "BitmapOr",
        ),
        (
            "SELECT job_file_id FROM formal_interviews "
            "WHERE job_file_id = '00000000-0000-0000-0000-000000000001' "
            "UNION ALL SELECT job_file_id FROM formal_interviews",
            False,
            "Append",
        ),
    ],
    ids=["whole-table-aggregate", "filter-only", "wrong-index-key", "unbounded-or", "mixed-scans"],
)
def test_frontier_plan_assertion_rejects_unbounded_reads(
    database_settings, query, bitmap, expected_node
):
    """Negative controls use real PostgreSQL plans, including keyed and unkeyed branches."""

    async def scenario(database):
        async with database.engine.connect() as connection:
            await connection.exec_driver_sql("SET LOCAL enable_seqscan = off")
            if bitmap:
                await connection.exec_driver_sql("SET LOCAL enable_indexscan = off")
                await connection.exec_driver_sql("SET LOCAL enable_indexonlyscan = off")
            else:
                await connection.exec_driver_sql("SET LOCAL enable_bitmapscan = off")
            result = await connection.exec_driver_sql("EXPLAIN (VERBOSE, FORMAT JSON) " + query)
            plan = result.scalar_one()[0]["Plan"]
        assert any(node["Node Type"] == expected_node for node in plan_nodes(plan)), plan
        with pytest.raises(AssertionError):
            assert_formal_reads_are_key_bounded(plan)

    execute(database_settings, scenario)


def test_frontier_plan_assertion_does_not_use_a_key_from_a_nested_expression(database_settings):
    """The joined relation's file comparison does not constrain the formal index key."""

    async def scenario(database):
        writer = await start_turn(database)
        await complete_turn(database, writer)
        async with database.sessions.begin() as session:
            await consolidation_requests.record_failure(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=uuid4(),
                reason="synthetic",
                frontier=1,
            )
        async with database.engine.connect() as connection:
            source_id = (
                await connection.exec_driver_sql(
                    "SELECT source_id FROM formal_interviews WHERE job_file_id = %s LIMIT 1",
                    (writer.scope.job_file_id,),
                )
            ).scalar_one()
            query = (
                "SELECT f.job_file_id FROM memory_operations AS m "
                "JOIN formal_interviews AS f ON f.source_id = "
                "CASE WHEN m.job_file_id = %s THEN %s::uuid ELSE %s::uuid END"
            )
            parameters = (writer.scope.job_file_id, source_id, uuid4())
            assert (await connection.exec_driver_sql(query, parameters)).scalars().all() == [
                writer.scope.job_file_id
            ]
            await connection.exec_driver_sql("SET LOCAL enable_hashjoin = off")
            await connection.exec_driver_sql("SET LOCAL enable_mergejoin = off")
            await connection.exec_driver_sql("SET LOCAL enable_seqscan = off")
            await connection.exec_driver_sql("SET LOCAL enable_bitmapscan = off")
            result = await connection.exec_driver_sql(
                "EXPLAIN (VERBOSE, FORMAT JSON) " + query, parameters
            )
            plan = result.scalar_one()[0]["Plan"]
        formal_reads = [
            node for node in plan_nodes(plan) if node.get("Relation Name") == "formal_interviews"
        ]
        assert len(formal_reads) == 1
        assert formal_reads[0]["Index Cond"].startswith("(f.source_id = CASE"), plan
        with pytest.raises(AssertionError):
            assert_formal_reads_are_key_bounded(plan)

    execute(database_settings, scenario)


def test_a_consolidation_request_without_a_consultant_turn_is_damaged_evidence(database_settings):
    async def scenario(database):
        flow = MemoryConsolidationWorkflow(database.sessions)
        writer = await start_turn(database)
        await complete_turn(database, writer)
        async with database.sessions.begin() as session:
            memory = ExecutionScope(writer.scope.job_file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            await executions.admit_execution(session, memory)
            # Finished, so discovery does not skip the file as having active Memory work.
            batch = await executions.claim_writer(session, memory, writer_id=uuid4())
            await executions.finish_execution(session, batch, ExecutionStatus.COMPLETED)
        from caliburn.features.interviews import queries as interviews
        from tests.integration.test_memory_evidence_isolation import replace_evidence

        command_id = uuid4()
        async with database.sessions.begin() as session:
            source_id = await interviews.read_execution_input_source_id(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
            )
            await consolidation_requests.record_intent(
                session,
                job_file_id=writer.scope.job_file_id,
                execution_id=writer.scope.execution_id,
                command_id=command_id,
                source_id=source_id,
            )
        await replace_evidence(database, command_id, {"execution_id": memory.execution_id})
        discovery = await flow.discover()
        assert discovery.ready_file_ids == ()
        assert len(discovery.issues) == 1
        assert discovery.issues[0].job_file_id == writer.scope.job_file_id
        assert discovery.issues[0].reason == "missing_consultant_turn"

    execute(database_settings, scenario)
