"""The same fixed formal-source bounds serve context and later A/B read tools."""

from collections.abc import Awaitable, Callable
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionStatus
from caliburn.features.interviews import queries
from caliburn.features.interviews.models import (
    InterviewInputNotFoundError,
    InterviewReadError,
    InterviewReadScope,
)
from caliburn.workflows.interview_completion import record_formal_interview

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


def add_exchange(client: TestClient, file_id: UUID, number: int) -> None:
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={
            "command_id": str(uuid4()),
            "text": f" 員工原話 {number}\n補充 ",
        },
    ).json()
    scope = ExecutionScope(file_id, UUID(accepted["execution_id"]), ExecutionKind.CONSULTANT_TURN)
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))

    async def complete(session: AsyncSession) -> None:
        await record_formal_interview(session, writer, reply_text=f"顧問正式答覆 {number}")
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)

    transact(client, complete)


@pytest.fixture
def history_file(client: TestClient) -> UUID:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={"command_id": str(uuid4()), "display_name": "來源範圍", "employee_name": "員工"},
        ).json()["job_file_id"]
    )
    for number in range(1, 4):
        add_exchange(client, file_id, number)
    return file_id


def test_batch_upper_bound_excludes_the_final_consultant_reply(
    client: TestClient, history_file: UUID
) -> None:
    # Employee input 6 triggered the batch; formal reply 7 is not part of its sources.
    scope = InterviewReadScope(history_file, 6)
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_range(s, scope, start_sequence=5, end_sequence=7),
        )


def test_selection_is_sorted_deduplicated_and_does_not_insert_extra_context(
    client: TestClient, history_file: UUID
) -> None:
    scope = InterviewReadScope(history_file, 7)
    messages = transact(
        client, lambda s: queries.read_interview_messages(s, scope, sequences=(7, 2, 5, 2))
    )
    assert [message.interview_sequence for message in messages] == [2, 5, 7]
    assert [message.speaker for message in messages] == ["employee", "consultant", "consultant"]
    assert messages[0].interview_text == " 員工原話 1\n補充 "
    full_range = transact(
        client, lambda s: queries.read_interview_range(s, scope, start_sequence=2, end_sequence=5)
    )
    assert [message.interview_sequence for message in full_range] == [2, 3, 4, 5]
    assert full_range[0] == messages[0]


@pytest.mark.parametrize("sequences", [(), (0,), (-1,), (True,), (1.5,), (1, 8)])
def test_invalid_or_partly_outside_selection_returns_no_partial_result(
    client: TestClient, history_file: UUID, sequences: tuple[int, ...]
) -> None:
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_messages(
                s, InterviewReadScope(history_file, 7), sequences=sequences
            ),
        )


@pytest.mark.parametrize("start,end", [(0, 2), (1, 8), (4, 2), (1.0, 2), (1, True)])
def test_invalid_ranges_are_rejected(
    client: TestClient, history_file: UUID, start: int, end: int
) -> None:
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_range(
                s, InterviewReadScope(history_file, 7), start_sequence=start, end_sequence=end
            ),
        )


def test_missing_formal_source_is_not_hidden_by_a_loose_or_wrong_scope(
    client: TestClient, history_file: UUID
) -> None:
    # A future binding layer must not invent 99, but the query still fails closed if it does.
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_messages(
                s, InterviewReadScope(history_file, 99), sequences=(1, 99)
            ),
        )
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_range(
                s, InterviewReadScope(uuid4(), 7), start_sequence=1, end_sequence=7
            ),
        )


@pytest.mark.parametrize(
    "covered,upper,expected,context",
    [
        (0, 1, [1], ()),
        (0, 7, [1, 2, 3, 4, 5, 6, 7], ()),
        (4, 7, [5, 6, 7], ()),
        (3, 7, [3, 4, 5, 6, 7], (3,)),
        (7, 7, [7], (7,)),
        (2, 6, [3, 4, 5, 6], ()),
    ],
)
def test_recent_sources_keep_coverage_and_added_guidance_distinct(
    client: TestClient,
    history_file: UUID,
    covered: int,
    upper: int,
    expected: list[int],
    context: tuple[int, ...],
) -> None:
    scope = InterviewReadScope(history_file, upper)
    recent = transact(
        client,
        lambda s: queries.read_recent_interviews(s, scope, covered_through_sequence=covered),
    )
    assert [message.interview_sequence for message in recent.messages] == expected
    assert recent.context_sequences == context
    assert scope.through_sequence == upper


def test_fixed_scope_does_not_grow_when_more_interviews_finish(
    client: TestClient, history_file: UUID
) -> None:
    a_scope, b_scope = InterviewReadScope(history_file, 7), InterviewReadScope(history_file, 6)
    add_exchange(client, history_file, 4)
    assert transact(client, lambda s: queries.read_history_frontier(s, history_file)) == 9
    for scope, expected in ((a_scope, [5, 6, 7]), (b_scope, [5, 6])):
        recent = transact(
            client,
            lambda s, scope=scope: queries.read_recent_interviews(
                s, scope, covered_through_sequence=4
            ),
        )
        assert [message.interview_sequence for message in recent.messages] == expected


def test_unfinished_original_is_private_and_never_in_recent_or_shared_sources(
    client: TestClient, history_file: UUID
) -> None:
    accepted = client.post(
        f"/api/job-files/{history_file}/inputs",
        json={"command_id": str(uuid4()), "text": "本次還沒完成的原話"},
    ).json()
    execution_id = UUID(accepted["execution_id"])
    original = transact(
        client,
        lambda s: queries.read_execution_input(
            s, job_file_id=history_file, execution_id=execution_id
        ),
    )
    assert original.source_id == UUID(accepted["source_id"])
    assert original.interview_text == "本次還沒完成的原話"
    with pytest.raises(InterviewInputNotFoundError):
        transact(
            client,
            lambda s: queries.read_execution_input(
                s, job_file_id=uuid4(), execution_id=execution_id
            ),
        )
    recent = transact(
        client,
        lambda s: queries.read_recent_interviews(
            s, InterviewReadScope(history_file, 7), covered_through_sequence=0
        ),
    )
    assert all(message.source_id != original.source_id for message in recent.messages)
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_interview_messages(
                s, InterviewReadScope(history_file, 99), sequences=(8,)
            ),
        )


@pytest.mark.parametrize("covered", [-1, 8, True, 1.5])
def test_invalid_coverage_is_not_silently_turned_into_an_empty_recent_window(
    client: TestClient, history_file: UUID, covered: int
) -> None:
    with pytest.raises(InterviewReadError):
        transact(
            client,
            lambda s: queries.read_recent_interviews(
                s, InterviewReadScope(history_file, 7), covered_through_sequence=covered
            ),
        )
