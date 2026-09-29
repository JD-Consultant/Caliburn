"""Migrate only an explicitly selected target PostgreSQL namespace."""

from alembic import context
from sqlalchemy import Connection, create_engine, pool, text
from sqlalchemy.schema import CreateSchema

from caliburn.adapters.database import Base
from caliburn.features.executions.budget_persistence import ExecutionBudgetRecord
from caliburn.features.executions.persistence import ExecutionRecord
from caliburn.features.interviews.persistence import (
    FormalInterviewRecord,
    InterviewInputRecord,
    InterviewReplyRecord,
    InterviewTextRecord,
)
from caliburn.features.job_description.candidate_persistence import JdCandidateRecord
from caliburn.features.job_description.persistence import JdRevisionRecord
from caliburn.features.job_files.persistence import JobFileRecord
from caliburn.features.work_memory.batch_persistence import MemoryBatchRecord
from caliburn.features.work_memory.position_persistence import MemoryPositionRecord
from caliburn.features.work_memory.revision_persistence import MemoryObjectRevisionRecord
from caliburn.settings import Settings

config = context.config
# Explicit imports register each owned table for autogenerate, not application startup.
target_metadata = Base.metadata
assert JobFileRecord.__table__.metadata is target_metadata
assert InterviewTextRecord.__table__.metadata is target_metadata
assert FormalInterviewRecord.__table__.metadata is target_metadata
assert InterviewInputRecord.__table__.metadata is target_metadata
assert InterviewReplyRecord.__table__.metadata is target_metadata
assert ExecutionRecord.__table__.metadata is target_metadata
assert ExecutionBudgetRecord.__table__.metadata is target_metadata
assert JdRevisionRecord.__table__.metadata is target_metadata
assert JdCandidateRecord.__table__.metadata is target_metadata
assert MemoryObjectRevisionRecord.__table__ is target_metadata.tables["memory_object_revisions"]
assert MemoryPositionRecord.__table__ is target_metadata.tables["memory_positions"]
assert MemoryBatchRecord.__table__ is target_metadata.tables["memory_batches"]


def migrate(connection: Connection, schema: str) -> None:
    if connection.scalar(text("SELECT current_schema()")) != schema:
        raise RuntimeError("Migration connection must select the configured target schema")
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    raise RuntimeError("Use an explicit target PostgreSQL connection for reviewed migrations")

connection = config.attributes.get("connection")
if connection is not None:
    migrate(connection, config.attributes["schema"])
else:
    settings = Settings.from_environment().database
    if settings is None:
        raise RuntimeError("Set CALIBURN_DATABASE_URL; legacy DATABASE_URL/.env is not used")
    engine = create_engine(
        settings.sqlalchemy_url,
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args={"options": f"-c search_path={settings.schema}"},
    )
    try:
        with engine.begin() as connection:
            connection.execute(CreateSchema(settings.schema, if_not_exists=True))
            migrate(connection, settings.schema)
    finally:
        engine.dispose()
