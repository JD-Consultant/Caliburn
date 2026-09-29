"""Candidate pointers and original operations retain file scope and fixed JD history."""

import asyncio
from uuid import UUID, uuid4

import psycopg
import pytest
from alembic import command
from psycopg.types.json import Jsonb
from sqlalchemy import create_engine, text

from caliburn.adapters.database import Database, migration_config
from caliburn.features.job_description.candidate_persistence import (
    JdCandidateRecord,
    read_candidate,
)
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres

CANDIDATE_INSERT = (
    "INSERT INTO jd_candidates "
    "(job_file_id, execution_id, base_revision_id, current_revision_id, generation_id, status) "
    "VALUES (%s,%s,%s,%s,%s,%s)"
)
OPERATION_INSERT = (
    "INSERT INTO jd_operations (job_file_id, command_id, kind, expected_revision_id, "
    "result_revision_id, candidate_execution_id, candidate_generation_id, request_payload) "
    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)"
)


def create_file_revision(connection: psycopg.Connection) -> tuple[UUID, UUID]:
    job_file_id, revision_id = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO job_files (job_file_id, creation_command_id, initial_display_name, "
        "display_name, employee_name) VALUES (%s,%s,'candidate test','candidate test','synthetic')",
        (job_file_id, uuid4()),
    )
    connection.execute(
        "INSERT INTO jd_revisions (job_file_id, revision_id) VALUES (%s,%s)",
        (job_file_id, revision_id),
    )
    connection.execute(
        "INSERT INTO job_descriptions (job_file_id, initial_revision_id, current_revision_id) "
        "VALUES (%s,%s,%s)",
        (job_file_id, revision_id, revision_id),
    )
    return job_file_id, revision_id


def create_execution(connection: psycopg.Connection, job_file_id: UUID) -> UUID:
    execution_id = uuid4()
    connection.execute(
        "INSERT INTO executions (job_file_id, execution_id, kind, status) "
        "VALUES (%s,%s,'consultant_turn','active')",
        (job_file_id, execution_id),
    )
    return execution_id


def create_candidate(
    connection: psycopg.Connection, job_file_id: UUID, revision_id: UUID
) -> tuple[UUID, UUID]:
    execution_id = create_execution(connection, job_file_id)
    generation_id = uuid4()
    connection.execute(
        CANDIDATE_INSERT,
        (job_file_id, execution_id, revision_id, revision_id, generation_id, "open"),
    )
    return execution_id, generation_id


@pytest.mark.parametrize("kind", ["restore_candidate", "discard_candidate", "adopt_candidate"])
def test_candidate_operation_kinds_seal_nonformal_revision_results(
    database_connection: psycopg.Connection, kind: str
) -> None:
    connection = database_connection
    job_file_id, base_revision_id = create_file_revision(connection)
    execution_id, generation_id = create_candidate(connection, job_file_id, base_revision_id)
    revision_id = uuid4()
    connection.execute(
        "INSERT INTO jd_revisions (job_file_id, revision_id, parent_revision_id) VALUES (%s,%s,%s)",
        (job_file_id, revision_id, base_revision_id),
    )
    area_id, content_revision_id = uuid4(), uuid4()
    connection.execute(
        "INSERT INTO jd_area_revisions (job_file_id, area_id, content_revision_id, title) "
        "VALUES (%s,%s,%s,'candidate area')",
        (job_file_id, area_id, content_revision_id),
    )
    connection.execute(
        "INSERT INTO jd_area_selections "
        "(job_file_id, revision_id, area_id, content_revision_id, position) VALUES (%s,%s,%s,%s,0)",
        (job_file_id, revision_id, area_id, content_revision_id),
    )
    # The DB admits operation kinds; workflow owns their execution/status semantics.
    connection.execute(
        OPERATION_INSERT,
        (
            job_file_id,
            uuid4(),
            kind,
            base_revision_id,
            revision_id,
            execution_id,
            generation_id,
            Jsonb({}),
        ),
    )
    assert connection.execute(
        "SELECT current_revision_id FROM job_descriptions WHERE job_file_id = %s", (job_file_id,)
    ).fetchone() == (base_revision_id,)
    with pytest.raises(psycopg.errors.CheckViolation, match="Cannot append"):
        connection.execute(
            "INSERT INTO jd_area_selections "
            "(job_file_id, revision_id, area_id, content_revision_id, position) "
            "VALUES (%s,%s,%s,%s,1)",
            (job_file_id, revision_id, area_id, content_revision_id),
        )
    for statement in (
        "UPDATE jd_operations SET request_payload = '{}'",
        "DELETE FROM jd_operations",
        "UPDATE jd_revisions SET job_title = 'changed'",
        "DELETE FROM jd_revisions",
        "UPDATE jd_area_selections SET position = 1",
        "DELETE FROM jd_area_selections",
    ):
        with pytest.raises(psycopg.errors.CheckViolation, match="immutable"):
            connection.execute(statement)


@pytest.mark.parametrize("foreign_target", ["execution", "base_revision", "current_revision"])
def test_candidate_foreign_keys_reject_other_files(
    database_connection: psycopg.Connection, foreign_target: str
) -> None:
    connection = database_connection
    file_id, revision_id = create_file_revision(connection)
    other_file_id, other_revision_id = create_file_revision(connection)
    execution_id = create_execution(connection, file_id)
    other_execution_id = create_execution(connection, other_file_id)
    with pytest.raises(psycopg.errors.ForeignKeyViolation) as error:
        connection.execute(
            CANDIDATE_INSERT,
            (
                file_id,
                other_execution_id if foreign_target == "execution" else execution_id,
                other_revision_id if foreign_target == "base_revision" else revision_id,
                other_revision_id if foreign_target == "current_revision" else revision_id,
                uuid4(),
                "open",
            ),
        )
    assert error.value.diag.constraint_name == f"fk_jd_candidates_{foreign_target}"
    assert connection.execute("SELECT count(*) FROM jd_candidates").fetchone() == (0,)


def test_candidate_identity_status_and_generation_are_constrained(
    database_connection: psycopg.Connection,
) -> None:
    connection = database_connection
    file_id, revision_id = create_file_revision(connection)
    execution_id, generation_id = create_candidate(connection, file_id, revision_id)
    with pytest.raises(psycopg.errors.UniqueViolation):
        connection.execute(
            CANDIDATE_INSERT,
            (file_id, execution_id, revision_id, revision_id, uuid4(), "open"),
        )
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        connection.execute("UPDATE jd_candidates SET status = 'completed'")
    assert error.value.diag.constraint_name == "ck_jd_candidates_status"
    with pytest.raises(psycopg.errors.NotNullViolation):
        connection.execute("UPDATE jd_candidates SET generation_id = NULL")
    assert connection.execute("SELECT generation_id, status FROM jd_candidates").fetchone() == (
        generation_id,
        "open",
    )
    # Status transitions are owned by the service; the DB only enforces the finite value set.
    for status in ("adopted", "discarded", "open"):
        connection.execute("UPDATE jd_candidates SET status = %s", (status,))
        assert connection.execute("SELECT status FROM jd_candidates").fetchone() == (status,)


@pytest.mark.parametrize("missing", ["execution", "generation"])
def test_operation_candidate_scope_requires_both_values(
    database_connection: psycopg.Connection, missing: str
) -> None:
    connection = database_connection
    file_id, revision_id = create_file_revision(connection)
    execution_id, generation_id = create_candidate(connection, file_id, revision_id)
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        connection.execute(
            OPERATION_INSERT,
            (
                file_id,
                uuid4(),
                "revise_profile",
                revision_id,
                revision_id,
                None if missing == "execution" else execution_id,
                None if missing == "generation" else generation_id,
                Jsonb({}),
            ),
        )
    assert error.value.diag.constraint_name == "ck_jd_operations_candidate_scope"


def test_candidate_operations_reject_foreign_or_missing_candidates_and_share_command_identity(
    database_connection: psycopg.Connection,
) -> None:
    connection = database_connection
    file_id, revision_id = create_file_revision(connection)
    other_file_id, other_revision_id = create_file_revision(connection)
    other_execution_id, other_generation_id = create_candidate(
        connection, other_file_id, other_revision_id
    )
    execution_id = create_execution(connection, file_id)
    for candidate_execution_id in (other_execution_id, execution_id):
        with pytest.raises(psycopg.errors.ForeignKeyViolation) as error:
            connection.execute(
                OPERATION_INSERT,
                (
                    file_id,
                    uuid4(),
                    "revise_profile",
                    revision_id,
                    revision_id,
                    candidate_execution_id,
                    other_generation_id,
                    Jsonb({}),
                ),
            )
        assert error.value.diag.constraint_name == "fk_jd_operations_candidate"
    connection.execute(
        CANDIDATE_INSERT,
        (file_id, execution_id, revision_id, revision_id, other_generation_id, "open"),
    )
    command_id = uuid4()
    connection.execute(
        OPERATION_INSERT,
        (file_id, command_id, "revise_profile", revision_id, revision_id, None, None, Jsonb({})),
    )
    with pytest.raises(psycopg.errors.UniqueViolation):
        connection.execute(
            OPERATION_INSERT,
            (
                file_id,
                command_id,
                "restore_candidate",
                revision_id,
                revision_id,
                execution_id,
                other_generation_id,
                Jsonb({}),
            ),
        )
    with pytest.raises(psycopg.errors.CheckViolation) as error:
        connection.execute(
            OPERATION_INSERT,
            (file_id, uuid4(), "unknown", revision_id, revision_id, None, None, Jsonb({})),
        )
    assert error.value.diag.constraint_name == "ck_jd_operations_kind"


def test_restore_result_keeps_its_generation_after_candidate_advances(
    database_connection: psycopg.Connection,
) -> None:
    connection = database_connection
    file_id, revision_id = create_file_revision(connection)
    execution_id, generation_id = create_candidate(connection, file_id, revision_id)
    result_generation_id = uuid4()
    payload = {"result_generation_id": str(result_generation_id)}
    connection.execute(
        OPERATION_INSERT,
        (
            file_id,
            uuid4(),
            "restore_candidate",
            revision_id,
            revision_id,
            execution_id,
            generation_id,
            Jsonb(payload),
        ),
    )
    for current_generation_id in (result_generation_id, uuid4()):
        connection.execute("UPDATE jd_candidates SET generation_id = %s", (current_generation_id,))
    assert connection.execute(
        "SELECT candidate_generation_id, request_payload FROM jd_operations"
    ).fetchone() == (generation_id, payload)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        connection.execute("DELETE FROM jd_candidates")


def test_read_candidate_refreshes_cached_position_without_locking_or_committing(
    database_settings: DatabaseSettings, database_connection: psycopg.Connection
) -> None:
    file_id, revision_id = create_file_revision(database_connection)
    execution_id = create_execution(database_connection, file_id)
    generation_id, next_generation_id = uuid4(), uuid4()

    async def exercise() -> None:
        database = Database(database_settings)
        try:
            async with database.sessions.begin() as session:
                record = JdCandidateRecord(
                    job_file_id=file_id,
                    execution_id=execution_id,
                    base_revision_id=revision_id,
                    current_revision_id=revision_id,
                    generation_id=generation_id,
                    status="open",
                )
                session.add(record)
                await session.flush()
                assert record.created_at.tzinfo is not None
            async with database.sessions() as session:
                original = await read_candidate(session, file_id, execution_id)
                assert original is not None
                assert await read_candidate(session, uuid4(), execution_id) is None
                assert await read_candidate(session, file_id, uuid4()) is None
                async with database.sessions.begin() as writer:
                    # A plain candidate read must not hold a row lock against another writer.
                    await writer.execute(text("SET LOCAL lock_timeout = '500ms'"))
                    await writer.execute(
                        text("UPDATE jd_candidates SET generation_id = :generation_id"),
                        {"generation_id": next_generation_id},
                    )
                refreshed = await read_candidate(session, file_id, execution_id)
                assert refreshed is original
                assert refreshed.generation_id == next_generation_id
                refreshed.status = "discarded"
                await session.flush()
                pending = await read_candidate(session, file_id, execution_id)
                assert pending is not None and pending.status == "discarded"
                # Closing the caller's uncommitted session must still roll back its change.
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(exercise())
    assert database_connection.execute(
        "SELECT generation_id, status FROM jd_candidates"
    ).fetchone() == (next_generation_id, "open")


def test_upgrade_preserves_existing_operations_and_downgrade_refuses_history_loss(
    empty_database_settings: DatabaseSettings,
) -> None:
    settings = empty_database_settings
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "0009_jd_collaborators_conditions")
            file_id, revision_id = uuid4(), uuid4()
            connection.execute(
                text(
                    "INSERT INTO job_files (job_file_id, creation_command_id, "
                    "initial_display_name, display_name, employee_name) "
                    "VALUES (:file_id,:command_id,'test','test','test')"
                ),
                {"file_id": file_id, "command_id": uuid4()},
            )
            connection.execute(
                text(
                    "INSERT INTO jd_revisions (job_file_id, revision_id) "
                    "VALUES (:file_id,:revision)"
                ),
                {"file_id": file_id, "revision": revision_id},
            )
            for kind in (
                "revise_profile",
                "edit_areas",
                "edit_tasks",
                "edit_capabilities",
                "edit_collaborators",
                "edit_conditions",
            ):
                connection.execute(
                    text(
                        "INSERT INTO jd_operations (job_file_id, command_id, kind, "
                        "expected_revision_id, result_revision_id, request_payload) "
                        "VALUES (:file_id,:command_id,:kind,:revision,:revision,'{}')"
                    ),
                    {
                        "file_id": file_id,
                        "command_id": uuid4(),
                        "kind": kind,
                        "revision": revision_id,
                    },
                )
            original_query = text(
                "SELECT job_file_id, command_id, kind, expected_revision_id, result_revision_id, "
                "request_payload, created_at FROM jd_operations ORDER BY command_id"
            )
            original = connection.execute(original_query).all()
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            assert connection.execute(original_query).all() == original
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM jd_operations "
                        "WHERE candidate_execution_id IS NULL AND candidate_generation_id IS NULL"
                    )
                ).scalar_one()
                == 6
            )
            # The expanded CHECK continues accepting all six manual kinds after upgrade.
            connection.execute(
                text(
                    "INSERT INTO jd_operations (job_file_id, command_id, kind, "
                    "expected_revision_id, result_revision_id, request_payload) "
                    "SELECT job_file_id, gen_random_uuid(), kind, "
                    "expected_revision_id, result_revision_id, request_payload FROM jd_operations"
                )
            )
            assert connection.execute(text("SELECT count(*) FROM jd_operations")).scalar_one() == 12
            with pytest.raises(RuntimeError, match="must remain recoverable"):
                command.downgrade(config, "0009_jd_collaborators_conditions")
            assert connection.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one() == ("0010_jd_candidates")
    finally:
        engine.dispose()
