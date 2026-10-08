"""Turn-local plan preservation, original results and formal adoption on PostgreSQL."""

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Barrier
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    ContextPosition,
    HistoryConflictError,
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
from caliburn.features.interview_plans import service
from caliburn.features.interview_plans.models import (
    PlanConflictError,
    PlanEdit,
    PlanSnapshot,
    PlanStateError,
    StalePlanPositionError,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import (
    FormalInterviewExchange,
    InterviewCompletionConflictError,
    InterviewReadScope,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.interview_completion import record_formal_interview
from caliburn.workflows.interview_plans import (
    InterviewPlanReadWorkflow,
    InterviewPlanWorkflow,
    read_adopted_plan,
    start_interview_plan,
)
from tests.integration.test_consultant_completion import (
    Turn,
    assert_unfinished,
    complete,
    start_turn,
    transact,
)

pytestmark = pytest.mark.postgres


def test_saved_plan_has_owned_candidate_and_immutable_full_operation_tables(
    database_connection: psycopg.Connection,
) -> None:
    # Missing durable plan storage is a behavior gap, rather than an import failure.
    found = {
        row[0]
        for row in database_connection.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = current_schema() "
            "AND table_name IN ('interview_plan_candidates', 'interview_plan_operations')"
        )
    }
    assert found == {"interview_plan_candidates", "interview_plan_operations"}


def test_start_saves_nullable_full_body_and_reentry_keeps_original_base(client: TestClient) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    initial = transact(
        client, lambda s: service.start_candidate(s, scope.job_file_id, scope.execution_id, None)
    )
    current = transact(
        client, lambda s: service.read_current(s, scope.job_file_id, scope.execution_id)
    )
    assert current == initial
    assert current is not None and current.body is None
    reentered = transact(
        client,
        lambda s: service.start_candidate(s, scope.job_file_id, scope.execution_id, "新基底"),
    )
    assert reentered == initial


def test_complete_cannot_skip_an_existing_plan_candidate(client: TestClient) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    transact(
        client, lambda s: service.start_candidate(s, scope.job_file_id, scope.execution_id, None)
    )
    with pytest.raises(PlanStateError):
        complete(client, turn)


def start_plan(client: TestClient, turn: Turn, body: str | None = None) -> PlanSnapshot:
    scope = turn.writer.scope
    return transact(
        client, lambda s: service.start_candidate(s, scope.job_file_id, scope.execution_id, body)
    )


def plan_workflow(client: TestClient) -> InterviewPlanWorkflow:
    return InterviewPlanWorkflow(client.app.state.database.sessions)


def edit_at(snapshot: PlanSnapshot, body: str | None, *, unchanged: bool = False) -> PlanEdit:
    """Owner tests supply already prepared effects; the shared editor is tested separately."""
    return PlanEdit(
        uuid4(),
        snapshot.position,
        "@@\n-舊內容\n+新內容",
        body,
        '{"status":"unchanged"}' if unchanged else '{"status":"updated","diff":"原成功\\n觀察"}',
    )


def current(client: TestClient, turn: Turn) -> PlanSnapshot | None:
    return client.portal.call(plan_workflow(client).read_current, turn.writer.scope)


def settle(client: TestClient, turn: Turn, plan: PlanSnapshot) -> FormalInterviewExchange:
    assert turn.candidate is not None
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    return client.portal.call(
        workflow.complete,
        turn.writer,
        turn.candidate,
        "通常如何核對結果？",
        turn.completed,
        plan.position,
    )


def adopted(client: TestClient, file_id: UUID, frontier: int | None = None) -> PlanSnapshot | None:
    if frontier is None:
        return client.portal.call(
            InterviewPlanReadWorkflow(client.app.state.database.sessions).read_adopted, file_id
        )
    return transact(client, lambda s: read_adopted_plan(s, InterviewReadScope(file_id, frontier)))


@pytest.mark.parametrize("body", [None, "", " \n", "## 焦點\n保留其他未知。"])
def test_unchanged_still_saves_result_and_advances_revision(
    client: TestClient, body: str | None
) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn, body)
    command = edit_at(initial, body, unchanged=True)
    result = client.portal.call(plan_workflow(client).apply, turn.writer, command)
    assert result.snapshot.body == body
    assert result.snapshot.position != initial.position
    assert result.result_text == '{"status":"unchanged"}'
    assert current(client, turn) == result.snapshot
    scope = turn.writer.scope
    assert (
        transact(client, lambda s: service.read_base(s, scope.job_file_id, scope.execution_id))
        == initial
    )
    assert (
        transact(
            client,
            lambda s: service.start_candidate(s, scope.job_file_id, scope.execution_id, "較新"),
        )
        == initial
    )


def test_original_apply_replays_exact_result_without_rewinding_later_head(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn)
    workflow = plan_workflow(client)
    command = edit_at(initial, "## 焦點\n釐清盤點。")
    first = client.portal.call(workflow.apply, turn.writer, command)
    clear = edit_at(first.snapshot, "")
    second = client.portal.call(workflow.apply, turn.writer, clear)
    assert second.snapshot.body == ""
    assert client.portal.call(workflow.apply, turn.writer, command) == first
    assert current(client, turn) == second.snapshot
    with pytest.raises(StalePlanPositionError):
        client.portal.call(workflow.apply, turn.writer, replace(command, operation_id=uuid4()))
    for different in (
        replace(command, diff=command.diff + "\n+其他"),
        replace(command, next_plan="不同正文"),
        replace(command, result_text=command.result_text + " "),
        replace(command, position=second.snapshot.position),
    ):
        with pytest.raises(PlanConflictError):
            client.portal.call(workflow.apply, turn.writer, different)
    assert current(client, turn) == second.snapshot


def test_completed_turn_replays_only_original_plan_operation_without_changing_head(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn)
    workflow = plan_workflow(client)
    command = edit_at(initial, "完成前正文")
    first = client.portal.call(workflow.apply, turn.writer, command)
    second = client.portal.call(workflow.apply, turn.writer, edit_at(first.snapshot, "最後正文"))
    settle(client, turn, second.snapshot)
    recovered = client.portal.call(workflow.apply, turn.writer, command)
    assert recovered == first
    assert current(client, turn) == second.snapshot
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.apply, turn.writer, replace(command, operation_id=uuid4()))
    with pytest.raises(PlanConflictError):
        client.portal.call(workflow.apply, turn.writer, replace(command, next_plan="另一意圖"))


def test_earlier_unchanged_replay_is_retained_after_new_effect(client: TestClient) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn)
    workflow = plan_workflow(client)
    command = edit_at(initial, None, unchanged=True)
    first = client.portal.call(workflow.apply, turn.writer, command)
    last = client.portal.call(workflow.apply, turn.writer, edit_at(first.snapshot, "新增焦點"))
    assert client.portal.call(workflow.apply, turn.writer, command) == first
    assert first.snapshot.body is None
    assert current(client, turn) == last.snapshot


def test_apply_commit_confirmation_loss_recovers_from_original_operation(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn)
    command = edit_at(initial, "可靠正文")
    workflow = plan_workflow(client)

    def lose_ack() -> None:
        client.portal.call(workflow.apply, turn.writer, command)
        raise ConnectionError("injected lost commit confirmation")

    with pytest.raises(ConnectionError, match="lost commit confirmation"):
        lose_ack()
    recovered = client.portal.call(plan_workflow(client).apply, turn.writer, command)
    assert recovered.snapshot == current(client, turn)
    assert recovered.snapshot.body == "可靠正文"
    assert recovered.result_text == command.result_text


def test_cross_scope_stale_writer_pause_and_terminal_effects_are_fenced(client: TestClient) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn)
    command = edit_at(initial, "本輪正文")
    other = start_turn(client)
    start_plan(client, other)
    workflow = plan_workflow(client)
    with pytest.raises(PlanStateError):
        client.portal.call(workflow.apply, other.writer, command)
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s, turn.writer.scope, writer_id=uuid4(), replaces_writer_id=turn.writer.writer_id
        ),
    )
    with pytest.raises(StaleWriterError):
        client.portal.call(workflow.apply, turn.writer, command)
    turn = replace(turn, writer=replacement)
    transact(client, lambda s: executions.request_pause(s, turn.writer.scope))
    result = client.portal.call(workflow.apply, turn.writer, command)
    assert result.snapshot.body == "本輪正文"
    transact(client, lambda s: executions.pause_execution(s, turn.writer))
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.apply, turn.writer, edit_at(result.snapshot, "遲到正文"))
    stop = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    client.portal.call(stop.stop, turn.writer, ExecutionStatus.CANCELLED)
    with pytest.raises(ExecutionStateError):
        client.portal.call(workflow.apply, turn.writer, command)
    assert current(client, turn) == result.snapshot


@pytest.mark.parametrize("body", [None, "", "新原文"])
def test_adoption_uses_completed_exchange_employee_frontier_and_keeps_nullable_winner(
    client: TestClient, body: str | None
) -> None:
    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    first_plan = start_plan(client, first, "前輪原文")
    exchange = settle(client, first, first_plan)
    assert adopted(client, file_id, exchange.employee_input.interview_sequence) == first_plan
    assert adopted(client, file_id, exchange.employee_input.interview_sequence - 1) is None
    second = start_turn(client, file_id=file_id)
    second_plan = start_plan(client, second, body)
    assert adopted(client, file_id) == first_plan
    second_exchange = settle(client, second, second_plan)
    assert adopted(client, file_id, exchange.employee_input.interview_sequence) == first_plan
    assert (
        adopted(client, file_id, second_exchange.employee_input.interview_sequence) == second_plan
    )
    assert adopted(client, file_id) == second_plan


@pytest.mark.parametrize("outcome", [ExecutionStatus.CANCELLED, ExecutionStatus.FAILED])
def test_cancelled_and_failed_candidates_do_not_gain_adoption(
    client: TestClient, outcome: ExecutionStatus
) -> None:
    first = start_turn(client)
    first_plan = start_plan(client, first, "正式前輪")
    settle(client, first, first_plan)
    later = start_turn(client, file_id=first.writer.scope.job_file_id)
    start_plan(client, later, "未完成候選")
    workflow = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    client.portal.call(workflow.stop, later.writer, outcome)
    assert adopted(client, first.writer.scope.job_file_id) == first_plan


def test_start_capture_reentry_reads_base_even_after_current_advances(client: TestClient) -> None:
    turn = start_turn(client)
    scope = turn.writer.scope
    bound = InterviewReadScope(scope.job_file_id, 1)
    initial = transact(client, lambda s: start_interview_plan(s, turn.writer, bound))
    result = client.portal.call(
        plan_workflow(client).apply, turn.writer, edit_at(initial, "本輪修改")
    )
    assert result.snapshot != initial
    assert transact(client, lambda s: start_interview_plan(s, turn.writer, bound)) == initial
    assert current(client, turn) == result.snapshot


def test_final_plan_position_failure_rolls_back_formal_jd_and_context(client: TestClient) -> None:
    turn = start_turn(client)
    initial = start_plan(client, turn)
    last = client.portal.call(
        plan_workflow(client).apply, turn.writer, edit_at(initial, "目前正文")
    )
    with pytest.raises(StalePlanPositionError):
        settle(client, turn, initial)
    assert_unfinished(client, turn)
    assert current(client, turn) == last.snapshot
    assert adopted(client, turn.writer.scope.job_file_id) is None
    settle(client, turn, last.snapshot)
    assert adopted(client, turn.writer.scope.job_file_id) == last.snapshot


def test_completion_commit_loss_and_later_turn_do_not_rewind_original_result(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "原完成正文")
    original = settle(client, turn, plan)
    later = start_turn(client, file_id=turn.writer.scope.job_file_id)
    later_plan = start_plan(client, later, "後輪完成正文")
    settle(client, later, later_plan)
    assert settle(client, turn, plan) == original
    assert adopted(client, turn.writer.scope.job_file_id) == later_plan
    assert (
        transact(
            client,
            lambda s: history.read_adopted_context(
                s, job_file_id=turn.writer.scope.job_file_id, role=AgentRole.JOB_CONSULTANT
            ),
        )
        == later.completed
    )
    with pytest.raises(PlanStateError):
        settle(client, turn, PlanSnapshot(replace(plan.position, revision_id=uuid4()), plan.body))
    with pytest.raises(ExecutionStateError):
        client.portal.call(plan_workflow(client).apply, turn.writer, edit_at(plan, "遲到修改"))


def test_completed_recovery_rejects_active_without_granting_eligibility(client: TestClient) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn)
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    with pytest.raises(ExecutionStateError):
        client.portal.call(
            completion.recover_completed, turn.writer, turn.completed, "原回覆", plan.position
        )
    assert transact(client, lambda s: executions.read_execution(s, turn.writer.scope)).status == (
        ExecutionStatus.ACTIVE
    )
    assert adopted(client, turn.writer.scope.job_file_id) is None


def test_completed_recovery_uses_original_exchange_head_and_writer_after_later_turn(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "原完成正文")
    original = settle(client, turn, plan)
    later = start_turn(client, file_id=turn.writer.scope.job_file_id)
    later_plan = start_plan(client, later, "後轮正文")
    settle(client, later, later_plan)
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    result = client.portal.call(
        completion.recover_completed,
        turn.writer,
        turn.completed,
        original.consultant_reply.interview_text,
        plan.position,
    )
    assert result == original
    assert adopted(client, turn.writer.scope.job_file_id) == later_plan
    with pytest.raises(StaleWriterError):
        client.portal.call(
            completion.recover_completed,
            replace(turn.writer, writer_id=uuid4()),
            turn.completed,
            original.consultant_reply.interview_text,
            plan.position,
        )
    with pytest.raises(PlanStateError):
        client.portal.call(
            completion.recover_completed,
            turn.writer,
            turn.completed,
            original.consultant_reply.interview_text,
            None,
        )


def test_final_transaction_exception_rolls_back_all_eligibility(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "候選正文")
    complete_histories = history.complete_context_histories

    async def fail_after_settlement(
        session: AsyncSession,
        writer: ExecutionWriter,
        positions: Mapping[AgentRole, ContextPosition],
    ) -> None:
        await complete_histories(session, writer, positions)
        raise RuntimeError("injected failure before commit")

    with monkeypatch.context() as fault:
        fault.setattr(history, "complete_context_histories", fail_after_settlement)
        with pytest.raises(RuntimeError, match="before commit"):
            settle(client, turn, plan)
    assert adopted(client, turn.writer.scope.job_file_id) is None
    assert transact(client, lambda s: executions.read_execution(s, turn.writer.scope)).status == (
        ExecutionStatus.ACTIVE
    )
    assert current(client, turn) == plan
    settle(client, turn, plan)
    assert adopted(client, turn.writer.scope.job_file_id) == plan


def test_plan_completion_and_cancel_race_has_one_whole_outcome(client: TestClient) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "候選正文")
    ready = Barrier(2)
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)

    def finishing() -> FormalInterviewExchange | None:
        ready.wait(timeout=10)
        try:
            return settle(client, turn, plan)
        except ExecutionStateError:
            return None

    def cancelling() -> ExecutionInfo:
        ready.wait(timeout=10)
        return client.portal.call(completion.stop, turn.writer, ExecutionStatus.CANCELLED)

    with ThreadPoolExecutor(max_workers=2) as pool:
        finishing_future = pool.submit(finishing)
        stopping_future = pool.submit(cancelling)
        exchange, result = finishing_future.result(), stopping_future.result()
    expected = ExecutionStatus.COMPLETED if exchange is not None else ExecutionStatus.CANCELLED
    assert result.status == expected
    assert adopted(client, turn.writer.scope.job_file_id) == (plan if exchange else None)


def test_operation_guard_scope_foreign_keys_and_whole_file_cascade(
    client: TestClient, database_connection: psycopg.Connection
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "不可變原文")
    result = client.portal.call(plan_workflow(client).apply, turn.writer, edit_at(plan, "保存正文"))
    other = start_turn(client)
    other_plan = start_plan(client, other, "別案正文")
    scope = turn.writer.scope
    for statement in (
        "UPDATE interview_plan_operations SET body='被改寫' WHERE job_file_id=%s",
        "DELETE FROM interview_plan_operations WHERE job_file_id=%s",
    ):
        with pytest.raises(psycopg.errors.CheckViolation):
            database_connection.execute(statement, (scope.job_file_id,))
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        database_connection.execute(
            "UPDATE interview_plan_candidates SET current_revision_id=%s "
            "WHERE job_file_id=%s AND execution_id=%s",
            (other_plan.position.revision_id, scope.job_file_id, scope.execution_id),
        )
    settle(client, turn, result.snapshot)
    assert client.delete(f"/api/job-files/{scope.job_file_id}").status_code == 204
    for table in ("interview_plan_operations", "interview_plan_candidates"):
        assert database_connection.execute(
            sql.SQL("SELECT count(*) FROM {} WHERE job_file_id=%s").format(sql.Identifier(table)),
            (scope.job_file_id,),
        ).fetchone() == (0,)
    assert current(client, other) == other_plan


def test_qualification_requires_both_completed_execution_and_matching_formal_exchange(
    client: TestClient,
) -> None:
    no_exchange = start_turn(client)
    start_plan(client, no_exchange, "只有completed")
    transact(
        client,
        lambda s: executions.finish_execution(s, no_exchange.writer, ExecutionStatus.COMPLETED),
    )
    assert adopted(client, no_exchange.writer.scope.job_file_id) is None
    active_exchange = start_turn(client)
    start_plan(client, active_exchange, "只有正式exchange")
    exchange = transact(
        client,
        lambda s: record_formal_interview(s, active_exchange.writer, reply_text="正式候選回覆"),
    )
    metadata = transact(
        client,
        lambda s: interviews.list_formal_exchange_positions(
            s,
            InterviewReadScope(
                active_exchange.writer.scope.job_file_id, exchange.employee_input.interview_sequence
            ),
        ),
    )
    assert [(position.execution_id, position.employee_input_sequence) for position in metadata] == [
        (active_exchange.writer.scope.execution_id, exchange.employee_input.interview_sequence)
    ]
    assert adopted(client, active_exchange.writer.scope.job_file_id) is None


def test_adoption_returns_one_plan_without_materializing_all_formal_turns(
    client: TestClient,
) -> None:
    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    latest = start_plan(client, first, "較早正文")
    exchange = settle(client, first, latest)
    for body in ("中間正文", ""):
        turn = start_turn(client, file_id=file_id)
        latest = start_plan(client, turn, body)
        exchange = settle(client, turn, latest)
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        actual = transact(
            client,
            lambda session: read_adopted_plan(
                session, InterviewReadScope(file_id, exchange.employee_input.interview_sequence)
            ),
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert actual == latest
    # 資格、排序與勝出列都在 DB 內完成；空正文仍是最新正式結果。
    assert len(statements) == 1
    assert "LIMIT" in statements[0]
    assert "VALUES" not in statements[0]


def test_completed_batch_query_restricts_file_kind_and_selected_ids(client: TestClient) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn)
    settle(client, turn, plan)
    other = start_turn(client)
    other_plan = start_plan(client, other)
    settle(client, other, other_plan)
    file_id = turn.writer.scope.job_file_id
    memory = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)

    async def complete_memory(session: AsyncSession) -> None:
        await executions.admit_execution(session, memory)
        writer = await executions.claim_writer(session, memory, writer_id=uuid4())
        await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)

    transact(client, complete_memory)
    found = transact(
        client,
        lambda s: executions.read_completed_consultant_execution_ids(
            s,
            file_id,
            (
                turn.writer.scope.execution_id,
                other.writer.scope.execution_id,
                memory.execution_id,
                uuid4(),
            ),
        ),
    )
    assert found == frozenset({turn.writer.scope.execution_id})
    assert (
        transact(
            client, lambda s: executions.read_completed_consultant_execution_ids(s, file_id, ())
        )
        == frozenset()
    )


def test_new_start_inherits_fixed_frontier_and_old_capability_has_no_new_candidate(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "採用基底")
    exchange = settle(client, turn, plan)
    file_id = turn.writer.scope.job_file_id
    old = start_turn(client, file_id=file_id)
    complete(client, old)
    assert current(client, old) is None
    assert adopted(client, file_id) == plan
    later = start_turn(client, file_id=file_id)
    base = transact(
        client,
        lambda s: start_interview_plan(
            s,
            later.writer,
            InterviewReadScope(file_id, exchange.employee_input.interview_sequence),
        ),
    )
    assert base.body == "採用基底"
    assert base.position.execution_id == later.writer.scope.execution_id
    with pytest.raises(PlanStateError):
        client.portal.call(
            plan_workflow(client).apply, later.writer, edit_at(plan, "錯用另一輪位置")
        )
    clear = client.portal.call(plan_workflow(client).apply, later.writer, edit_at(base, ""))
    settle(client, later, clear.snapshot)
    assert adopted(client, file_id) == clear.snapshot


def test_completed_recovery_rejects_different_exact_context_or_reply(client: TestClient) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn)
    exchange = settle(client, turn, plan)
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    with pytest.raises(HistoryConflictError):
        client.portal.call(
            completion.recover_completed,
            turn.writer,
            replace(turn.completed, checkpoint_id="another-checkpoint"),
            exchange.consultant_reply.interview_text,
            plan.position,
        )
    with pytest.raises(InterviewCompletionConflictError):
        client.portal.call(
            completion.recover_completed,
            turn.writer,
            turn.completed,
            "不同正式回覆",
            plan.position,
        )
    assert adopted(client, turn.writer.scope.job_file_id) == plan


def test_active_plan_read_rejects_cancelled_execution_but_retains_terminal_read(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "取消後只留恢復證據")
    completion = ConsultantCompletionWorkflow(client.app.state.database.sessions)
    client.portal.call(completion.stop, turn.writer, ExecutionStatus.CANCELLED)
    with pytest.raises(ExecutionStateError):
        client.portal.call(plan_workflow(client).read_active, turn.writer)
    assert current(client, turn) == plan


def test_active_plan_read_fences_replaced_writer_and_keeps_pending_pause(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "當輪未釐清")
    replacement = transact(
        client,
        lambda s: executions.claim_writer(
            s,
            turn.writer.scope,
            writer_id=uuid4(),
            replaces_writer_id=turn.writer.writer_id,
        ),
    )
    with pytest.raises(StaleWriterError):
        client.portal.call(plan_workflow(client).read_active, turn.writer)
    transact(client, lambda s: executions.request_pause(s, replacement.scope))
    assert client.portal.call(plan_workflow(client).read_active, replacement) == plan


@pytest.mark.parametrize("fail_read", [False, True])
def test_active_plan_read_holds_file_and_writer_rows_until_same_transaction_finishes(
    client: TestClient,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
    fail_read: bool,
) -> None:
    turn = start_turn(client)
    plan = start_plan(client, turn, "要投影的完整正文")
    original_read = service.read_current
    scope = turn.writer.scope
    checked = False

    async def inspect_locked_read(
        session: AsyncSession, job_file_id: UUID, execution_id: UUID
    ) -> PlanSnapshot | None:
        nonlocal checked
        assert session.in_transaction()
        for query, args in (
            ("SELECT 1 FROM job_files WHERE job_file_id=%s FOR UPDATE NOWAIT", (job_file_id,)),
            (
                "SELECT 1 FROM executions WHERE job_file_id=%s AND execution_id=%s "
                "FOR UPDATE NOWAIT",
                (job_file_id, execution_id),
            ),
        ):
            try:
                with database_connection.transaction():
                    database_connection.execute(query, args)
            except psycopg.errors.LockNotAvailable:
                pass
            else:
                raise RuntimeError("The active-plan read does not retain its row locks")
        checked = True
        if fail_read:
            raise RuntimeError("synthetic active-plan read unavailable")
        return await original_read(session, job_file_id, execution_id)

    monkeypatch.setattr(service, "read_current", inspect_locked_read)
    if fail_read:
        with pytest.raises(RuntimeError, match="active-plan read unavailable"):
            client.portal.call(plan_workflow(client).read_active, turn.writer)
    else:
        assert client.portal.call(plan_workflow(client).read_active, turn.writer) == plan
    assert checked
    # Both normal completion and rollback release the actual locks to another connection.
    with database_connection.transaction():
        assert database_connection.execute(
            "SELECT 1 FROM job_files WHERE job_file_id=%s FOR UPDATE NOWAIT",
            (scope.job_file_id,),
        ).fetchone()
        assert database_connection.execute(
            "SELECT 1 FROM executions WHERE job_file_id=%s AND execution_id=%s FOR UPDATE NOWAIT",
            (scope.job_file_id, scope.execution_id),
        ).fetchone()
