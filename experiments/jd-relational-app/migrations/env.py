"""Explicit migration entry: offline SQL, or a caller-owned PostgreSQL connection."""

from alembic import context
from sqlalchemy.engine import Connection

from jd_relational.storage.schema import JD_TABLE_NAMES, metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Future autogeneration must not propose dropping another owner's tables.
    return type_ != "table" or name in JD_TABLE_NAMES


def run_migrations_offline():
    context.configure(
        dialect_name="postgresql",
        target_metadata=metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table="alembic_version",
        include_object=include_object,
        include_schemas=False,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connection = context.config.attributes.get("connection")
    if not isinstance(connection, Connection) or connection.dialect.name != "postgresql":
        raise RuntimeError("Migration requires an explicit PostgreSQL Connection in Config.attributes['connection'].")
    context.configure(connection=connection, target_metadata=metadata,
                      version_table="alembic_version", include_object=include_object, include_schemas=False)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
