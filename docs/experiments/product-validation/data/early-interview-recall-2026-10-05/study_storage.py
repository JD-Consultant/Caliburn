"""Fresh research namespaces and read-only evidence export; no production lifecycle."""

from dataclasses import asdict
from pathlib import Path
from uuid import UUID

import psycopg
from alembic import command
from baseline_store import require_research_database
from caliburn.adapters.database import Database, migration_config
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.features.interviews.persistence import list_formal_interviews
from caliburn.features.job_description import queries, source_persistence, work_queries
from psycopg import sql
from sqlalchemy import create_engine
from study_manifest import save_new


def create_namespace(settings: DatabaseSettings) -> None:
    require_research_database(Database(settings))
    with psycopg.connect(settings.url, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(settings.schema)))
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(config, "head")
    finally:
        engine.dispose()


async def export_product(database: Database, file_id: UUID, path: Path) -> None:
    async with database.sessions() as session:
        profile = await queries.read_profile(session, file_id)
        work = await work_queries.read_work(session, file_id)
        references = await source_persistence.read_source_references(
            session, file_id, profile.revision_id
        )
        interviews = await list_formal_interviews(session, file_id)
    save_new(
        path,
        {
            "profile": asdict(profile),
            "work": asdict(work),
            "references": [asdict(reference) for reference in references],
            "interviews": [asdict(message) for message in interviews],
        },
    )
