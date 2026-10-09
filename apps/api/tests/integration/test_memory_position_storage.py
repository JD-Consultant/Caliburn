"""PostgreSQL fixed positions, scoped batch coordinates and immutable publication records."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import replace
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database, migration_config
from caliburn.features.work_memory import batch_persistence as batches
from caliburn.features.work_memory import position_persistence as positions
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryContent, MemoryMapEntry, MemorySourceWindow
from caliburn.features.work_memory.revision_service import write_object_revision
from caliburn.features.work_memory.revisions import (
    MemoryLayer,
    MemoryObjectRevision,
    MemoryRevisionReference,
)
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


def execute[T](settings: DatabaseSettings, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            async with database.sessions.begin() as session:
                return await operation(session)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


def seed_file(connection: psycopg.Connection) -> MemorySourceWindow:
    file_id, source_id = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO job_files (job_file_id,initial_display_name,"
        "display_name,employee_name) VALUES (%s,'Memory','Memory','合成員工')",
        (file_id,),
    )
    for sequence, role, identity in ((1, "app", uuid4()), (2, "employee", source_id)):
        connection.execute(
            "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
            "VALUES (%s,%s,%s,'合成原文')",
            (file_id, identity, role),
        )
        connection.execute(
            "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) "
            "VALUES (%s,%s,%s)",
            (file_id, sequence, identity),
        )
    return MemorySourceWindow(file_id, source_id, 0, 2)


@pytest.fixture
def window(database_connection: psycopg.Connection) -> MemorySourceWindow:
    return seed_file(database_connection)


def reference(revision: MemoryObjectRevision) -> MemoryRevisionReference:
    return MemoryRevisionReference(revision.object_id, revision.revision_id)


def create_revision(
    settings: DatabaseSettings,
    window: MemorySourceWindow,
    title: str = "盤點",
    layer: MemoryLayer = MemoryLayer.WORK_SITUATION,
) -> MemoryObjectRevision:
    return execute(
        settings,
        lambda session: write_object_revision(
            session, window, layer=layer, content=MemoryContent(title, "描述", "正文")
        ),
    )


def create_position(
    settings: DatabaseSettings,
    file_id: UUID,
    references: tuple[MemoryRevisionReference, ...] = (),
    parent: UUID | None = None,
) -> UUID:
    position_id = uuid4()
    execute(
        settings,
        lambda session: positions.insert_position(
            session, file_id, position_id, parent, references
        ),
    )
    return position_id


def test_memory_storage_migration_provides_candidate_and_publication_tables(
    database_connection: psycopg.Connection,
) -> None:
    tables = {
        row[0]
        for row in database_connection.execute(
            "SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"
        )
    }
    assert {
        "memory_positions",
        "memory_position_members",
        "memory_batches",
        "memory_snapshots",
        "memory_heads",
        "memory_operations",
    } <= tables


def test_migration_reentry_and_orm_metadata_agree(database_settings: DatabaseSettings) -> None:
    engine = create_engine(
        database_settings.sqlalchemy_url,
        connect_args={"options": f"-c search_path={database_settings.schema}"},
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=database_settings.schema)
            command.upgrade(config, "head")
            command.check(config)
    finally:
        engine.dispose()


def test_empty_missing_and_unsealed_positions_are_distinct(
    database_settings: DatabaseSettings, window: MemorySourceWindow
) -> None:
    async def check(session: AsyncSession) -> None:
        file_id, position_id = window.job_file_id, uuid4()
        assert await positions.read_position_members(session, file_id, position_id) is None
        record = positions.MemoryPositionRecord(job_file_id=file_id, position_id=position_id)
        session.add(record)
        await session.flush()
        assert await positions.read_position_members(session, file_id, position_id) is None
        assert (
            await positions.read_position_map(
                session, file_id, position_id, MemoryLayer.WORK_SITUATION
            )
            == ()
        )
        record.is_sealed = True
        await session.flush()
        assert await positions.read_position_members(session, file_id, position_id) == ()
        assert await positions.read_position_members(session, uuid4(), position_id) is None

    execute(database_settings, check)


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE memory_positions SET parent_position_id = NULL",
        "UPDATE memory_positions SET is_sealed = false",
        "DELETE FROM memory_positions",
        "UPDATE memory_position_members SET revision_id = revision_id",
        "DELETE FROM memory_position_members",
    ],
)
def test_sealed_positions_and_members_reject_mutation(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
    statement: str,
) -> None:
    revision = create_revision(database_settings, window)
    create_position(database_settings, window.job_file_id, (reference(revision),))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(statement)


def test_sealed_position_rejects_append_and_unsealed_header_cannot_commit(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
) -> None:
    revision = create_revision(database_settings, window)
    position_id = create_position(database_settings, window.job_file_id)
    with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append"):
        database_connection.execute(
            "INSERT INTO memory_position_members VALUES (%s,%s,%s,%s)",
            (window.job_file_id, position_id, revision.object_id, revision.revision_id),
        )
    unfinished = uuid4()
    with pytest.raises(psycopg.errors.CheckViolation, match="before commit"):
        with database_connection.transaction():
            database_connection.execute(
                "INSERT INTO memory_positions (job_file_id,position_id) VALUES (%s,%s)",
                (window.job_file_id, unfinished),
            )
    assert (
        database_connection.execute(
            "SELECT 1 FROM memory_positions WHERE position_id=%s", (unfinished,)
        ).fetchone()
        is None
    )
    with pytest.raises(psycopg.errors.CheckViolation, match="before sealing"):
        database_connection.execute(
            "INSERT INTO memory_positions (job_file_id,position_id,is_sealed) VALUES (%s,%s,true)",
            (window.job_file_id, uuid4()),
        )


def test_sealing_rejects_duplicate_titles_in_same_layer_and_duplicate_object_selection(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
) -> None:
    first = create_revision(database_settings, window)
    second = create_revision(database_settings, window)
    with pytest.raises(IntegrityError, match="unique exact titles"):
        create_position(
            database_settings, window.job_file_id, (reference(first), reference(second))
        )
    with pytest.raises(IntegrityError):
        create_position(database_settings, window.job_file_id, (reference(first), reference(first)))
    assert database_connection.execute("SELECT count(*) FROM memory_positions").fetchone() == (0,)


def test_cross_layer_names_and_exact_c_title_variants_are_legal_in_map(
    database_settings: DatabaseSettings, window: MemorySourceWindow
) -> None:
    revisions = tuple(
        create_revision(database_settings, window, title)
        for title in ("Title", "title", "Title ", "é", "e\u0301")
    )
    understanding = create_revision(
        database_settings, window, "Title", MemoryLayer.WORK_UNDERSTANDING
    )
    position_id = create_position(
        database_settings,
        window.job_file_id,
        tuple(reference(item) for item in (*revisions, understanding)),
    )

    async def check(session: AsyncSession) -> None:
        assert await positions.read_position_map(
            session, window.job_file_id, position_id, MemoryLayer.WORK_SITUATION
        ) == tuple(
            MemoryMapEntry(item.object_id, item.content.title, item.content.description)
            for item in sorted(revisions, key=lambda item: item.object_id)
        )
        assert await positions.read_position_map(
            session, window.job_file_id, position_id, MemoryLayer.WORK_UNDERSTANDING
        ) == (MemoryMapEntry(understanding.object_id, "Title", "描述"),)
        assert (
            await positions.read_position_map(
                session, uuid4(), position_id, MemoryLayer.WORK_SITUATION
            )
            == ()
        )

    execute(database_settings, check)


def test_source_identity_must_be_present_but_candidate_may_select_a_newer_source_revision(
    database_settings: DatabaseSettings, window: MemorySourceWindow
) -> None:
    old = create_revision(database_settings, window)
    understanding = execute(
        database_settings,
        lambda session: write_object_revision(
            session,
            window,
            layer=MemoryLayer.WORK_UNDERSTANDING,
            content=MemoryContent("理解", "描述", "正文"),
            work_situation_references=frozenset({reference(old)}),
        ),
    )
    new = execute(
        database_settings,
        lambda session: write_object_revision(
            session,
            window,
            layer=old.layer,
            previous=reference(old),
            content=replace(old.content, title="新盤點"),
        ),
    )
    with pytest.raises(IntegrityError, match="missing a bound situation identity"):
        create_position(database_settings, window.job_file_id, (reference(understanding),))
    position_id = create_position(
        database_settings, window.job_file_id, (reference(understanding), reference(new))
    )
    assert execute(
        database_settings,
        lambda session: positions.read_position_members(session, window.job_file_id, position_id),
    ) == tuple(sorted((reference(understanding), reference(new))))


def test_parent_and_revision_cannot_cross_files(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
) -> None:
    other = seed_file(database_connection)
    other_position = create_position(database_settings, other.job_file_id)
    other_revision = create_revision(database_settings, other)
    with pytest.raises(IntegrityError, match="same-file parent"):
        create_position(database_settings, window.job_file_id, parent=other_position)
    with pytest.raises(IntegrityError, match="same-file revision"):
        create_position(database_settings, window.job_file_id, (reference(other_revision),))


def test_ancestry_is_inclusive_and_cannot_cross_boundary_or_branch(
    database_settings: DatabaseSettings, window: MemorySourceWindow
) -> None:
    file_id = window.job_file_id
    root = create_position(database_settings, file_id)
    boundary = create_position(database_settings, file_id, parent=root)
    middle = create_position(database_settings, file_id, parent=boundary)
    tip = create_position(database_settings, file_id, parent=middle)
    sibling = create_position(database_settings, file_id, parent=boundary)

    async def check(session: AsyncSession) -> None:
        assert await positions.is_position_ancestor(session, file_id, middle, tip, boundary)
        assert await positions.is_position_ancestor(session, file_id, boundary, tip, boundary)
        assert await positions.is_position_ancestor(session, file_id, tip, tip, boundary)
        assert not await positions.is_position_ancestor(session, file_id, root, tip, boundary)
        assert not await positions.is_position_ancestor(session, file_id, sibling, tip, boundary)
        assert not await positions.is_position_ancestor(session, file_id, tip, tip, sibling)
        assert not await positions.is_position_ancestor(session, file_id, tip, tip, uuid4())
        assert not await positions.is_position_ancestor(session, uuid4(), middle, tip, boundary)

    execute(database_settings, check)


@pytest.fixture
def batch_position(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
) -> MemoryBatchPosition:
    position = MemoryBatchPosition(
        window.job_file_id,
        uuid4(),
        uuid4(),
        uuid4(),
        MemoryLayer.WORK_SITUATION,
        create_position(database_settings, window.job_file_id),
    )
    database_connection.execute(
        "INSERT INTO executions (execution_id,job_file_id,kind,status) "
        "VALUES (%s,%s,'memory_batch','active')",
        (position.execution_id, position.job_file_id),
    )

    async def insert(session: AsyncSession) -> None:
        session.add(
            batches.MemoryBatchRecord(
                job_file_id=position.job_file_id,
                execution_id=position.execution_id,
                base_snapshot_id=None,
                base_position_id=position.position_id,
                current_position_id=position.position_id,
                generation_id=position.generation_id,
                stage_id=position.stage_id,
                phase=position.phase.value,
                status="open",
                through_source_id=window.through_source_id,
                covered_through_sequence=0,
                through_sequence=window.through_sequence,
            )
        )
        await session.flush()

    execute(database_settings, insert)
    return position


def result_fields(position: MemoryBatchPosition) -> dict[str, str]:
    return {
        "job_file_id": str(position.job_file_id),
        "execution_id": str(position.execution_id),
        "generation_id": str(position.generation_id),
        "stage_id": str(position.stage_id),
        "phase": position.phase.value,
        "position_id": str(position.position_id),
    }


@pytest.fixture
def published_snapshot(
    database_settings: DatabaseSettings,
    window: MemorySourceWindow,
    batch_position: MemoryBatchPosition,
) -> UUID:
    snapshot_id = uuid4()

    async def publish(session: AsyncSession) -> None:
        session.add(
            batches.MemorySnapshotRecord(
                job_file_id=window.job_file_id,
                snapshot_id=snapshot_id,
                position_id=batch_position.position_id,
                execution_id=batch_position.execution_id,
                through_source_id=window.through_source_id,
                covered_through_sequence=window.through_sequence,
            )
        )
        await session.flush()
        await batches.set_head(session, window.job_file_id, snapshot_id)
        session.add(
            batches.MemoryOperationRecord(
                job_file_id=window.job_file_id,
                command_id=batch_position.execution_id,
                execution_id=batch_position.execution_id,
                kind="start",
                request_payload={"through_source_id": str(window.through_source_id)},
                result_payload={**result_fields(batch_position), "snapshot_id": str(snapshot_id)},
            )
        )
        await session.flush()

    execute(database_settings, publish)
    return snapshot_id


@pytest.mark.parametrize(
    "statement",
    [
        "UPDATE memory_snapshots SET covered_through_sequence=3",
        "DELETE FROM memory_snapshots",
        "UPDATE memory_operations SET result_payload='{}'::jsonb",
        "DELETE FROM memory_operations",
    ],
)
def test_snapshot_and_operation_are_immutable(
    database_connection: psycopg.Connection, published_snapshot: UUID, statement: str
) -> None:
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute(statement)


def test_first_batch_has_no_head_and_reads_are_scoped(
    database_settings: DatabaseSettings, batch_position: MemoryBatchPosition
) -> None:
    async def check(session: AsyncSession) -> None:
        file_id, execution_id = batch_position.job_file_id, batch_position.execution_id
        assert await batches.read_head(session, file_id) is None
        batch = await batches.read_batch(session, file_id, execution_id)
        assert batch is not None and batch.base_snapshot_id is None
        assert batch.current_position_id == batch_position.position_id
        assert await batches.read_batch(session, uuid4(), execution_id) is None
        assert await batches.read_operation(session, file_id, execution_id) is None

    execute(database_settings, check)


def test_recorded_position_requires_all_coordinates_and_accepts_extra_result_fields(
    database_settings: DatabaseSettings,
    batch_position: MemoryBatchPosition,
    published_snapshot: UUID,
) -> None:
    async def check(session: AsyncSession) -> None:
        file_id, execution_id = batch_position.job_file_id, batch_position.execution_id
        snapshot = await batches.read_snapshot(session, file_id, published_snapshot)
        assert snapshot is not None and snapshot.position_id == batch_position.position_id
        assert await batches.read_head(session, file_id) is snapshot
        assert await batches.read_snapshot(session, uuid4(), published_snapshot) is None
        assert await batches.read_head(session, uuid4()) is None
        operation = await batches.read_operation(session, file_id, execution_id)
        assert operation is not None and operation.kind == "start"
        assert await batches.read_operation(session, uuid4(), execution_id) is None
        assert await batches.has_recorded_position(
            session, file_id, execution_id, result_fields(batch_position)
        )
        for forged in (
            replace(batch_position, job_file_id=uuid4()),
            replace(batch_position, execution_id=uuid4()),
            replace(batch_position, generation_id=uuid4()),
            replace(batch_position, stage_id=uuid4()),
            replace(batch_position, phase=MemoryLayer.WORK_UNDERSTANDING),
            replace(batch_position, position_id=uuid4()),
        ):
            assert not await batches.has_recorded_position(
                session, file_id, execution_id, result_fields(forged)
            )
        assert not await batches.has_recorded_position(
            session, file_id, uuid4(), result_fields(batch_position)
        )
        assert not await batches.has_recorded_position(
            session, file_id, execution_id, {"position_id": str(batch_position.position_id)}
        )

    execute(database_settings, check)


def test_batch_window_scoped_foreign_keys_and_single_snapshot_per_batch(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    batch_position: MemoryBatchPosition,
    published_snapshot: UUID,
) -> None:
    other = seed_file(database_connection)
    other_position = create_position(database_settings, other.job_file_id)
    for column, value in (
        ("base_position_id", other_position),
        ("current_position_id", other_position),
        ("through_source_id", other.through_source_id),
        ("execution_id", uuid4()),
        ("base_snapshot_id", uuid4()),
    ):
        with pytest.raises(psycopg.errors.ForeignKeyViolation):
            database_connection.execute(
                psycopg.sql.SQL("UPDATE memory_batches SET {}=%s").format(
                    psycopg.sql.Identifier(column)
                ),
                (value,),
            )
    for coverage in (-1, 2):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(
                "UPDATE memory_batches SET covered_through_sequence=%s", (coverage,)
            )
    with pytest.raises(psycopg.errors.UniqueViolation):
        database_connection.execute(
            "INSERT INTO memory_snapshots "
            "(job_file_id,snapshot_id,position_id,execution_id,through_source_id,"
            "covered_through_sequence) SELECT job_file_id,%s,position_id,execution_id,"
            "through_source_id,covered_through_sequence FROM memory_snapshots",
            (uuid4(),),
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "INSERT INTO memory_heads (job_file_id,snapshot_id) VALUES (%s,%s)",
            (other.job_file_id, published_snapshot),
        )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "INSERT INTO memory_operations VALUES (%s,%s,%s,'start','{}','{}')",
            (other.job_file_id, uuid4(), batch_position.execution_id),
        )


async def insert_snapshot(
    session: AsyncSession,
    window: MemorySourceWindow,
    execution_id: UUID,
    position_id: UUID,
) -> UUID:
    snapshot_id = uuid4()
    session.add(
        batches.MemorySnapshotRecord(
            job_file_id=window.job_file_id,
            snapshot_id=snapshot_id,
            position_id=position_id,
            execution_id=execution_id,
            through_source_id=window.through_source_id,
            covered_through_sequence=window.through_sequence,
        )
    )
    await session.flush()
    return snapshot_id


def test_snapshot_rejects_position_that_will_only_seal_after_its_insertion(
    database_settings: DatabaseSettings,
    window: MemorySourceWindow,
    batch_position: MemoryBatchPosition,
) -> None:
    async def write(session: AsyncSession) -> None:
        position = positions.MemoryPositionRecord(
            job_file_id=window.job_file_id, position_id=uuid4(), is_sealed=False
        )
        session.add(position)
        await session.flush()
        await insert_snapshot(session, window, batch_position.execution_id, position.position_id)
        position.is_sealed = True
        await session.flush()

    with pytest.raises(IntegrityError, match="Snapshot requires a sealed position"):
        execute(database_settings, write)


def test_snapshot_requires_selected_source_pairs_and_accepts_the_fixed_chain(
    database_settings: DatabaseSettings,
    window: MemorySourceWindow,
    batch_position: MemoryBatchPosition,
) -> None:
    old = create_revision(database_settings, window)
    understanding = execute(
        database_settings,
        lambda session: write_object_revision(
            session,
            window,
            layer=MemoryLayer.WORK_UNDERSTANDING,
            content=MemoryContent("理解", "描述", "正文"),
            work_situation_references=frozenset({reference(old)}),
        ),
    )
    new = execute(
        database_settings,
        lambda session: write_object_revision(
            session,
            window,
            layer=old.layer,
            previous=reference(old),
            content=replace(old.content, title="新版"),
        ),
    )
    candidate = create_position(
        database_settings, window.job_file_id, (reference(new), reference(understanding))
    )
    with pytest.raises(IntegrityError, match="Snapshot requires selected source revision pairs"):
        execute(
            database_settings,
            lambda session: insert_snapshot(
                session, window, batch_position.execution_id, candidate
            ),
        )
    fixed = execute(
        database_settings,
        lambda session: write_object_revision(
            session,
            window,
            layer=understanding.layer,
            previous=reference(understanding),
            content=understanding.content,
            work_situation_references=frozenset({reference(new)}),
        ),
    )
    position_id = create_position(
        database_settings, window.job_file_id, (reference(new), reference(fixed)), parent=candidate
    )
    assert execute(
        database_settings,
        lambda session: insert_snapshot(session, window, batch_position.execution_id, position_id),
    )


def test_snapshot_frontier_matches_its_formal_source(
    database_settings: DatabaseSettings,
    window: MemorySourceWindow,
    batch_position: MemoryBatchPosition,
) -> None:
    with pytest.raises(IntegrityError, match="Snapshot coverage must match its formal source"):
        execute(
            database_settings,
            lambda session: insert_snapshot(
                session,
                replace(window, through_sequence=3),
                batch_position.execution_id,
                batch_position.position_id,
            ),
        )


def test_snapshot_situation_interviews_cannot_exceed_frontier(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
    batch_position: MemoryBatchPosition,
) -> None:
    future_source = uuid4()
    database_connection.execute(
        "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) "
        "VALUES (%s,%s,'employee','後來來源')",
        (window.job_file_id, future_source),
    )
    database_connection.execute(
        "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) VALUES (%s,3,%s)",
        (window.job_file_id, future_source),
    )
    future_revision = execute(
        database_settings,
        lambda session: write_object_revision(
            session,
            replace(window, through_source_id=future_source, through_sequence=3),
            layer=MemoryLayer.WORK_SITUATION,
            content=MemoryContent("未來情境", "描述", "正文"),
            interview_references=frozenset({future_source}),
        ),
    )
    position_id = create_position(
        database_settings, window.job_file_id, (reference(future_revision),)
    )
    with pytest.raises(IntegrityError, match="Snapshot interview source exceeds coverage"):
        execute(
            database_settings,
            lambda session: insert_snapshot(
                session, window, batch_position.execution_id, position_id
            ),
        )


def test_mutable_batch_and_head_updates_respect_the_callers_rollback(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    window: MemorySourceWindow,
    batch_position: MemoryBatchPosition,
    published_snapshot: UUID,
) -> None:
    # The second completed execution is just storage setup; workflow owns admission/completion.
    second_execution = uuid4()
    database_connection.execute(
        "INSERT INTO executions (execution_id,job_file_id,kind,status) "
        "VALUES (%s,%s,'memory_batch','completed')",
        (second_execution, window.job_file_id),
    )
    database_connection.execute(
        "INSERT INTO memory_batches "
        "(job_file_id,execution_id,base_snapshot_id,base_position_id,current_position_id,"
        "generation_id,stage_id,phase,status,through_source_id,covered_through_sequence,"
        "through_sequence) SELECT job_file_id,%s,%s,base_position_id,current_position_id,"
        "generation_id,stage_id,phase,status,through_source_id,covered_through_sequence,"
        "through_sequence FROM memory_batches",
        (second_execution, published_snapshot),
    )
    second_snapshot = execute(
        database_settings,
        lambda session: insert_snapshot(
            session, window, second_execution, batch_position.position_id
        ),
    )

    async def rollback(session: AsyncSession) -> None:
        batch = await batches.read_batch(session, window.job_file_id, batch_position.execution_id)
        assert batch is not None
        batch.phase = MemoryLayer.WORK_UNDERSTANDING.value
        await session.flush()
        await batches.set_head(session, window.job_file_id, second_snapshot)
        head = await batches.read_head(session, window.job_file_id)
        assert head is not None and head.snapshot_id == second_snapshot
        raise RuntimeError("caller aborts")

    with pytest.raises(RuntimeError, match="caller aborts"):
        execute(database_settings, rollback)

    async def verify(session: AsyncSession) -> None:
        batch = await batches.read_batch(session, window.job_file_id, batch_position.execution_id)
        assert batch is not None and batch.phase == MemoryLayer.WORK_SITUATION.value
        head = await batches.read_head(session, window.job_file_id)
        assert head is not None and head.snapshot_id == published_snapshot
        await batches.set_head(session, window.job_file_id, second_snapshot)

    execute(database_settings, verify)
    head = execute(
        database_settings, lambda session: batches.read_head(session, window.job_file_id)
    )
    assert head is not None and head.snapshot_id == second_snapshot
