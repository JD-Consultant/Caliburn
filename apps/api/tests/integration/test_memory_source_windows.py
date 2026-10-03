"""Memory binds the requested employee source, not a Turn number or latest message."""

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.adapters.database import Database
from caliburn.features.interviews.models import InterviewReadError
from caliburn.features.work_memory import sources
from caliburn.features.work_memory.models import MemorySourceWindow, MemorySourceWindowError
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


@dataclass(frozen=True)
class History:
    job_file_id: UUID
    source_ids: tuple[UUID, ...]


def add_source(connection: psycopg.Connection, file_id: UUID, role: str, sequence: int) -> UUID:
    source_id = uuid4()
    connection.execute(
        "INSERT INTO interview_texts (job_file_id, source_id, speaker, interview_text) "
        "VALUES (%s,%s,%s,%s)",
        (file_id, source_id, role, f"合成 {role} {sequence}"),
    )
    connection.execute(
        "INSERT INTO formal_interviews (job_file_id, interview_sequence, source_id) "
        "VALUES (%s,%s,%s)",
        (file_id, sequence, source_id),
    )
    return source_id


@pytest.fixture
def history(database_connection: psycopg.Connection) -> History:
    file_id = uuid4()
    database_connection.execute(
        "INSERT INTO job_files (job_file_id, creation_command_id, initial_display_name, "
        "display_name, employee_name) VALUES (%s,%s,'Memory','Memory','合成员工')",
        (file_id, uuid4()),
    )
    # Deliberately not an odd/even speaker convention; formal membership is authoritative.
    roles = ("app", "employee", "consultant", "consultant", "employee", "consultant")
    return History(
        file_id,
        tuple(
            add_source(database_connection, file_id, role, index)
            for index, role in enumerate(roles, start=1)
        ),
    )


def query[T](settings: DatabaseSettings, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        database = Database(settings)
        try:
            async with database.sessions() as session:
                return await operation(session)
        finally:
            await database.close()

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        return runner.run(run())


def bind(settings: DatabaseSettings, history: History, covered: int = 0) -> MemorySourceWindow:
    window = query(
        settings,
        lambda session: sources.bind_memory_source_window(
            session,
            job_file_id=history.job_file_id,
            through_source_id=history.source_ids[4],
            covered_through_sequence=covered,
        ),
    )
    assert window is not None
    return window


def test_required_window_ends_at_requested_employee_not_final_reply_or_latest_history(
    database_settings: DatabaseSettings, database_connection: psycopg.Connection, history: History
) -> None:
    first = bind(database_settings, history)
    later_input = add_source(database_connection, history.job_file_id, "employee", 7)
    add_source(database_connection, history.job_file_id, "consultant", 8)
    delayed = bind(database_settings, history)
    assert delayed == first == MemorySourceWindow(history.job_file_id, history.source_ids[4], 0, 5)
    required = query(database_settings, lambda s: sources.read_required_interviews(s, first))
    assert [message.interview_sequence for message in required.messages] == [1, 2, 3, 4, 5]
    assert [message.speaker for message in required.messages] == [
        "app",
        "employee",
        "consultant",
        "consultant",
        "employee",
    ]
    assert required.context_sequences == ()
    assert all(message.source_id != later_input for message in required.messages)


def test_new_work_and_older_reference_scope_are_distinct(
    database_settings: DatabaseSettings, history: History
) -> None:
    window = bind(database_settings, history, covered=2)
    required = query(database_settings, lambda s: sources.read_required_interviews(s, window))
    assert [message.interview_sequence for message in required.messages] == [3, 4, 5]
    referenced = query(
        database_settings,
        lambda s: sources.read_reference_sources(
            s, window, source_ids=frozenset({history.source_ids[0], history.source_ids[1]})
        ),
    )
    assert [message.interview_sequence for message in referenced] == [1, 2]
    assert (
        query(
            database_settings,
            lambda s: sources.read_reference_sources(s, window, source_ids=frozenset()),
        )
        == ()
    )
    assert window.covered_through_sequence == 2


@pytest.mark.parametrize("covered", [5, 7])
def test_request_already_covered_does_not_create_an_empty_batch(
    database_settings: DatabaseSettings,
    database_connection: psycopg.Connection,
    history: History,
    covered: int,
) -> None:
    add_source(database_connection, history.job_file_id, "employee", 7)
    add_source(database_connection, history.job_file_id, "consultant", 8)
    result = query(
        database_settings,
        lambda s: sources.bind_memory_source_window(
            s,
            job_file_id=history.job_file_id,
            through_source_id=history.source_ids[4],
            covered_through_sequence=covered,
        ),
    )
    assert result is None


@pytest.mark.parametrize("sequence", [1, 3, 6])
def test_guidance_cannot_be_a_memory_processing_endpoint(
    database_settings: DatabaseSettings,
    history: History,
    sequence: int,
) -> None:
    with pytest.raises(MemorySourceWindowError):
        query(
            database_settings,
            lambda s: sources.bind_memory_source_window(
                s,
                job_file_id=history.job_file_id,
                through_source_id=history.source_ids[sequence - 1],
                covered_through_sequence=0,
            ),
        )


@pytest.mark.parametrize("covered", [-1, True, 1.5, 3, 99])
def test_bad_coverage_is_not_hidden_as_an_already_completed_request(
    database_settings: DatabaseSettings,
    history: History,
    covered: int,
) -> None:
    with pytest.raises((MemorySourceWindowError, InterviewReadError)):
        bind(database_settings, history, covered)


def test_references_reject_formal_but_outside_batch_reply(
    database_settings: DatabaseSettings,
    history: History,
) -> None:
    window = bind(database_settings, history)
    with pytest.raises(InterviewReadError):
        query(
            database_settings,
            lambda s: sources.read_reference_sources(
                s, window, source_ids=frozenset({history.source_ids[0], history.source_ids[5]})
            ),
        )
