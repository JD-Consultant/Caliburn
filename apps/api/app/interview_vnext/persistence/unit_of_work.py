"""SQLAlchemy Unit of Work — the only commit owner for vNext persistence (§6.2).

One instance = one AsyncSession = one transaction = one asyncio task. Exit
without an explicit successful ``commit()`` always rolls back. Instances are
not re-enterable and must not be shared across tasks (AsyncSession is a
mutable, stateful object). Provider/exporter network calls never happen while
a UoW is open.
"""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .capture import DurableCaptureWriter
from .errors import PersistenceError
from .repositories import (
    SqlAlchemyArtifactRepository,
    SqlAlchemyAttemptRepository,
    SqlAlchemyCheckpointRepository,
    SqlAlchemyCommandRepository,
    SqlAlchemyRunRepository,
    SqlAlchemySessionRepository,
    translate_integrity_error,
)


class SqlAlchemyVNextUnitOfWork:
    """composition root 注入 ``async_sessionmaker``,不是長命 AsyncSession。"""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = session_factory
        self._session: AsyncSession | None = None
        self._entered = False
        self._committed = False

    async def __aenter__(self) -> "SqlAlchemyVNextUnitOfWork":
        if self._entered:
            raise RuntimeError("VNextUnitOfWork instances are not re-enterable")
        self._entered = True
        self._session = self._factory()
        self.sessions = SqlAlchemySessionRepository(self._session)
        self.artifacts = SqlAlchemyArtifactRepository(self._session)
        self.commands = SqlAlchemyCommandRepository(self._session)
        self.runs = SqlAlchemyRunRepository(self._session)
        self.checkpoints = SqlAlchemyCheckpointRepository(self._session)
        self.attempts = SqlAlchemyAttemptRepository(self._session)
        self.capture = DurableCaptureWriter(self._session, artifacts=self.artifacts,
                                            runs=self.runs, sessions=self.sessions)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        assert self._session is not None
        try:
            if exc_type is not None or not self._committed:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        assert self._session is not None
        try:
            await self._session.commit()
        except IntegrityError as exc:
            await self._session.rollback()
            stable = translate_integrity_error(exc)
            if stable is not None:
                raise stable from exc
            raise PersistenceError("transaction commit failed") from exc
        except Exception:
            await self._session.rollback()
            raise
        self._committed = True

    async def rollback(self) -> None:
        assert self._session is not None
        await self._session.rollback()
