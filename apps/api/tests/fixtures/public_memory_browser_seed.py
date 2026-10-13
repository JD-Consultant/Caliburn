"""Create synthetic browser evidence in a new namespace of an explicit local _test DB.

No model, app database, deletion, or real B completion is involved. Memory publications
use the owner-only fixture; this script tests human browsing, not analyst execution.
"""

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

import psycopg
from alembic import command
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import create_engine

from caliburn.adapters.database import migration_config
from caliburn.adapters.database_settings import require_isolated_test_database
from caliburn.bootstrap import create_app
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews import queries
from caliburn.features.work_memory.candidates import CreateMemoryObject, ReviseMemoryObject
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings, Settings
from caliburn.transport.http.interview_inputs import get_consultant_dispatch
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.integration.test_consultant_completion import complete, start_turn


def main() -> None:
    dsn = os.environ["CALIBURN_TEST_DATABASE_URL"]
    require_isolated_test_database(dsn, environment=os.environ)
    schema = "browser_public_" + uuid4().hex
    settings = DatabaseSettings(url=dsn, schema=schema)
    with psycopg.connect(dsn, autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            config = migration_config()
            config.attributes.update(connection=connection, schema=schema)
            command.upgrade(config, "head")
    finally:
        engine.dispose()
    app = create_app(Settings(database=settings))
    app.dependency_overrides[get_consultant_dispatch] = lambda: lambda scope: None
    with TestClient(
        app,
        base_url="http://127.0.0.1:8100",
        headers={"Origin": "http://127.0.0.1:8100"},
        backend_options={"loop_factory": asyncio.SelectorEventLoop},
    ) as client:
        first = start_turn(client)
        complete(client, first)
        file_id = first.writer.scope.job_file_id

        async def publish(turn, previous=None):
            sessions = client.app.state.database.sessions
            async with sessions.begin() as session:
                scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
                source = await queries.read_execution_input(
                    session, job_file_id=file_id, execution_id=turn.writer.scope.execution_id
                )
                assert source is not None
            flow = MemoryCandidateWorkflow(sessions)
            initial = await flow.start(writer, source.source_id)
            assert initial is not None
            if previous is None:
                situation = await flow.edit(
                    writer,
                    CreateMemoryObject(
                        uuid4(),
                        initial,
                        MemoryLayer.WORK_SITUATION,
                        MemoryContent(
                            "合成：每月盤點", "核對庫存", "## 工作情境\n\n每月核對實物與帳目。"
                        ),
                        frozenset({source.source_id}),
                    ),
                )
            else:
                situation = await flow.edit(
                    writer,
                    ReviseMemoryObject(
                        uuid4(),
                        initial,
                        MemoryLayer.WORK_SITUATION,
                        previous,
                        MemoryContentChanges(
                            title="合成：每季盤點", body="## 工作情境\n\n每季核對實物，並追查差異。"
                        ),
                    ),
                )
            b2 = await flow.handoff(writer, situation.position, uuid4())
            if previous is None:
                understanding = await flow.edit(
                    writer,
                    CreateMemoryObject(
                        uuid4(),
                        b2,
                        MemoryLayer.WORK_UNDERSTANDING,
                        MemoryContent("合成：庫存管理", "盤點與回報", "依約定範圍盤點並回報異常。"),
                        frozenset({situation.object_id}),
                    ),
                )
                b2 = understanding.position
            snapshot = await publish_memory_owner_fixture(sessions, writer, b2, uuid4())
            return snapshot, situation.object_id

        old, object_id = client.portal.call(publish, first)
        second = start_turn(client, file_id=file_id)
        complete(client, second)
        latest, _ = client.portal.call(publish, second, object_id)
        # Exercise the public reader before returning a manifest; the seed is usable.
        response = client.get(f"/api/job-files/{file_id}/memory")
        response.raise_for_status()
        assert response.json()["snapshot_id"] == str(latest.snapshot_id)
        assert (
            client.get(
                f"/api/job-files/{file_id}/memory/{old.snapshot_id}/objects/{object_id}"
            ).json()["title"]
            == "合成：每月盤點"
        )
        manifest = {
            "schema": schema,
            "job_file_id": str(file_id),
            "old_snapshot_id": str(old.snapshot_id),
            "snapshot_id": str(latest.snapshot_id),
            "object_id": str(object_id),
        }
    target = Path(__file__).resolve().parents[4] / ".tmp/memory-refactor/public-memory-browser.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))


if __name__ == "__main__":
    main()
