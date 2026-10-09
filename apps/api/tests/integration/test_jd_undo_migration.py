"""0017 data is retained while 0018 enables a new kind in the existing JD journal."""

from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

from caliburn.adapters.database import migration_config
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


def test_0018_preserves_existing_revisions_and_operations(
    empty_database_settings: DatabaseSettings,
) -> None:
    settings = empty_database_settings
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    identities = {"file": uuid4(), "revision": uuid4(), "command": uuid4()}
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "0017_jd_source_references")
            connection.execute(
                text(
                    "INSERT INTO job_files(job_file_id, creation_command_id, initial_display_name, "
                    "display_name, employee_name) VALUES (:file, :command, '合成', '合成', '合成')"
                ),
                identities,
            )
            connection.execute(
                text(
                    "INSERT INTO jd_revisions(job_file_id, revision_id, job_title) "
                    "VALUES (:file, :revision, '既存職稱不可丟失')"
                ),
                identities,
            )
            connection.execute(
                text(
                    "INSERT INTO job_descriptions(job_file_id, initial_revision_id, "
                    "current_revision_id) "
                    "VALUES (:file, :revision, :revision)"
                ),
                identities,
            )
            insert = text(
                "INSERT INTO jd_operations(job_file_id, command_id, kind, expected_revision_id, "
                "result_revision_id, request_payload) "
                "VALUES (:file, :command, :kind, :revision, :revision, '{}'::jsonb)"
            )
            connection.execute(insert, {**identities, "kind": "revise_profile"})
            before = {
                table: connection.execute(text(f"SELECT * FROM {table}")).mappings().all()
                for table in ("job_files", "jd_revisions", "job_descriptions", "jd_operations")
            }
            with pytest.raises(IntegrityError):
                with connection.begin_nested():
                    connection.execute(
                        insert, {**identities, "command": uuid4(), "kind": "undo_completed_turn"}
                    )
            command.upgrade(config, "head")
            command.upgrade(config, "head")
            for table, rows in before.items():
                # 0030 moves creation identity into the independently retained receipt.
                if table == "job_files":
                    rows = [
                        {key: value for key, value in row.items() if key != "creation_command_id"}
                        for row in rows
                    ]
                columns = ", ".join(rows[0].keys())
                assert (
                    connection.execute(text(f"SELECT {columns} FROM {table}")).mappings().all()
                    == rows
                )
            assert connection.execute(
                text("SELECT command_id,result_file_id FROM job_file_creations")
            ).all() == [(identities["command"], identities["file"])]
            connection.execute(
                insert, {**identities, "command": uuid4(), "kind": "undo_completed_turn"}
            )
    finally:
        engine.dispose()
