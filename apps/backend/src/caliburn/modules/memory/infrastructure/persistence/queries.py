"""不啟動 Agent，讀取同一資料庫視圖中的目前稿、固定版或來源。"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from caliburn.modules.memory.application.errors import (
    MemoryQueryError,
    WorkspaceNotFoundError,
)
from caliburn.modules.memory.application.results import (
    MemoryInterviewMessage,
)
from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION, MemorySnapshot
from caliburn.modules.memory.domain.work_memory import WorkMemory
from caliburn.modules.memory.infrastructure.persistence.interview_sources import (
    SqlAlchemyInterviewSourceReader,
)
from caliburn.modules.memory.infrastructure.persistence.repository import (
    read_current,
    read_snapshot,
)
from caliburn.modules.workspace.infrastructure.persistence.public_queries import (
    select_workspace_id,
)


class SqlAlchemyMemoryQueries:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_current(self, *, workspace_id: UUID) -> WorkMemory:
        with self._view(workspace_id) as session:
            return read_current(session, workspace_id=workspace_id, lock=False) or (
                WorkMemory.create(workspace_id=workspace_id)
            )

    def get_published(
        self, *, workspace_id: UUID, published_version: int | None
    ) -> MemorySnapshot | None:
        if published_version is not None and (
            type(published_version) is not int
            or not 1 <= published_version <= MAX_MEMORY_VERSION
        ):
            raise ValueError("Memory 發布版號須為可精確表示的正整數")
        with self._view(workspace_id) as session:
            if published_version is None:
                return None
            return read_snapshot(
                session, workspace_id=workspace_id, version=published_version
            )

    def list_analysis_sources(
        self, *, workspace_id: UUID, analysis_id: UUID
    ) -> tuple[MemoryInterviewMessage, ...]:
        with self._view(workspace_id) as session:
            memory = read_current(session, workspace_id=workspace_id, lock=False) or (
                WorkMemory.create(workspace_id=workspace_id)
            )
            analysis = memory.require_analysis(analysis_id=analysis_id)
            return SqlAlchemyInterviewSourceReader(session).list_window(
                analysis.source_window
            )

    @contextmanager
    def _view(self, workspace_id: UUID) -> Iterator[Session]:
        try:
            with Session(self._engine, autobegin=False) as session, session.begin():
                session.connection(
                    execution_options={"isolation_level": "REPEATABLE READ"}
                )
                if (
                    session.scalar(select_workspace_id(workspace_id=workspace_id))
                    is None
                ):
                    raise WorkspaceNotFoundError("Workspace 不存在")
                yield session
        except SQLAlchemyError as error:
            raise MemoryQueryError("Memory 查詢或資源釋放失敗") from error
