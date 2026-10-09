"""Evidence conversion is atomic and rejects malformed original scheduling receipts."""

import json
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from caliburn.adapters.database import migration_config

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("frontier", [3, None, True, "3", 3.5])
def test_conversion_preserves_valid_evidence_or_rolls_back(empty_database_settings, frontier):
    settings = empty_database_settings
    engine = create_engine(
        settings.sqlalchemy_url,
        connect_args={"options": f"-c search_path={settings.schema}"},
        hide_parameters=True,
    )
    file_id, execution_id, source_id = uuid4(), uuid4(), uuid4()
    intent_command, failure_command = uuid4(), uuid4()
    identities = dict(file=file_id, execution=execution_id, source=source_id)
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "0031_jd_operation_result_index")
            connection.execute(
                text(
                    "INSERT INTO job_files(job_file_id, initial_display_name, display_name, "
                    "employee_name) VALUES (:file, 'migration', 'migration', 'synthetic')"
                ),
                identities,
            )
            connection.execute(
                text(
                    "INSERT INTO executions(execution_id, job_file_id, kind, status) "
                    "VALUES (:execution, :file, 'consultant_turn', 'active')"
                ),
                identities,
            )
            connection.execute(
                text(
                    "INSERT INTO interview_texts(source_id, job_file_id, speaker, interview_text) "
                    "VALUES (:source, :file, 'employee', 'synthetic')"
                ),
                identities,
            )
            connection.execute(
                text(
                    "INSERT INTO interview_inputs "
                    "(job_file_id, execution_id, source_id, command_id) "
                    "VALUES (:file, :execution, :source, :command)"
                ),
                identities | {"command": uuid4()},
            )
            for command_id, kind, request, result in (
                (
                    intent_command,
                    "consolidation_intent",
                    {"source_id": str(source_id)},
                    {"source_id": str(source_id), "message": "synthetic"},
                ),
                (
                    failure_command,
                    "batch_failure",
                    {"reason": "synthetic"},
                    {"reason": "synthetic", "formal_frontier": frontier},
                ),
            ):
                connection.execute(
                    text(
                        "INSERT INTO memory_operations "
                        "(job_file_id, execution_id, command_id, kind, "
                        "request_payload, result_payload) "
                        "VALUES (:file, :execution, :command, :kind, "
                        "CAST(:request AS jsonb), CAST(:result AS jsonb))"
                    ),
                    identities
                    | dict(
                        command=command_id,
                        kind=kind,
                        request=json.dumps(request),
                        result=json.dumps(result),
                    ),
                )

        def upgrade():
            with engine.begin() as connection:
                config = migration_config()
                config.attributes.update(connection=connection, schema=settings.schema)
                command.upgrade(config, "head")

        if type(frontier) is int:
            upgrade()
            with engine.connect() as connection:
                rows = connection.execute(
                    text(
                        "SELECT intent_source_id, failure_frontier, "
                        "request_payload, result_payload "
                        "FROM memory_operations ORDER BY kind"
                    )
                ).all()
                assert [tuple(row) for row in rows] == [
                    (None, 3, None, None),
                    (source_id, None, None, None),
                ]
        else:
            with pytest.raises(IntegrityError, match="Cannot migrate invalid Memory evidence"):
                upgrade()
            with engine.connect() as connection:
                assert (
                    connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
                    == "0031_jd_operation_result_index"
                )
                assert (
                    connection.execute(
                        text(
                            "SELECT count(*) FROM memory_operations "
                            "WHERE result_payload IS NOT NULL"
                        )
                    ).scalar_one()
                    == 2
                )
                assert (
                    connection.execute(
                        text(
                            "SELECT tgenabled FROM pg_trigger "
                            "WHERE tgrelid='memory_operations'::regclass "
                            "AND tgname='protect_memory_operations'"
                        )
                    ).scalar_one()
                    == "O"
                )
    finally:
        engine.dispose()
