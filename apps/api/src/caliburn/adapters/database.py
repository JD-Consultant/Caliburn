"""Own engines and short sessions, not feature SQL or business decisions."""

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from caliburn.adapters.database_settings import DatabaseSettings


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
