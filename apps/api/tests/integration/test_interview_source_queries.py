"""Source identities resolve only as a complete selection inside the caller's fixed scope."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews import queries
from caliburn.features.interviews.models import (
    InterviewMessage,
    InterviewReadError,
    InterviewReadScope,
    InterviewSpeaker,
)

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    # Reuse the integration client's existing app, database and event loop.
    assert isinstance(client.app, FastAPI)
    database = client.app.state.database
    assert isinstance(database, Database)
    assert client.portal is not None

    async def run() -> T:
        async with database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def create_file(client: TestClient) -> UUID:
    response = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "來源身分", "employee_name": "合成員工"},
    )
    assert response.status_code == 201
    return UUID(response.json()["job_file_id"])


def add_formal_message(
    connection: psycopg.Connection,
    file_id: UUID,
    sequence: int,
    speaker: InterviewSpeaker,
    text: str,
) -> InterviewMessage:
    source_id = uuid4()
    with connection.transaction():
        connection.execute(
            "INSERT INTO interview_texts (source_id, job_file_id, speaker, interview_text) "
            "VALUES (%s, %s, %s, %s)",
            (source_id, file_id, speaker.value, text),
        )
        connection.execute(
            "INSERT INTO formal_interviews (job_file_id, interview_sequence, source_id) "
            "VALUES (%s, %s, %s)",
            (file_id, sequence, source_id),
        )
    return InterviewMessage(source_id, sequence, speaker, text)


@pytest.fixture
def source_history(
    client: TestClient, database_connection: psycopg.Connection
) -> tuple[InterviewReadScope, list[InterviewMessage]]:
    file_id = create_file(client)
    messages = transact(client, lambda s: queries.read_interview_history(s, file_id))
    for sequence, speaker, text in (
        (2, InterviewSpeaker.EMPLOYEE, " 員工原話\n保留空白 "),
        (3, InterviewSpeaker.CONSULTANT, "較早的顧問追問"),
        (4, InterviewSpeaker.EMPLOYEE, "本批 F 的員工原話"),
        (5, InterviewSpeaker.CONSULTANT, "F 之後的顧問答覆不能外露"),
    ):
        messages.append(add_formal_message(database_connection, file_id, sequence, speaker, text))
    return InterviewReadScope(file_id, 4), messages


def test_selected_sources_are_deduplicated_sorted_and_preserve_originals(
    client: TestClient, source_history: tuple[InterviewReadScope, list[InterviewMessage]]
) -> None:
    scope, history = source_history
    first, frontier = history[1], history[3]
    messages = transact(
        client,
        lambda s: queries.read_interview_sources(
            s, scope, source_ids=(frontier.source_id, first.source_id, frontier.source_id)
        ),
    )
    assert messages == [first, frontier]
    assert messages[0].interview_text == " 員工原話\n保留空白 "


def test_opening_and_earlier_consultant_sources_are_readable_in_the_same_scope(
    client: TestClient, source_history: tuple[InterviewReadScope, list[InterviewMessage]]
) -> None:
    scope, history = source_history
    opening, consultant = history[0], history[2]
    messages = transact(
        client,
        lambda s: queries.read_interview_sources(
            s, scope, source_ids=(consultant.source_id, opening.source_id)
        ),
    )
    assert messages == [opening, consultant]
    assert [message.speaker for message in messages] == [
        InterviewSpeaker.APP,
        InterviewSpeaker.CONSULTANT,
    ]


@pytest.mark.parametrize("status", [ExecutionStatus.ACTIVE, ExecutionStatus.CANCELLED])
def test_pending_or_cancelled_input_rejects_the_entire_selection(
    client: TestClient,
    source_history: tuple[InterviewReadScope, list[InterviewMessage]],
    status: ExecutionStatus,
) -> None:
    scope, history = source_history
    private_text = "尚無正式資格的原話不能外露"
    response = client.post(
        f"/api/job-files/{scope.job_file_id}/inputs",
        json={"command_id": str(uuid4()), "text": private_text},
    )
    assert response.status_code == 202
    accepted = response.json()
    source_id = UUID(accepted["source_id"])
    if status == ExecutionStatus.CANCELLED:
        execution_scope = ExecutionScope(
            scope.job_file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN
        )
        writer = transact(
            client, lambda s: executions.claim_writer(s, execution_scope, writer_id=uuid4())
        )
        transact(client, lambda s: executions.finish_execution(s, writer, status))

    with pytest.raises(InterviewReadError) as error:
        transact(
            client,
            lambda s: queries.read_interview_sources(
                s, scope, source_ids=(history[1].source_id, source_id)
            ),
        )
    assert private_text not in str(error.value)
    assert str(source_id) not in str(error.value)


@pytest.mark.parametrize("invalid_source", ["cross_file", "missing", "above_boundary"])
def test_unavailable_or_out_of_scope_source_rejects_the_entire_selection(
    client: TestClient,
    database_connection: psycopg.Connection,
    source_history: tuple[InterviewReadScope, list[InterviewMessage]],
    invalid_source: str,
) -> None:
    scope, history = source_history
    forbidden_text = history[4].interview_text
    if invalid_source == "cross_file":
        forbidden_text = "另一份檔案的正式原話不能外露"
        source_id = add_formal_message(
            database_connection, create_file(client), 2, InterviewSpeaker.EMPLOYEE, forbidden_text
        ).source_id
    elif invalid_source == "missing":
        source_id = uuid4()
    else:
        source_id = history[4].source_id

    with pytest.raises(InterviewReadError) as error:
        transact(
            client,
            lambda s: queries.read_interview_sources(
                s, scope, source_ids=(history[1].source_id, source_id)
            ),
        )
    assert forbidden_text not in str(error.value)
    assert str(source_id) not in str(error.value)


def test_old_scope_does_not_expand_after_new_formal_interviews(
    client: TestClient,
    database_connection: psycopg.Connection,
    source_history: tuple[InterviewReadScope, list[InterviewMessage]],
) -> None:
    scope, history = source_history
    selected = (history[3].source_id, history[1].source_id)
    before = transact(
        client, lambda s: queries.read_interview_sources(s, scope, source_ids=selected)
    )
    newer = add_formal_message(
        database_connection, scope.job_file_id, 6, InterviewSpeaker.EMPLOYEE, "後來完成的員工原話"
    )
    assert (
        transact(client, lambda s: queries.read_interview_sources(s, scope, source_ids=selected))
        == before
    )
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_sources(
                s, scope, source_ids=(*selected, newer.source_id)
            ),
        )
    new_scope = InterviewReadScope(scope.job_file_id, newer.interview_sequence)
    assert transact(
        client,
        lambda s: queries.read_interview_sources(s, new_scope, source_ids=(newer.source_id,)),
    ) == [newer]
    assert scope.through_sequence == 4


def test_empty_source_selection_is_rejected(client: TestClient) -> None:
    scope = InterviewReadScope(create_file(client), 1)
    with pytest.raises(InterviewReadError):
        transact(client, lambda s: queries.read_interview_sources(s, scope, source_ids=()))
