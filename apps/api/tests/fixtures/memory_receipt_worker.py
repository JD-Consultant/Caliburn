"""Cold Memory owner replay after commit and physical process loss."""

import asyncio
import json
import os
import sys
from uuid import UUID

from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import require_isolated_test_database
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.work_memory.candidate_operations import position_fields
from caliburn.features.work_memory.candidates import CreateMemoryObject, MemoryBatchPosition
from caliburn.features.work_memory.models import MemoryContent
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import DatabaseSettings
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow


async def main() -> None:
    mode, schema, writer_id = sys.argv[1:]
    dsn = os.environ["CALIBURN_TEST_DATABASE_URL"]
    require_isolated_test_database(dsn, environment=os.environ)
    database = Database(DatabaseSettings(url=dsn, schema=schema))
    payload = json.loads(sys.stdin.read())
    saved = payload["position"]
    stage = MemoryBatchPosition(
        UUID(saved["job_file_id"]),
        UUID(saved["execution_id"]),
        UUID(saved["stage_id"]),
        MemoryLayer(saved["phase"]),
        UUID(saved["position_id"]),
    )
    writer = ExecutionWriter(
        ExecutionScope(stage.job_file_id, stage.execution_id, ExecutionKind.MEMORY_BATCH),
        UUID(writer_id),
    )
    result = await MemoryCandidateWorkflow(database.sessions).edit(
        writer,
        CreateMemoryObject(
            UUID(payload["command_id"]),
            stage,
            stage.phase,
            MemoryContent(**payload["content"]),
            frozenset(UUID(value) for value in payload["reference_ids"]),
        ),
    )
    print(
        json.dumps(
            {"position": position_fields(result.position), "object_id": str(result.object_id)}
        ),
        flush=True,
    )
    if mode == "commit_then_exit":
        os._exit(19)
    if mode != "replay":
        raise ValueError("Unknown Memory receipt probe")
    await database.close()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
