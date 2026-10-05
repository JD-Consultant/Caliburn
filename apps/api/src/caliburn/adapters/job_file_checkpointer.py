"""Fence native checkpoint writes against whole-job-file deletion."""

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection


class JobFilePostgresSaver(AsyncPostgresSaver):
    """Borrow the official connection/codec; add only a per-file write fence.

    A native exit task can be cancelled while its submitted saver keeps running.
    File identity, rather than completion of that carrier, is the final guard.
    The job row's key-share lock outlives the actual official write, including
    caller cancellation. No model/network request holds this short transaction.
    """

    def __init__(self, native: AsyncPostgresSaver) -> None:
        if not isinstance(native.conn, AsyncConnection) or native.pipe is not None:
            raise ValueError("Job-file checkpoints require the App's single native connection")
        super().__init__(native.conn, native.pipe, native.serde)
        self._native = native
        self._connection = native.conn

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        native_put = self._native.aput
        return await self._save_for_job_file(
            config, lambda: native_put(config, checkpoint, metadata, new_versions)
        )

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, object]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        native_put = self._native.aput_writes
        await self._save_for_job_file(
            config, lambda: native_put(config, writes, task_id, task_path)
        )

    async def _save_for_job_file[T](
        self, config: RunnableConfig, save: Callable[[], Awaitable[T]]
    ) -> T:
        thread_id = config.get("configurable", {}).get("thread_id")
        if not isinstance(thread_id, str) or ":" not in thread_id:
            raise ValueError("A checkpoint needs the App's job-file thread identity")
        job_file_id = UUID(thread_id.split(":", 1)[0])

        async def locked_save() -> T:
            # Use the official writer's very same connection: losing it rolls
            # back both the file fence and checkpoint write, not just the fence.
            async with self.lock, self._connection.transaction():
                async with self._connection.cursor() as cursor:
                    await cursor.execute(
                        "SELECT 1 FROM job_files WHERE job_file_id=%s FOR KEY SHARE",
                        (job_file_id,),
                    )
                    if await cursor.fetchone() is None:
                        raise LookupError("Checkpoint job file no longer exists")
                return await save()

        task = asyncio.create_task(locked_save())
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            # A key-share lock cannot leave while the borrowed connection's
            # save is still executing. Repeated cancellation grants no shortcut.
            while not task.done():
                try:
                    await asyncio.wait((task,))
                except asyncio.CancelledError:
                    continue
            if not task.cancelled():
                task.exception()
            raise
