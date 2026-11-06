"""目前內容及歷史讀取；每次公開查詢使用獨立唯讀快照，無寫鎖。"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from caliburn.modules.job_description.application.content import (
    DutyResult,
    KnowledgeResult,
    SkillResult,
    TaskResult,
    TaskTextResult,
)
from caliburn.modules.job_description.application.errors import JobDescriptionQueryError
from caliburn.modules.job_description.application.history_types import (
    DEFAULT_HISTORY_PAGE_SIZE,
    HistoryPage,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    HistoricalJobDescription,
)
from caliburn.modules.job_description.application.query_results import (
    DutyQueryResult,
    KnowledgeQueryResult,
    SkillQueryResult,
    TaskQueryResult,
)
from caliburn.modules.job_description.domain.models.entry_name import EntryName

from .content_mapping import load_current_content
from .history_reader import SqlAlchemyJobDescriptionHistoryReader
from .orm_models import (
    DutyRow,
    JobDescriptionRow,
    JobTaskRow,
    KnowledgeRow,
    SkillRow,
    TaskKnowledgeRow,
    TaskOutcomeRow,
    TaskRequirementRow,
    TaskSkillRow,
)


class SqlAlchemyJobDescriptionQueries:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_job_description(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> JobDescriptionResult | None:
        with self._snapshot() as session:
            row = session.scalar(
                select(JobDescriptionRow).where(
                    JobDescriptionRow.workspace_id == workspace_id,
                    JobDescriptionRow.id == job_description_id,
                )
            )
            return _complete(session, row) if row is not None else None

    def find_job_description_by_workspace(
        self, *, workspace_id: UUID
    ) -> JobDescriptionResult | None:
        with self._snapshot() as session:
            row = session.scalar(
                select(JobDescriptionRow).where(
                    JobDescriptionRow.workspace_id == workspace_id
                )
            )
            return _complete(session, row) if row is not None else None

    def get_duty(
        self, *, workspace_id: UUID, job_description_id: UUID, duty_id: UUID
    ) -> DutyQueryResult | None:
        with self._snapshot() as session:
            version = _version(session, workspace_id, job_description_id)
            if version is None:
                return None
            row = session.scalar(
                select(DutyRow).where(
                    DutyRow.id == duty_id,
                    DutyRow.job_description_id == job_description_id,
                )
            )
            if row is None:
                return None
            return DutyQueryResult(
                job_description_id=job_description_id,
                jd_version=version,
                duty=DutyResult(
                    id=row.id, name=EntryName(value=row.name).value, scope=row.scope
                ),
            )

    def get_knowledge(
        self, *, workspace_id: UUID, job_description_id: UUID, knowledge_id: UUID
    ) -> KnowledgeQueryResult | None:
        with self._snapshot() as session:
            version = _version(session, workspace_id, job_description_id)
            if version is None:
                return None
            row = session.scalar(
                select(KnowledgeRow).where(
                    KnowledgeRow.id == knowledge_id,
                    KnowledgeRow.job_description_id == job_description_id,
                )
            )
            if row is None:
                return None
            return KnowledgeQueryResult(
                job_description_id=job_description_id,
                jd_version=version,
                knowledge=KnowledgeResult(
                    id=row.id,
                    name=EntryName(value=row.name).value,
                    description=row.description,
                ),
            )

    def get_skill(
        self, *, workspace_id: UUID, job_description_id: UUID, skill_id: UUID
    ) -> SkillQueryResult | None:
        with self._snapshot() as session:
            version = _version(session, workspace_id, job_description_id)
            if version is None:
                return None
            row = session.scalar(
                select(SkillRow).where(
                    SkillRow.id == skill_id,
                    SkillRow.job_description_id == job_description_id,
                )
            )
            if row is None:
                return None
            return SkillQueryResult(
                job_description_id=job_description_id,
                jd_version=version,
                skill=SkillResult(
                    id=row.id,
                    name=EntryName(value=row.name).value,
                    description=row.description,
                ),
            )

    def get_task(
        self, *, workspace_id: UUID, job_description_id: UUID, task_id: UUID
    ) -> TaskQueryResult | None:
        with self._snapshot() as session:
            version = _version(session, workspace_id, job_description_id)
            if version is None:
                return None
            row = session.scalar(
                select(JobTaskRow).where(
                    JobTaskRow.id == task_id,
                    JobTaskRow.job_description_id == job_description_id,
                )
            )
            if row is None:
                return None
            outcomes = tuple(
                TaskTextResult(id=x.id, text=x.text)
                for x in session.scalars(
                    select(TaskOutcomeRow)
                    .where(TaskOutcomeRow.task_id == task_id)
                    .order_by(TaskOutcomeRow.position)
                )
            )
            requirements = tuple(
                TaskTextResult(id=x.id, text=x.text)
                for x in session.scalars(
                    select(TaskRequirementRow)
                    .where(TaskRequirementRow.task_id == task_id)
                    .order_by(TaskRequirementRow.position)
                )
            )
            knowledge = tuple(
                session.scalars(
                    select(TaskKnowledgeRow.knowledge_id)
                    .where(TaskKnowledgeRow.task_id == task_id)
                    .order_by(TaskKnowledgeRow.position)
                )
            )
            skills = tuple(
                session.scalars(
                    select(TaskSkillRow.skill_id)
                    .where(TaskSkillRow.task_id == task_id)
                    .order_by(TaskSkillRow.position)
                )
            )
            return TaskQueryResult(
                job_description_id=job_description_id,
                jd_version=version,
                task=TaskResult(
                    id=row.id,
                    duty_id=row.duty_id,
                    name=EntryName(value=row.name).value,
                    description=row.description,
                    competency_level=row.competency_level,
                    outcomes=outcomes,
                    requirements=requirements,
                    knowledge_ids=knowledge,
                    skill_ids=skills,
                ),
            )

    def list_history(
        self,
        *,
        workspace_id: UUID,
        job_description_id: UUID,
        page_size: int = DEFAULT_HISTORY_PAGE_SIZE,
        page_token: str | None = None,
        correlation_id: str | None = None,
        reverts_correlation_id: str | None = None,
    ) -> HistoryPage:
        with self._snapshot() as session:
            return SqlAlchemyJobDescriptionHistoryReader(session).list(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                page_size=page_size,
                page_token=page_token,
                correlation_id=correlation_id,
                reverts_correlation_id=reverts_correlation_id,
            )

    def get_history(
        self, *, workspace_id: UUID, job_description_id: UUID, version: int
    ) -> HistoricalJobDescription:
        with self._snapshot() as session:
            return SqlAlchemyJobDescriptionHistoryReader(session).get(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                version=version,
            )

    @contextmanager
    def _snapshot(self) -> Iterator[Session]:
        try:
            with self._engine.connect() as connection:
                connection.execution_options(
                    isolation_level="REPEATABLE READ", postgresql_readonly=True
                )
                with Session(bind=connection) as session, session.begin():
                    yield session
        except SQLAlchemyError as error:
            raise JobDescriptionQueryError("JD 查詢失敗") from error


def _version(session: Session, workspace_id: UUID, jd_id: UUID) -> int | None:
    return session.scalar(
        select(JobDescriptionRow.version).where(
            JobDescriptionRow.workspace_id == workspace_id,
            JobDescriptionRow.id == jd_id,
        )
    )


def _complete(session: Session, row: JobDescriptionRow) -> JobDescriptionResult:
    content = load_current_content(session, row).to_domain()
    return JobDescriptionResult.from_job_description(content, version=row.version)
