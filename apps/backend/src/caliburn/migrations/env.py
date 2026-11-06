"""明確執行 schema 遷移；不從舊產品或預設帳密推導連線。"""

import os

from alembic import context
from sqlalchemy import Connection

from caliburn.modules.interview.infrastructure.persistence import (  # noqa: F401
    orm_models as interview_models,
)
from caliburn.modules.job_description.infrastructure.persistence import (  # noqa: F401
    citation_rows as job_description_citation_models,
)
from caliburn.modules.job_description.infrastructure.persistence import (  # noqa: F401
    orm_models as job_description_models,
)
from caliburn.modules.memory.infrastructure.persistence import (  # noqa: F401
    orm_models as memory_models,
)
from caliburn.modules.model_references import orm_models as model_reference_models  # noqa: F401
from caliburn.modules.plan.infrastructure.persistence import (  # noqa: F401
    orm_models as plan_models,
)
from caliburn.modules.workspace.infrastructure.persistence import (  # noqa: F401
    orm_models as workspace_models,
)
from caliburn.shared.infrastructure.persistence.database import create_database_engine
from caliburn.shared.infrastructure.persistence.orm_base import OrmBase

config = context.config
target_metadata = OrmBase.metadata


def database_url() -> str:
    url = os.environ.get("CALIBURN_REBUILD_DATABASE_URL")
    if not url:
        raise RuntimeError("CALIBURN_REBUILD_DATABASE_URL must be explicitly set")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connection = config.attributes.get("connection")
    if connection is not None:
        if not isinstance(connection, Connection):
            raise TypeError("Migration connection must be a SQLAlchemy Connection")
        run_migrations(connection)
        return

    engine = create_database_engine(database_url())
    try:
        with engine.connect() as connection:
            run_migrations(connection)
    finally:
        engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
