import sys
import asyncio
from logging.config import fileConfig

from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from app.config import settings
from app.models.base import Base
import app.models  # noqa: F401  確保所有 model 被 import 進 metadata
# vNext persistence rows(V2-B):只註冊 metadata 供 autogenerate diff 輔助;
# production route 不接線(composition root 不 import)。
import app.interview_vnext.persistence.models  # noqa: F401
# UI-independent canonical Authoring Core (migration 0011).  Import only for
# metadata registration; production composition remains unwired.
import app.job_authoring.postgres_models  # noqa: F401
# Greenfield local Current State persistence (migration 0012). Adapter metadata
# registration only; no composition with old authoring/vNext paths.
import app.adapters.job_analysis_postgres.models  # noqa: F401

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata,
                      literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = create_async_engine(settings.database_url, future=True)
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
