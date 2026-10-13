"""A cold process replays B1's committed original after the batch has entered B2."""

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidate_operations import position_fields
from caliburn.features.work_memory.candidates import CreateMemoryObject
from caliburn.features.work_memory.models import MemoryContent
from caliburn.settings import DatabaseSettings
from tests.integration.test_memory_candidates import SITUATION, execute, start
from tests.integration.test_memory_candidates import source as source

pytestmark = pytest.mark.postgres


def test_cold_memory_receipt_reentry_keeps_original_b1_result_and_b2_head(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    source,
) -> None:
    async def scenario(database):
        workflow, writer, initial = await start(database, source)
        intent = {
            "position": position_fields(initial),
            "command_id": str(uuid4()),
            "content": {"title": "原盤點", "description": "合成描述", "body": "原正文"},
            "reference_ids": [str(source[1])],
        }

        def worker(mode):
            return subprocess.run(
                [
                    sys.executable,
                    "-B",
                    "-m",
                    "tests.fixtures.memory_receipt_worker",
                    mode,
                    database_settings.schema,
                    str(writer.writer_id),
                ],
                cwd=Path(__file__).resolve().parents[2],
                input=json.dumps(intent),
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=30,
            )

        crashed = worker("commit_then_exit")
        assert crashed.returncode == 19, crashed.stderr
        original = json.loads(crashed.stdout)
        async with database.sessions() as session:
            current = candidate_queries.batch_position(
                await candidate_queries.require_stage(session, initial)
            )
        changed = await workflow.edit(
            writer,
            CreateMemoryObject(uuid4(), current, SITUATION, MemoryContent("後續", "描述", "正文")),
        )
        b2 = await workflow.handoff(writer, changed.position, uuid4())

        def counts():
            return database_connection.execute(
                "SELECT (SELECT count(*) FROM memory_objects WHERE job_file_id=%s),"
                "(SELECT count(*) FROM memory_operations WHERE job_file_id=%s)",
                (source[0], source[0]),
            ).fetchone()

        before = counts()
        replayed = worker("replay")
        assert replayed.returncode == 0, replayed.stderr
        assert json.loads(replayed.stdout) == original
        assert counts() == before == (2, 4)
        # B2 retains its own stage and current member set; reentry must not rewind to B1.
        async with database.sessions() as session:
            assert await candidate_queries.require_stage(session, b2, exact_position=True)
        assert {
            item.title for item in await workflow.read_map(writer.scope, stage=b2, layer=SITUATION)
        } == {"原盤點", "後續"}

    execute(database_settings, scenario)
