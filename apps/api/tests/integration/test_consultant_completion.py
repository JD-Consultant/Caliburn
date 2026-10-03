"""A completion/abandonment transactions on PostgreSQL; native final proof belongs to caller."""

from collections.abc import Awaitable, Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from functools import partial
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import (
    ExecutionInfo,
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
    ExecutionWriter,
    StaleWriterError,
)
from caliburn.features.interviews import queries
from caliburn.features.interviews import service as interviews
from caliburn.features.interviews.models import (
    FormalInterviewExchange,
    InterviewSourceNotAvailableError,
)
from caliburn.features.job_description import candidate_service, source_persistence
from caliburn.features.job_description.candidates import CandidateStateError, JdCandidatePosition
from caliburn.features.job_description.models import (
    ProfileField,
    ReviseJdProfile,
    SetProfileField,
)
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow

pytestmark = pytest.mark.postgres


def transact[T](client: TestClient, operation: Callable[[AsyncSession], Awaitable[T]]) -> T:
    async def run() -> T:
        async with client.app.state.database.sessions.begin() as session:
            return await operation(session)

    return client.portal.call(run)


@dataclass(frozen=True)
class Turn:
    writer: ExecutionWriter
    prepared: ContextPosition
    completed: ContextPosition
    candidate: JdCandidatePosition | None


def start_turn(
    client: TestClient, *, with_candidate: bool = True, file_id: UUID | None = None
) -> Turn:
    if file_id is None:
        created = client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "完成測試",
                "employee_name": "合成人員",
            },
        )
        assert created.status_code == 201
        file_id = UUID(created.json()["job_file_id"])
    accepted = client.post(
        f"/api/job-files/{file_id}/inputs",
        json={"command_id": str(uuid4()), "text": "我負責網站前端交付。"},
    )
    assert accepted.status_code == 202
    scope = ExecutionScope(
        file_id, UUID(accepted.json()["execution_id"]), ExecutionKind.CONSULTANT_TURN
    )
    writer = transact(client, lambda s: executions.claim_writer(s, scope, writer_id=uuid4()))
    role = AgentRole.JOB_CONSULTANT
    # Like the history-owner fixtures: these are caller-supplied references. This suite
    # verifies transactional eligibility, not native saver durability or final detection.
    prepared = ContextPosition(
        context_thread_id(scope, role, HistoryWindowKind.PREPARED_HISTORY),
        "prepared-checkpoint",
        HistoryWindowKind.PREPARED_HISTORY,
    )
    completed = ContextPosition(
        context_thread_id(scope, role, HistoryWindowKind.COMPLETED_WORK),
        "completed-checkpoint",
        HistoryWindowKind.COMPLETED_WORK,
    )
    transact(client, lambda s: history.bind_context_history(s, writer, role))
    transact(client, lambda s: history.adopt_prepared_context(s, writer, role, prepared))
    candidate = None
    if with_candidate:
        candidates = JdCandidateWorkflow(client.app.state.database.sessions)
        initial = client.portal.call(candidates.start, writer)
        candidate = client.portal.call(
            candidates.edit,
            writer,
            initial.scope,
            ReviseJdProfile(
                uuid4(),
                initial.revision_id,
                (SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),),
            ),
        )
    return Turn(writer, prepared, completed, candidate)


def complete(
    client: TestClient, turn: Turn, reply_text: str = "通常如何驗收交付成果？"
) -> FormalInterviewExchange:
    assert turn.candidate is not None
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    return client.portal.call(
        workflow.complete, turn.writer, turn.candidate, reply_text, turn.completed
    )


def read_head(client: TestClient, turn: Turn) -> ContextPosition | None:
    return transact(
        client,
        partial(
            history.read_adopted_context,
            job_file_id=turn.writer.scope.job_file_id,
            role=AgentRole.JOB_CONSULTANT,
        ),
    )


def test_complete_adopts_jd_and_formal_exchange_and_replays_after_new_history(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    assert turn.candidate is not None
    result = complete(client, turn)
    assert result.employee_input.interview_sequence == 2
    assert result.consultant_reply.interview_sequence == 3
    assert result.consultant_reply.interview_text == "通常如何驗收交付成果？"
    assert transact(client, lambda s: executions.read_execution(s, turn.writer.scope)).status == (
        ExecutionStatus.COMPLETED
    )
    assert read_head(client, turn) == turn.completed
    formal = client.get(f"/api/job-files/{turn.writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(turn.candidate.revision_id)
    later = start_turn(client, file_id=turn.writer.scope.job_file_id)
    assert complete(client, turn) == result
    assert read_head(client, turn) == later.prepared
    assert (
        len(
            client.get(f"/api/job-files/{turn.writer.scope.job_file_id}/interviews").json()[
                "messages"
            ]
        )
        == 3
    )


@pytest.mark.parametrize("status", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_stop_discards_candidate_without_rewinding_prepared_history(
    client: TestClient,
    status: ExecutionStatus,
) -> None:
    turn = start_turn(client)
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    result = client.portal.call(workflow.stop, turn.writer, status)
    assert result.status == status
    with pytest.raises(CandidateStateError):
        transact(
            client,
            lambda s: candidate_service.read_position(
                s, turn.writer.scope.job_file_id, turn.writer.scope.execution_id
            ),
        )
    assert read_head(client, turn) == turn.prepared
    assert client.portal.call(workflow.stop, turn.writer, status) == result
    with pytest.raises(ExecutionStateError):
        complete(client, turn)
    assert (
        transact(
            client,
            partial(
                interviews.read_formal_exchange,
                job_file_id=turn.writer.scope.job_file_id,
                execution_id=turn.writer.scope.execution_id,
            ),
        )
        is None
    )


@pytest.mark.parametrize("status", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_stop_before_candidate_creation_keeps_original_input_private(
    client: TestClient,
    status: ExecutionStatus,
) -> None:
    turn = start_turn(client, with_candidate=False)
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    assert client.portal.call(workflow.stop, turn.writer, status).status == status
    assert read_head(client, turn) == turn.prepared


def test_stop_after_completion_returns_completed_without_discarding(client: TestClient) -> None:
    turn = start_turn(client)
    result = complete(client, turn)
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    assert client.portal.call(workflow.stop, turn.writer, ExecutionStatus.CANCELLED).status == (
        ExecutionStatus.COMPLETED
    )
    assert read_head(client, turn) == turn.completed
    assert complete(client, turn) == result


def input_source(client: TestClient, turn: Turn) -> InterviewSource:
    original = transact(
        client,
        partial(
            queries.read_execution_input,
            job_file_id=turn.writer.scope.job_file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    return InterviewSource(original.source_id)


def add_sources(client: TestClient, turn: Turn, *sources: InterviewSource) -> Turn:
    assert turn.candidate is not None
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    position = client.portal.call(
        candidates.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            tuple(AddJdSource(source) for source in sources),
        ),
    )
    updated = replace(turn, candidate=position)
    # Read real storage: an unavailable/no-op persistence module is not a behavioral Red.
    assert tuple(reference.source for reference in read_sources(client, updated)) == sources
    return updated


def read_sources(client: TestClient, turn: Turn) -> tuple[JdSourceReference, ...]:
    assert turn.candidate is not None
    return transact(
        client,
        partial(
            source_persistence.read_source_references,
            job_file_id=turn.writer.scope.job_file_id,
            revision_id=turn.candidate.revision_id,
        ),
    )


def test_complete_formalizes_current_input_without_rewriting_its_jd_source(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    source = input_source(client, turn)
    turn = add_sources(client, turn, source)
    references = read_sources(client, turn)
    result = complete(client, turn)
    assert result.employee_input.source_id == source.source_id
    assert read_sources(client, turn) == references
    assert complete(client, turn) == result


def test_unformal_source_blocks_whole_completion_even_after_current_input_formalization(
    client: TestClient,
) -> None:
    earlier = start_turn(client, with_candidate=False)
    unformal = input_source(client, earlier)
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    client.portal.call(workflow.stop, earlier.writer, ExecutionStatus.CANCELLED)
    turn = start_turn(client, file_id=earlier.writer.scope.job_file_id)
    turn = add_sources(client, turn, input_source(client, turn), unformal)
    with pytest.raises(InterviewSourceNotAvailableError):
        complete(client, turn)
    assert_unfinished(client, turn)


def assert_unfinished(client: TestClient, turn: Turn) -> None:
    assert turn.candidate is not None
    assert (
        transact(
            client,
            partial(
                interviews.read_formal_exchange,
                job_file_id=turn.writer.scope.job_file_id,
                execution_id=turn.writer.scope.execution_id,
            ),
        )
        is None
    )
    assert transact(client, lambda s: executions.read_execution(s, turn.writer.scope)).status == (
        ExecutionStatus.ACTIVE
    )
    assert (
        transact(
            client,
            lambda s: candidate_service.read_position(
                s, turn.writer.scope.job_file_id, turn.writer.scope.execution_id
            ),
        )
        == turn.candidate
    )
    assert read_head(client, turn) == turn.prepared
    binding = transact(
        client,
        lambda s: history.read_context_history(s, turn.writer.scope, AgentRole.JOB_CONSULTANT),
    )
    assert binding is not None and binding.completed is None
    formal = client.get(f"/api/job-files/{turn.writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(turn.candidate.base_revision_id)
    assert (
        transact(client, lambda s: queries.read_history_frontier(s, turn.writer.scope.job_file_id))
        == 1
    )


@pytest.mark.parametrize("action", ["complete", "stop"])
def test_exception_rolls_back_all_settlement_participants_and_can_retry(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    turn = start_turn(client)
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    finish = executions.finish_execution
    complete_histories = history.complete_context_histories

    async def fail_after_finish(
        session: AsyncSession,
        writer: ExecutionWriter,
        outcome: ExecutionStatus,
    ) -> None:
        await finish(session, writer, outcome)
        raise RuntimeError("injected failure before commit")

    async def fail_after_histories(
        session: AsyncSession,
        writer: ExecutionWriter,
        positions: Mapping[AgentRole, ContextPosition],
    ) -> None:
        await complete_histories(session, writer, positions)
        raise RuntimeError("injected failure before commit")

    def settle() -> FormalInterviewExchange | ExecutionInfo:
        if action == "complete":
            return complete(client, turn)
        return client.portal.call(workflow.stop, turn.writer, ExecutionStatus.CANCELLED)

    # Fault injection follows real owner writes/flushes; no formalization bypass.
    with monkeypatch.context() as fault:
        if action == "complete":
            fault.setattr(history, "complete_context_histories", fail_after_histories)
        else:
            fault.setattr(executions, "finish_execution", fail_after_finish)
        with pytest.raises(RuntimeError, match="injected failure before commit"):
            settle()
    assert_unfinished(client, turn)
    result = settle()
    if isinstance(result, FormalInterviewExchange):
        assert result.employee_input.interview_sequence == 2
        assert result.consultant_reply.interview_sequence == 3
        assert read_head(client, turn) == turn.completed
    else:
        assert result.status == ExecutionStatus.CANCELLED
        assert read_head(client, turn) == turn.prepared
    with pytest.raises(CandidateStateError):
        transact(
            client,
            lambda s: candidate_service.read_position(
                s, turn.writer.scope.job_file_id, turn.writer.scope.execution_id
            ),
        )


def test_replaced_writer_and_pending_pause_cannot_complete_but_paused_turn_can_stop(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s, turn.writer.scope, writer_id=uuid4(), replaces_writer_id=turn.writer.writer_id
        ),
    )
    with pytest.raises(StaleWriterError):
        complete(client, turn)
    with pytest.raises(StaleWriterError):
        client.portal.call(workflow.stop, turn.writer, ExecutionStatus.CANCELLED)
    turn = replace(turn, writer=replacement)
    transact(client, lambda s: executions.request_pause(s, turn.writer.scope))
    with pytest.raises(ExecutionStateError):
        complete(client, turn)
    assert_unfinished(client, turn)
    assert transact(
        client, lambda s: executions.read_execution(s, turn.writer.scope)
    ).pause_requested
    transact(client, lambda s: executions.pause_execution(s, turn.writer))
    assert client.portal.call(workflow.stop, turn.writer, ExecutionStatus.CANCELLED).status == (
        ExecutionStatus.CANCELLED
    )
    assert read_head(client, turn) == turn.prepared


def test_complete_and_cancel_race_has_one_atomic_outcome(client: TestClient) -> None:
    turn = start_turn(client)
    assert turn.candidate is not None
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    ready = Barrier(2)

    def completing() -> FormalInterviewExchange | None:
        ready.wait(timeout=10)
        try:
            return complete(client, turn)
        except ExecutionStateError:
            return None

    def stopping() -> ExecutionInfo:
        ready.wait(timeout=10)
        return client.portal.call(workflow.stop, turn.writer, ExecutionStatus.CANCELLED)

    with ThreadPoolExecutor(max_workers=2) as pool:
        completion = pool.submit(completing)
        cancellation = pool.submit(stopping)
        exchange, outcome = completion.result(), cancellation.result()
    persisted = transact(
        client,
        partial(
            interviews.read_formal_exchange,
            job_file_id=turn.writer.scope.job_file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    assert persisted == exchange
    final = transact(client, lambda s: executions.read_execution(s, turn.writer.scope))
    assert outcome == final
    assert final.status == (ExecutionStatus.COMPLETED if exchange else ExecutionStatus.CANCELLED)
    assert read_head(client, turn) == (turn.completed if exchange else turn.prepared)
    formal = client.get(f"/api/job-files/{turn.writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(
        turn.candidate.revision_id if exchange else turn.candidate.base_revision_id
    )
    with pytest.raises(CandidateStateError):
        transact(
            client,
            lambda s: candidate_service.read_position(
                s, turn.writer.scope.job_file_id, turn.writer.scope.execution_id
            ),
        )
