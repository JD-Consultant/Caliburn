"""One unpooled PG session owns local consultant supervision until all tasks exit."""

import asyncio
import errno
import os
import sys
from hashlib import sha256
from pathlib import Path
from tempfile import gettempdir

from psycopg import AsyncConnection

from caliburn.settings import DatabaseSettings


class ProcessLockUnavailableError(RuntimeError):
    """Another supervisor already holds this database/schema's admission lock."""


class ProcessLockLostError(RuntimeError):
    """The original session is gone; reconnecting cannot restore its ownership."""


class PostgresProcessLock:
    def __init__(self, settings: DatabaseSettings, *, timeout_seconds: float = 5.0) -> None:
        if not 0 < timeout_seconds <= 30:
            raise ValueError("Process lock timeout must be within (0, 30] seconds")
        self._settings = settings
        self._timeout = timeout_seconds
        self._key = int.from_bytes(
            sha256(f"caliburn:consultant-supervisor:{settings.schema}".encode()).digest()[:8],
            signed=True,
        )
        self._connection: AsyncConnection[tuple[object, ...]] | None = None
        # Same local account/temp directory is part of the single-host deployment.
        # Exclude host aliases/credentials: changing localhost to 127.0.0.1 must not
        # bypass the local fence. Same-named remote DBs are conservatively serialized.
        identity = f"{settings.sqlalchemy_url.database}:{settings.schema}".encode()
        self._local_path = Path(gettempdir()) / (
            f"caliburn-consultant-{sha256(identity).hexdigest()}.lock"
        )
        self._local_fd: int | None = None

    async def acquire(self) -> None:
        if self._connection is not None or self._local_fd is not None:
            raise RuntimeError("Process lock is already acquired")
        dsn = self._settings.sqlalchemy_url.set(drivername="postgresql").render_as_string(
            hide_password=False
        )
        connection: AsyncConnection[tuple[object, ...]] | None = None
        try:
            self._acquire_local()
            async with asyncio.timeout(self._timeout):
                connection = await AsyncConnection.connect(dsn, autocommit=True)
                cursor = await connection.execute("SELECT pg_try_advisory_lock(%s)", (self._key,))
                row = await cursor.fetchone()
                if row is None or row[0] is not True:
                    raise ProcessLockUnavailableError("Another consultant supervisor is running")
                self._connection = connection
        finally:
            if self._connection is None:
                try:
                    if connection is not None:
                        await connection.close()
                finally:
                    self._close_local()

    async def check(self) -> None:
        """Probe the same physical session; never reconnect or reacquire a lost lock."""
        connection = self._connection
        if connection is None or connection.closed:
            raise ProcessLockLostError("Consultant supervisor session is not held")
        async with asyncio.timeout(self._timeout):
            await connection.execute("SELECT 1")

    async def close(self) -> None:
        connection, self._connection = self._connection, None
        try:
            if connection is not None:
                # Never return a session holding an advisory lock to a pool.
                await connection.close()
        finally:
            self._close_local()

    def _acquire_local(self) -> None:
        descriptor = os.open(self._local_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            os.close(descriptor)
            if error.errno in (errno.EACCES, errno.EAGAIN, errno.EDEADLK):
                raise ProcessLockUnavailableError("Another local supervisor is running") from None
            raise
        self._local_fd = descriptor

    def _close_local(self) -> None:
        descriptor, self._local_fd = self._local_fd, None
        if descriptor is not None:
            os.close(descriptor)
        # Do not unlink: deleting/recreating a lock file permits two locked inodes.
