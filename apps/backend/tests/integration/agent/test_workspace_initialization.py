"""正式 Host 原子建立 Workspace、空 JD 及唯一 App 開場，不啟動模型。"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from uuid import UUID

import httpx2
import pytest
from sqlalchemy import Engine, text

from caliburn.bundles.consultant import OPENING_TEXT
from caliburn.host.app import build_app
from tests.integration.agent.http_support import api_app
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION


@asynccontextmanager
async def initialization_client(
    engine: Engine, checkpoint_conninfo: str, *, agent_enabled: bool
) -> AsyncIterator[httpx2.AsyncClient]:
    def reject_model(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("Workspace creation must not call the model")

    async with AsyncExitStack() as stack:
        if agent_enabled:
            app = await stack.enter_async_context(
                api_app(engine, checkpoint_conninfo, httpx2.MockTransport(reject_model))
            )
        else:
            app = build_app(
                reference_configuration=HOST_REFERENCE_CONFIGURATION,
                database_url=engine.url.render_as_string(hide_password=False),
            )
            await stack.enter_async_context(app.router.lifespan_context(app))
        client = await stack.enter_async_context(
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://testserver"
            )
        )
        yield client


@pytest.mark.parametrize("agent_enabled", [True, False])
def test_workspace_creation_records_opening_and_empty_jd_without_agent_turn(
    pg_engine: Engine, checkpoint_conninfo: str, agent_enabled: bool
) -> None:
    async def run() -> None:
        async with initialization_client(
            pg_engine, checkpoint_conninfo, agent_enabled=agent_enabled
        ) as client:
            created = await client.post(
                "/workspaces", json={"interviewee_name": "Synthetic opening"}
            )
            assert created.status_code == 201, created.text
            workspace_id = created.json()["workspace_id"]
            path = f"/workspaces/{workspace_id}"
            transcript = await client.get(path + "/interview/messages")
            assert transcript.status_code == 200, transcript.text
            messages = transcript.json()
            assert len(messages) == 1
            assert messages[0]["speaker"] == "app"
            assert messages[0]["kind"] == "text"
            assert messages[0]["text"] == OPENING_TEXT
            assert messages[0]["reply_to_message_id"] is None
            jd = await client.get(path + "/job-description")
            assert jd.status_code == 200, jd.text
            assert jd.json()["workspace_id"] == workspace_id
            assert jd.json()["version"] == 1
            assert jd.json()["job_title"] is None
            assert jd.json()["purpose"] is None
            assert jd.json()["duties"] == []
            assert jd.json()["tasks"] == []
            turns = await client.get(path + "/agent/turns")
            if agent_enabled:
                assert turns.status_code == 200, turns.text
                assert turns.json() == []
            else:
                assert turns.status_code == 503, turns.text
            assert (await client.get(path + "/interview/messages")).json() == messages

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("agent_enabled", [True, False])
@pytest.mark.parametrize(
    ("table", "deferred"),
    [
        pytest.param("job_description_snapshots", False, id="jd-snapshot"),
        pytest.param("interview_messages", False, id="opening"),
        pytest.param("interview_messages", True, id="outer-commit"),
    ],
)
def test_initialization_failure_rolls_back_the_whole_workspace_and_allows_retry(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    agent_enabled: bool,
    table: str,
    deferred: bool,
) -> None:
    async def run() -> None:
        async with initialization_client(
            pg_engine, checkpoint_conninfo, agent_enabled=agent_enabled
        ) as client:
            existing = await client.post(
                "/workspaces", json={"interviewee_name": "Existing workspace"}
            )
            assert existing.status_code == 201, existing.text
            existing_path = existing.headers["Location"]
            existing_jd = (await client.get(existing_path + "/job-description")).json()
            existing_messages = (
                await client.get(existing_path + "/interview/messages")
            ).json()
            # 真 DB 故障：延後 trigger 僅在外層 COMMIT 執行，未偽裝 Session 提交。
            with pg_engine.begin() as connection:
                connection.execute(
                    text("""
                    CREATE FUNCTION reject_initialization() RETURNS trigger
                    LANGUAGE plpgsql AS $$ BEGIN
                        RAISE EXCEPTION 'Synthetic initialization failure';
                    END $$
                    """)
                )
                timing = "DEFERRABLE INITIALLY DEFERRED" if deferred else ""
                connection.execute(
                    text(
                        f"CREATE CONSTRAINT TRIGGER reject_initialization "
                        f"AFTER INSERT ON {table} {timing} FOR EACH ROW "
                        "EXECUTE FUNCTION reject_initialization()"
                    )
                )

            failed = await client.post(
                "/workspaces", json={"interviewee_name": "Must roll back"}
            )
            assert failed.status_code == 500, failed.text
            assert failed.json() == {"detail": {"code": "internal_error"}}
            listed = (await client.get("/workspaces")).json()
            assert listed["items"] == [existing.json()]
            assert (
                await client.get(existing_path + "/job-description")
            ).json() == existing_jd
            assert (
                await client.get(existing_path + "/interview/messages")
            ).json() == existing_messages

            with pg_engine.begin() as connection:
                connection.execute(
                    text(f"DROP TRIGGER reject_initialization ON {table}")
                )
            retried = await client.post(
                "/workspaces", json={"interviewee_name": "Successful retry"}
            )
            assert retried.status_code == 201, retried.text
            path = retried.headers["Location"]
            assert (await client.get(path + "/job-description")).json()["version"] == 1
            messages = (await client.get(path + "/interview/messages")).json()
            assert len(messages) == 1
            assert messages[0]["text"] == OPENING_TEXT

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("agent_enabled", [True, False])
def test_existing_standalone_workspace_is_not_initialized_by_startup_or_reads(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    agent_enabled: bool,
) -> None:
    async def run() -> None:
        async with initialization_client(
            pg_engine, checkpoint_conninfo, agent_enabled=agent_enabled
        ) as client:
            path = f"/workspaces/{jd_workspace_id}"
            for _ in range(2):
                assert (await client.get(path)).status_code == 200
                assert (await client.get(path + "/job-description")).status_code == 404
                assert (await client.get(path + "/interview/messages")).json() == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
