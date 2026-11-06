"""完成輪旅程的 HTTP 前置及明示的合成保存點損壞注入。"""

from collections.abc import Mapping
from typing import cast
from uuid import UUID

import httpx2
from langgraph.checkpoint.base import (
    ChannelVersions,
    CheckpointMetadata,
    copy_checkpoint,
)

from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)


async def create_workspace_jd(
    client: httpx2.AsyncClient,
) -> tuple[UUID, JobDescriptionResult]:
    created = await client.post("/workspaces", json={"interviewee_name": "完成輪差異"})
    assert created.status_code == 201, created.text
    workspace_id = UUID(created.json()["workspace_id"])
    initial = await client.get(f"/workspaces/{workspace_id}/job-description")
    assert initial.status_code == 200, initial.text
    return workspace_id, JobDescriptionResult.model_validate_json(initial.content)


async def checkpoint_ids(conninfo: str, *, turn_id: UUID) -> list[str]:
    async with open_postgres_checkpointer(conninfo) as saver:
        return [
            saved.checkpoint["id"]
            async for saved in saver.alist(None, filter={"turn_id": str(turn_id)})
        ]


async def append_checkpoint_fault(
    conninfo: str,
    *,
    turn_id: UUID,
    values: Mapping[str, object],
    input_turn_id: UUID | None = None,
) -> None:
    """僅在本例專用 schema 追加故障快照，保留較舊正常完成點驗拒絕 fallback。"""
    async with open_postgres_checkpointer(conninfo) as saver:
        history = [
            saved
            async for saved in saver.alist(
                None, filter={"turn_id": str(turn_id)}, limit=1
            )
        ]
        assert len(history) == 1
        saved = history[0]
        checkpoint = copy_checkpoint(saved.checkpoint)
        # 沒有後續執行，只需在本例最新 UUID 之後追加一個唯一保存點。
        checkpoint["id"] = str(UUID(int=UUID(checkpoint["id"]).int + 1))
        versions: ChannelVersions = {}
        for channel, value in values.items():
            checkpoint["channel_values"][channel] = value
            version = checkpoint["channel_versions"].get(channel)
            assert version is None or isinstance(version, str)
            versions[channel] = saver.get_next_version(version, None)
        checkpoint["channel_versions"].update(versions)
        metadata = {**saved.metadata, "step": saved.metadata["step"] + 1}
        if input_turn_id is not None:
            metadata["source"] = "input"
            metadata["turn_id"] = str(input_turn_id)
        # 官方 metadata 允許額外欄位；TypedDict 只列出框架自有欄位。
        await saver.aput(
            saved.config, checkpoint, cast(CheckpointMetadata, metadata), versions
        )
