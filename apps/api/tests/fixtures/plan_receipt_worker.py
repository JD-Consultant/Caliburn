"""Exit after a real Plan tool commit, before a caller can checkpoint its output."""

import asyncio
import json
import os
import sys
from uuid import UUID

from caliburn.adapters.database import Database
from caliburn.adapters.database_settings import require_isolated_test_database
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.interview_plans import InterviewPlanTools
from caliburn.workflows.interview_plans import InterviewPlanWorkflow


async def main() -> None:
    mode, schema, file_id, execution_id, writer_id = sys.argv[1:]
    dsn = os.environ["CALIBURN_TEST_DATABASE_URL"]
    require_isolated_test_database(dsn, environment=os.environ)
    database = Database(DatabaseSettings(url=dsn, schema=schema))
    scope = ExecutionScope(UUID(file_id), UUID(execution_id), ExecutionKind.CONSULTANT_TURN)
    writer = ExecutionWriter(scope, UUID(writer_id))
    tools = InterviewPlanTools(InterviewPlanWorkflow(database.sessions), writer)
    result = await tools.execute(json.loads(sys.stdin.read()))
    print(json.dumps({"result": result}, ensure_ascii=True), flush=True)
    if mode == "commit_then_exit":
        os._exit(19)  # Deliberately skip finally/connection cleanup in this isolated worker.
    if mode != "replay":
        raise ValueError("Unknown Plan receipt probe")
    await database.close()


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
