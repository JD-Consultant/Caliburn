"""Cold owner reentry recovers a committed Plan tool without duplicating body or receipt."""

import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from caliburn.features.interview_plans import service
from caliburn.features.interview_plans.models import PlanEdit
from caliburn.settings import DatabaseSettings
from caliburn.transport.model_tools.interview_plans import InterviewPlanTools
from caliburn.workflows.interview_plans import InterviewPlanWorkflow
from tests.integration.test_consultant_completion import start_turn, transact

pytestmark = pytest.mark.postgres


def test_cold_plan_tool_reentry_keeps_original_result_and_later_head(
    client: TestClient,
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
) -> None:
    turn = start_turn(client)
    writer = turn.writer
    scope = writer.scope
    initial = transact(
        client, lambda s: service.start_candidate(s, scope.job_file_id, scope.execution_id, None)
    )
    workflow = InterviewPlanWorkflow(client.app.state.database.sessions)
    tools = InterviewPlanTools(workflow, writer)
    prepared = client.portal.call(
        tools.prepare,
        "edit_interview_plan",
        json.dumps({"diff": "@@\n+固定原正文\n*** End of File"}),
        uuid4(),
    )
    assert isinstance(prepared, dict)

    def worker(mode: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-B",
                "-m",
                "tests.fixtures.plan_receipt_worker",
                mode,
                database_settings.schema,
                str(scope.job_file_id),
                str(scope.execution_id),
                str(writer.writer_id),
            ],
            cwd=Path(__file__).resolve().parents[2],
            input=json.dumps(prepared),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=30,
        )

    crashed = worker("commit_then_exit")
    assert crashed.returncode == 19, crashed.stderr
    committed_result = json.loads(crashed.stdout)["result"]
    original = client.portal.call(workflow.read_current, scope)
    assert original is not None and original.body == "固定原正文"
    assert original.position != initial.position
    later = client.portal.call(
        workflow.apply,
        writer,
        PlanEdit(uuid4(), original.position, "@@\n-固定原正文\n+後續正文", "後續正文", "later"),
    )

    def counts() -> tuple[int, int]:
        return database_connection.execute(
            "SELECT (SELECT count(*) FROM interview_plan_bodies WHERE job_file_id=%s),"
            "(SELECT count(*) FROM interview_plan_operations WHERE job_file_id=%s)",
            (scope.job_file_id, scope.job_file_id),
        ).fetchone()

    before = counts()
    replayed = worker("replay")
    assert replayed.returncode == 0, replayed.stderr
    assert json.loads(replayed.stdout)["result"] == committed_result
    assert client.portal.call(workflow.read_current, scope) == later.snapshot
    assert counts() == before == (2, 3)
