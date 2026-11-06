"""來源 owner 的公開能力；Interview 查驗與 JD 保存共用交易。"""

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from caliburn.modules.interview.application.errors import InterviewDataError
from caliburn.modules.interview.infrastructure.persistence.public_queries import (
    interview_source_position,
    read_interview_sources,
)
from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceView,
)
from caliburn.modules.job_description.application.errors import (
    CitationSourceDataError,
    InvalidCitationSourceError,
    JobDescriptionPersistenceError,
    JobDescriptionQueryError,
)
from caliburn.modules.job_description.domain.models.citation import (
    InterviewReference,
    SourceReference,
)
from caliburn.modules.memory.application.errors import (
    MemoryDataError,
    MemoryQueryError,
    MemoryVersionNotFoundError,
)
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)

from .errors import translate_persistence_error


class SqlAlchemyCitationSources:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._memory = SqlAlchemyMemoryQueries(session.get_bind().engine)

    def require_available(self, *, source: SourceReference) -> None:
        try:
            self._require_available(source=source)
        except SQLAlchemyError as error:
            raise translate_persistence_error(
                error, commit_status="not_committed"
            ) from error
        except (MemoryQueryError, MemoryDataError, InterviewDataError) as error:
            raise JobDescriptionPersistenceError(
                commit_status="not_committed"
            ) from error

    def _require_available(self, *, source: SourceReference) -> None:
        if isinstance(source, InterviewReference):
            found = read_interview_sources(
                self._session,
                workspace_id=source.workspace_id,
                message_ids=frozenset((source.message_id,)),
                lock_turns=True,
            )
            if not found:
                raise InvalidCitationSourceError(
                    "訪談來源不存在、已撤回或不屬此 Workspace"
                )
        else:
            try:
                self.read(source=source)
            except CitationSourceDataError as error:
                raise InvalidCitationSourceError(
                    "Memory 來源不是此 Workspace 的已發布項目"
                ) from error

    def read(self, *, source: SourceReference) -> CitationSourceView:
        if isinstance(source, InterviewReference):
            found = read_interview_sources(
                self._session,
                workspace_id=source.workspace_id,
                message_ids=frozenset((source.message_id,)),
                lock_turns=False,
            )
            if found:
                return CitationSourceView(
                    source=source, availability="available", text=found[0].message.text
                )
            if (
                interview_source_position(
                    self._session,
                    workspace_id=source.workspace_id,
                    message_id=source.message_id,
                )
                is None
            ):
                raise CitationSourceDataError("固定訪談來源已遺失")
            return CitationSourceView(source=source, availability="unavailable")
        try:
            snapshot = self._memory.get_published(
                workspace_id=source.workspace_id,
                published_version=source.published_version,
            )
        except MemoryVersionNotFoundError as error:
            raise CitationSourceDataError("固定 Memory 發布版已遺失") from error
        item = (
            next((item for item in snapshot.items if item.id == source.item_id), None)
            if snapshot
            else None
        )
        if item is None:
            raise CitationSourceDataError("固定 Memory 項目已遺失")
        return CitationSourceView(
            source=source,
            availability="available",
            title=item.content.title,
            text=item.content.body,
            changed_version=item.changed_version,
            item_kind=item.kind,
        )


class SqlAlchemyCitationSourceQueries:
    """人工/工具獨立展開來源，不要求 Agent 或寫入 UoW。"""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def read(self, *, source: SourceReference) -> CitationSourceView:
        try:
            with Session(self._engine) as session, session.begin():
                session.connection(
                    execution_options={"isolation_level": "REPEATABLE READ"}
                )
                return SqlAlchemyCitationSources(session).read(source=source)
        except SQLAlchemyError as error:
            raise JobDescriptionQueryError("JD 引用來源查讀失敗") from error
