"""JD 整合測試固定內容與新連線觀察；不加入產品相容介面。"""

from collections.abc import Callable
from uuid import UUID

from sqlalchemy import Engine, text

from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.queries import get_job_description
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_scenarios import JD, complete_root

CONTENT_TABLES = (
    "job_descriptions",
    "duties",
    "job_tasks",
    "task_outcomes",
    "task_requirements",
    "knowledge",
    "skills",
    "task_knowledge",
    "task_skills",
    "collaboration_entries",
    "job_conditions",
    "job_description_snapshots",
)


def factory(engine: Engine) -> Callable[[], SqlAlchemyJobDescriptionUnitOfWork]:
    sessions = create_session_factory(engine)
    return lambda: SqlAlchemyJobDescriptionUnitOfWork(sessions)


def seed_root(
    engine: Engine, workspace_id: UUID, *, root: JobDescription | None = None
) -> JobDescriptionResult:
    with factory(engine)() as unit:
        unit.job_descriptions.add(
            root if root is not None else complete_root(workspace_id=workspace_id)
        )
        unit.commit()
    return read_current(
        engine,
        workspace_id=workspace_id,
        job_description_id=root.id if root is not None else JD,
    )


def read_current(
    engine: Engine, *, workspace_id: UUID, job_description_id: UUID = JD
) -> JobDescriptionResult:
    return get_job_description(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        queries=SqlAlchemyJobDescriptionQueries(engine),
    )


def content_rows(
    engine: Engine, *, tables: tuple[str, ...] = CONTENT_TABLES
) -> dict[str, tuple[str, ...]]:
    """固定名單的目前內容與完整快照，供失敗前後獨立 SQL 比對。"""
    with engine.connect() as connection:
        result = {}
        for table in tables:
            projection = "to_jsonb(saved)"
            result[table] = tuple(
                sorted(
                    str(row[0])
                    for row in connection.execute(
                        text(f"SELECT ({projection})::text FROM {table} AS saved")
                    )
                )
            )
        return result
