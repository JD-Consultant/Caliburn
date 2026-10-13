"""Own engines and short sessions, not feature SQL or business decisions."""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from functools import wraps

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from tenacity import (
    AsyncRetrying,
    RetryCallState,
    retry_if_exception,
    stop_after_attempt,
    wait_random_exponential,
)

from caliburn.adapters.checkpoint_failures import is_transient_checkpoint_failure
from caliburn.adapters.database_settings import DatabaseSettings

_LOG = logging.getLogger(__name__)


def is_transient_database_failure(error: BaseException) -> bool:
    """只解開直接 SQLAlchemy driver 原因；資格與原操作由呼叫者核對。"""
    return isinstance(error, DBAPIError) and is_transient_checkpoint_failure(error.orig)


def retry_database_operation[**P, T](
    operation: Callable[P, Awaitable[T]],
) -> Callable[P, Awaitable[T]]:
    """限純 DB 原操作以新 session 重入；不得包 HTTP、Graph 或準備工具。"""

    def before_sleep(retry_state: RetryCallState) -> None:
        error = retry_state.outcome.exception() if retry_state.outcome is not None else None
        if isinstance(error, DBAPIError):
            _LOG.warning(
                "database.operation_retry",
                extra={
                    "operation": operation.__qualname__,
                    "retry_attempt": retry_state.attempt_number,
                    "failure_kind": type(error.orig).__name__,
                },
            )

    @wraps(operation)
    async def recover(*args: P.args, **kwargs: P.kwargs) -> T:
        async for attempt in AsyncRetrying(
            retry=retry_if_exception(is_transient_database_failure),
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=0.25, max=1.0),
            reraise=True,
            before_sleep=before_sleep,
        ):
            with attempt:
                return await operation(*args, **kwargs)
        raise RuntimeError("Database recovery ended without an outcome")

    return recover


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class DatabaseSchemaError(RuntimeError):
    """The selected target namespace has not reached the required migration head."""


@asynccontextmanager
async def consistent_read_session(
    sessions: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    """Pin multi-query projections before their first SELECT; release before CPU or I/O."""
    async with sessions.begin() as session:
        await session.connection(
            execution_options={
                "isolation_level": "REPEATABLE READ",
                "postgresql_readonly": True,
            }
        )
        yield session


def migration_config() -> Config:
    config = Config()
    config.set_main_option("script_location", "caliburn:migrations")
    return config


class Database:
    def __init__(self, settings: DatabaseSettings) -> None:
        self.settings = settings
        self.engine = create_async_engine(
            settings.sqlalchemy_url,
            pool_pre_ping=True,
            hide_parameters=True,
            connect_args={"options": f"-c search_path={settings.schema}"},
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def verify_schema(self) -> None:
        expected = set(ScriptDirectory.from_config(migration_config()).get_heads())
        async with self.engine.connect() as connection:
            actual = await connection.run_sync(
                lambda sync_connection: set(
                    MigrationContext.configure(
                        sync_connection,
                        opts={"version_table_schema": self.settings.schema},
                    ).get_current_heads()
                )
            )
        if actual != expected:
            raise DatabaseSchemaError("Run the target database migrations before starting the app")

    async def close(self) -> None:
        await self.engine.dispose()
