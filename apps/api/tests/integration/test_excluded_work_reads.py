"""Excluded-work reads use the existing fixed Memory batch and formal Turn boundaries."""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews import service as interview_service
from caliburn.features.work_memory.batch_models import MemoryBatchWork
from caliburn.features.work_memory.candidates import MemoryCandidateStateError
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.excluded_work_reads import ExcludedWorkReadTools
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from caliburn.workflows.memory_reads import (
    CandidateMemoryRead,
    MemoryReadWorkflow,
    PublishedMemoryRead,
)
from caliburn.workflows.occupation_reference_reads import ExcludedWorkReadWorkflow
from tests.integration.test_occupation_reference_workflow import (
    finish,
    new_writer,
    transact,
    workflow,
)

pytestmark = pytest.mark.postgres


def start_batch(client: TestClient, excluded_work: tuple[str, ...]) -> MemoryBatchWork:
    references, _ = workflow(client)
    writer = new_writer(client)
    client.portal.call(references.start, writer)
    if excluded_work:
        change = client.portal.call(
            references.prepare_excluded_work, writer, excluded_work, (), uuid4()
        )
        client.portal.call(references.execute, writer, change)
    consolidation = MemoryConsolidationWorkflow(client.app.state.database.sessions)
    client.portal.call(consolidation.request, writer, uuid4())
    finish(client, writer, ExecutionStatus.COMPLETED)

    async def claim() -> MemoryBatchWork:
        work = await consolidation.claim(writer.scope.job_file_id, writer_id=uuid4())
        assert work is not None
        return work

    return client.portal.call(claim)


def test_trigger_employee_boundary_includes_its_exclusions_before_the_reply_sequence(
    client: TestClient,
) -> None:
    work = start_batch(client, ("不負責部署", "不負責採購"))
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    binding = CandidateMemoryRead(work.writer.scope, work.position)
    frontier = transact(
        client, lambda s: interviews.read_history_frontier(s, work.writer.scope.job_file_id)
    )
    assert frontier == work.source_window.through_sequence + 1
    assert client.portal.call(reader.read, binding) == ("不負責部署", "不負責採購")
    candidates = MemoryCandidateWorkflow(client.app.state.database.sessions)
    b2 = client.portal.call(candidates.handoff, work.writer, work.position, uuid4())
    assert client.portal.call(reader.read, CandidateMemoryRead(work.writer.scope, b2)) == (
        "不負責部署",
        "不負責採購",
    )
    with pytest.raises(MemoryCandidateStateError):
        client.portal.call(reader.read, binding)


@pytest.mark.parametrize(
    ("add", "remove", "latest"),
    [
        (("不負責採購",), (), ["不負責部署", "不負責採購"]),
        ((), ("不負責部署",), []),
    ],
)
def test_later_add_or_removal_stays_outside_the_restored_batch_frontier(
    client: TestClient, add: tuple[str, ...], remove: tuple[str, ...], latest: list[str]
) -> None:
    work = start_batch(client, ("不負責部署",))
    references, _ = workflow(client)
    later = new_writer(client, work.writer.scope.job_file_id)
    client.portal.call(references.start, later)
    change = client.portal.call(references.prepare_excluded_work, later, add, remove, uuid4())
    assert client.portal.call(references.execute, later, change)["excluded_work"] == latest
    finish(client, later, ExecutionStatus.COMPLETED)
    consolidation = MemoryConsolidationWorkflow(client.app.state.database.sessions)

    async def recover() -> MemoryBatchWork:
        recovered = await consolidation.claim(work.writer.scope.job_file_id, writer_id=uuid4())
        assert recovered is not None
        return recovered

    recovered = client.portal.call(recover)
    assert recovered.source_window == work.source_window
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    assert client.portal.call(
        reader.read, CandidateMemoryRead(recovered.writer.scope, recovered.position)
    ) == ("不負責部署",)
    candidates = MemoryCandidateWorkflow(client.app.state.database.sessions)
    b2 = client.portal.call(candidates.handoff, recovered.writer, recovered.position, uuid4())
    rebuilt = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    assert client.portal.call(rebuilt.read, CandidateMemoryRead(recovered.writer.scope, b2)) == (
        "不負責部署",
    )
    newest = new_writer(client, later.scope.job_file_id)
    assert client.portal.call(references.start, newest).state.excluded_work == tuple(latest)


@pytest.mark.parametrize(
    ("status", "formal"),
    [
        (ExecutionStatus.CANCELLED, True),
        (ExecutionStatus.FAILED, True),
        (ExecutionStatus.COMPLETED, False),
    ],
)
def test_a_formal_exchange_and_successful_execution_are_both_required(
    client: TestClient, status: ExecutionStatus, formal: bool
) -> None:
    work = start_batch(client, ("不負責部署",))
    references, _ = workflow(client)
    invalid = new_writer(client, work.writer.scope.job_file_id)
    client.portal.call(references.start, invalid)
    change = client.portal.call(
        references.prepare_excluded_work, invalid, ("不負責採購",), (), uuid4()
    )
    client.portal.call(references.execute, invalid, change)
    finish(client, invalid, status, formal)
    advisor = new_writer(client, invalid.scope.job_file_id)
    frontier = transact(
        client, lambda s: interviews.read_history_frontier(s, advisor.scope.job_file_id)
    )
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    assert client.portal.call(reader.read, PublishedMemoryRead(advisor.scope, None, frontier)) == (
        "不負責部署",
    )


def test_live_consultant_candidate_cannot_leak_into_memory_reads(client: TestClient) -> None:
    work = start_batch(client, ("不負責部署",))
    references, _ = workflow(client)
    active = new_writer(client, work.writer.scope.job_file_id)
    client.portal.call(references.start, active)
    change = client.portal.call(
        references.prepare_excluded_work, active, ("不負責採購",), ("不負責部署",), uuid4()
    )
    client.portal.call(references.execute, active, change)
    # Even an existing formal exchange is insufficient while the Turn is still active.
    exchange = transact(
        client,
        lambda s: interview_service.formalize_exchange(
            s,
            job_file_id=active.scope.job_file_id,
            execution_id=active.scope.execution_id,
            reply_text="合成回覆",
        ),
    )
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    binding = PublishedMemoryRead(active.scope, None, exchange.consultant_reply.interview_sequence)
    assert client.portal.call(reader.read, binding) == ("不負責部署",)
    assert client.portal.call(
        reader.read, CandidateMemoryRead(work.writer.scope, work.position)
    ) == ("不負責部署",)
    assert client.portal.call(references.read, active)["excluded_work"] == ["不負責採購"]


def test_fixed_job_files_and_empty_state_remain_isolated(client: TestClient) -> None:
    first = start_batch(client, ("不負責部署",))
    second = start_batch(client, ("不負責採購",))
    empty = start_batch(client, ())
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    for work, expected in [(first, ("不負責部署",)), (second, ("不負責採購",)), (empty, ())]:
        assert (
            client.portal.call(reader.read, CandidateMemoryRead(work.writer.scope, work.position))
            == expected
        )


def test_superseded_generation_cannot_read_but_the_restored_stage_can(client: TestClient) -> None:
    work = start_batch(client, ("不負責部署",))
    candidates = MemoryCandidateWorkflow(client.app.state.database.sessions)
    restored = client.portal.call(
        candidates.restore, work.writer, work.position, work.position, uuid4()
    )
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    with pytest.raises(MemoryCandidateStateError):
        client.portal.call(reader.read, CandidateMemoryRead(work.writer.scope, work.position))
    assert client.portal.call(reader.read, CandidateMemoryRead(work.writer.scope, restored)) == (
        "不負責部署",
    )


def test_inactive_memory_and_consultant_bindings_reject_instead_of_returning_empty(
    client: TestClient,
) -> None:
    work = start_batch(client, ("不負責部署",))
    reader = ExcludedWorkReadWorkflow(client.app.state.database.sessions)
    candidates = MemoryCandidateWorkflow(client.app.state.database.sessions)
    client.portal.call(candidates.discard, work.writer, work.position, uuid4())
    with pytest.raises(ExecutionStateError):
        client.portal.call(reader.read, CandidateMemoryRead(work.writer.scope, work.position))
    advisor = new_writer(client, work.writer.scope.job_file_id)
    binding = PublishedMemoryRead(advisor.scope, None, work.source_window.through_sequence)
    finish(client, advisor, ExecutionStatus.CANCELLED, False)
    with pytest.raises(ExecutionStateError):
        client.portal.call(reader.read, binding)


def test_tool_json_reads_fixed_b1_b2_exclusions_without_copying_them_into_memory(
    client: TestClient,
) -> None:
    work = start_batch(client, ("不負責部署",))
    sessions = client.app.state.database.sessions
    b1 = CandidateMemoryRead(work.writer.scope, work.position)
    tools = ExcludedWorkReadTools(ExcludedWorkReadWorkflow(sessions), b1)
    assert json.loads(client.portal.call(tools.invoke, "read_excluded_work", "{}")) == {
        "excluded_work": ["不負責部署"]
    }
    references, _ = workflow(client)
    later = new_writer(client, work.writer.scope.job_file_id)
    client.portal.call(references.start, later)
    change = client.portal.call(
        references.prepare_excluded_work, later, ("不負責採購",), ("不負責部署",), uuid4()
    )
    client.portal.call(references.execute, later, change)
    finish(client, later, ExecutionStatus.COMPLETED)
    candidates = MemoryCandidateWorkflow(sessions)
    phase = client.portal.call(candidates.handoff, work.writer, work.position, uuid4())
    assert json.loads(client.portal.call(tools.invoke, "read_excluded_work", "{}"))["code"] == (
        "target_stale"
    )
    b2 = CandidateMemoryRead(work.writer.scope, phase)
    rebuilt = ExcludedWorkReadTools(ExcludedWorkReadWorkflow(sessions), b2)
    assert json.loads(client.portal.call(rebuilt.invoke, "read_excluded_work", "{}")) == {
        "excluded_work": ["不負責部署"]
    }
    for name, arguments, code in [
        ("read_excluded_work", '{"through_sequence":999}', "invalid_arguments"),
        ("read_excluded_work", json.dumps({"job_file_id": str(uuid4())}), "invalid_arguments"),
        ("select_occupation_references", '{"reference_ids":[]}', "scope_not_allowed"),
        ("update_excluded_work", '{"add":[],"remove":["不負責部署"]}', "scope_not_allowed"),
    ]:
        rejection = json.loads(client.portal.call(rebuilt.invoke, name, arguments))
        assert rejection["status"] == "rejected"
        assert rejection["code"] == code
    memory = MemoryReadWorkflow(sessions)
    assert client.portal.call(memory.read_map, b2, MemoryLayer.WORK_SITUATION) == ()
    assert client.portal.call(memory.read_map, b2, MemoryLayer.WORK_UNDERSTANDING) == ()
    assert json.loads(client.portal.call(rebuilt.invoke, "read_excluded_work", "{}")) == {
        "excluded_work": ["不負責部署"]
    }
