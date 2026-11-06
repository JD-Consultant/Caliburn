"""正式 Server 的事件迴圈可啟動 Agent 並讀取真 PostgreSQL。"""

import asyncio

import httpx2
from sqlalchemy import Engine

from caliburn.server import create_server
from tests.integration.agent.http_support import api_client


def test_server_loop_starts_agent_and_reads_postgres(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    def unexpected_model_call(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("啟動與查讀不應呼叫模型")

    async def run() -> None:
        async with api_client(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(unexpected_model_call)
        ) as client:
            workspace = await client.post(
                "/workspaces", json={"interviewee_name": "啟動測試"}
            )
            assert workspace.status_code == 201
            workspace_id = workspace.json()["workspace_id"]
            turns = await client.get(f"/workspaces/{workspace_id}/agent/turns")
            assert turns.status_code == 200
            assert turns.json() == []

    asyncio.run(run(), loop_factory=create_server().config.get_loop_factory())
