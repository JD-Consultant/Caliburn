"""Start a synthetic consultant writer through the formal HTTP admission boundary."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


MANUAL_PURPOSE = "冷重啟保留完整人工使命"


def start_consultant_turn(
    client: TestClient, *, initial_purpose: str | None = None
) -> ExecutionWriter:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "來源編修",
                "employee_name": "合成人員",
            },
        ).json()["job_file_id"]
    )
    if initial_purpose is not None:
        url = f"/api/job-files/{file_id}/jd/profile"
        before = client.get(url).json()
        edited = client.post(
            url,
            json={
                "command_id": str(uuid4()),
                "expected_revision_id": before["revision_id"],
                "changes": [{"action": "set_field", "field": "purpose", "value": initial_purpose}],
            },
        )
        assert edited.status_code == 200, edited.text
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我負責網站前端開發。"},
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    return transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))
