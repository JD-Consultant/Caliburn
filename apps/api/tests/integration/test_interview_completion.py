"""Formal interview membership is part of one completion transaction, not input acceptance."""

from collections.abc import Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.interviews.models import (
    FormalInterviewExchange,
    InterviewCompletionConflictError,
)
from caliburn.workflows.interview_completion import record_formal_interview

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def create_file(client: TestClient) -> UUID:
    return UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "盤點", "employee_name": "員工"},
        ).json()["job_file_id"]
    )


def accept_writer(client: TestClient, file_id: UUID, text: str = "每月一次") -> ExecutionWriter:
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs", json={"command_id": str(uuid4()), "text": text}
    )
    assert accepted.status_code == 202, accepted.text
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )
    return transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))


def complete_interview(
    client: TestClient, writer: ExecutionWriter, reply_text: str = "可以再說明實際流程嗎？"
) -> FormalInterviewExchange:
    async def complete(session: AsyncSession) -> FormalInterviewExchange:
        # This harness has no JD; the production T08 caller must commit all effects together.
        result = await record_formal_interview(session, writer, reply_text=reply_text)
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        return result

    return transact(client, complete)


def test_successful_exchange_retains_original_and_reply_in_formal_order(
    client: TestClient,
) -> None:
    file_id = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "盤點", "employee_name": "測試員工"},
    ).json()["job_file_id"]
    original_text, reply_text = " 每月一次。\n但旺季會加班。 ", "哪些工作只在旺季發生？"
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": original_text},
    ).json()
    scope = ExecutionScope(
        UUID(file_id), UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))

    async def complete_interview_part(session: AsyncSession) -> None:
        # Synthetic completion harness; production must also adopt JD and background intent.
        await record_formal_interview(session, writer, reply_text=reply_text)
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)

    transact(client, complete_interview_part)
    messages = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
    assert [message["interview_sequence"] for message in messages] == [1, 2, 3]
    assert [message["speaker"] for message in messages] == ["app", "employee", "consultant"]
    assert [message["interview_text"] for message in messages[1:]] == [original_text, reply_text]
    assert messages[1]["source_id"] == accepted["source_id"]


def test_completion_replay_keeps_original_pair_after_later_interviews(client: TestClient) -> None:
    file_id = create_file(client)
    first = accept_writer(client, file_id)
    result = complete_interview(client, first, "原本的完整答覆")
    complete_interview(client, accept_writer(client, file_id, "還有臨時盤點"), "後來的完整答覆")
    replay = transact(
        client, lambda s: record_formal_interview(s, first, reply_text="原本的完整答覆")
    )
    assert replay == result
    assert replay.employee_input.interview_sequence == 2
    assert replay.consultant_reply.interview_sequence == 3
    with pytest.raises(InterviewCompletionConflictError):
        transact(
            client, lambda s: record_formal_interview(s, first, reply_text="不能冒充的重算答覆")
        )


def test_concurrent_completion_replay_allocates_one_pair(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = accept_writer(client, create_file(client))
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: complete_interview(client, writer), range(8)))
    assert all(result == results[0] for result in results)
    assert database_connection.execute("SELECT count(*) FROM interview_replies").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone() == (3,)


def test_later_effect_failure_rolls_back_membership_reply_and_sequence_allocation(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    file_id = create_file(client)
    writer = accept_writer(client, file_id)

    async def fail_after_reply(session: AsyncSession) -> None:
        await record_formal_interview(session, writer, reply_text="不會成立的答覆")
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        raise RuntimeError("injected later completion failure")

    with pytest.raises(RuntimeError, match="injected"):
        transact(client, fail_after_reply)
    assert database_connection.execute("SELECT count(*) FROM interview_replies").fetchone() == (0,)
    assert database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone() == (1,)
    assert database_connection.execute("SELECT count(*) FROM interview_texts").fetchone() == (2,)
    assert transact(client, lambda s: executions.read_execution(s, writer.scope)).status == "active"
    recovered = complete_interview(client, writer, "真正成立的答覆")
    assert recovered.employee_input.interview_sequence == 2
    assert recovered.consultant_reply.interview_sequence == 3


@pytest.mark.parametrize("outcome", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_abandoned_input_never_becomes_formal_or_consumes_a_number(
    client: TestClient, outcome: ExecutionStatus
) -> None:
    file_id = create_file(client)
    abandoned = accept_writer(client, file_id, "不採用的輸入")
    transact(client, lambda s: executions.finish_execution(s, abandoned, outcome))
    with pytest.raises(ExecutionStateError):
        complete_interview(client, abandoned, "遲到的答覆")
    accepted = complete_interview(client, accept_writer(client, file_id, "新的輸入"))
    assert accepted.employee_input.interview_sequence == 2
    texts = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
    assert all(message["interview_text"] != "不採用的輸入" for message in texts)


def test_pause_and_superseded_writer_cannot_formalize(client: TestClient) -> None:
    writer = accept_writer(client, create_file(client))
    transact(client, lambda s: executions.pause_execution(s, writer))
    with pytest.raises(ExecutionStateError):
        complete_interview(client, writer)
    transact(client, lambda s: executions.resume_execution(s, writer))
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s, writer.scope, writer_id=uuid4(), replaces_writer_id=writer.writer_id
        ),
    )
    with pytest.raises(StaleWriterError):
        complete_interview(client, writer)
    assert complete_interview(client, replacement).employee_input.interview_sequence == 2


def test_memory_execution_cannot_create_formal_interviews(client: TestClient) -> None:
    scope = ExecutionScope(create_file(client), uuid4(), ExecutionKind.MEMORY_BATCH)
    transact(client, lambda s: executions.admit_execution(s, scope))
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))
    with pytest.raises(ExecutionStateError):
        complete_interview(client, writer)


def test_cross_file_writer_cannot_grant_source_eligibility(client: TestClient) -> None:
    original = accept_writer(client, create_file(client))
    wrong = ExecutionWriter(
        ExecutionScope(create_file(client), original.scope.execution_id, original.scope.kind),
        original.writer_id,
    )
    with pytest.raises(ExecutionNotFoundError):
        complete_interview(client, wrong)
    assert complete_interview(client, original).employee_input.interview_sequence == 2


def test_reply_identity_is_immutable_and_scoped_to_original_submission(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    first_file, second_file = create_file(client), create_file(client)
    first, second = accept_writer(client, first_file), accept_writer(client, second_file)
    complete_interview(client, first)
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute("UPDATE interview_replies SET source_id = %s", (uuid4(),))
    with pytest.raises(psycopg.errors.CheckViolation):
        database_connection.execute("DELETE FROM interview_replies")
    unused_reply = uuid4()
    database_connection.execute(
        "INSERT INTO interview_texts VALUES (%s, %s, 'consultant', '尚未正式採用的答覆')",
        (unused_reply, first_file),
    )
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "INSERT INTO interview_replies VALUES (%s, %s, %s)",
            (first_file, second.scope.execution_id, unused_reply),
        )


@pytest.mark.parametrize("reply_text", ["", " \n", "bad\x00text"])
def test_invalid_final_reply_cannot_grant_formal_membership(
    client: TestClient, reply_text: str
) -> None:
    writer = accept_writer(client, create_file(client))
    with pytest.raises(ValueError):
        complete_interview(client, writer, reply_text)
    assert (
        len(client.get(f"/api/job-files/{writer.scope.job_file_id}/interviews").json()["messages"])
        == 1
    )


def test_cancel_racing_completion_cannot_leave_a_half_formal_exchange(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    writer = accept_writer(client, create_file(client))

    def finish(cancel: bool) -> bool:
        try:
            if cancel:
                transact(
                    client,
                    lambda s: executions.finish_execution(s, writer, ExecutionStatus.CANCELLED),
                )
            else:
                complete_interview(client, writer)
            return True
        except ExecutionStateError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(finish, (True, False)))
    assert outcomes.count(True) == 1
    status = transact(client, lambda s: executions.read_execution(s, writer.scope)).status
    formal_count = database_connection.execute("SELECT count(*) FROM formal_interviews").fetchone()[
        0
    ]
    reply_count = database_connection.execute("SELECT count(*) FROM interview_replies").fetchone()[
        0
    ]
    assert (formal_count, reply_count) == ((3, 1) if status == "completed" else (1, 0))
