"""隔離真 PG owner＋create_agent：工具故障與取消不採用候選。"""

from dataclasses import replace
from functools import partial
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.agent_execution.native_agent import run_native_agent
from caliburn.agents.job_consultant.tools import ConsultantTools
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews import queries
from caliburn.features.job_description import candidate_service
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.transport.model_tools import jd_writes
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.executions.failure_boundary import run_with_failure_boundary
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.compound_writes import execute_prepared_jd_edit
from caliburn.workflows.job_description.item_creation import JdItemCreationWorkflow
from caliburn.workflows.job_description.item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.job_description.item_movement import JdItemMovementWorkflow
from caliburn.workflows.job_description.item_revision import JdItemRevisionWorkflow
from caliburn.workflows.job_description.profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.job_description.task_writes import JdTaskWriteWorkflow
from caliburn.workflows.work_memory.reads import PublishedMemoryRead
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at
from tests.integration.test_consultant_completion import start_turn, transact
from tests.unit.test_tool_failure_classification import VALID_PROFILE, internal_fault

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("phase", ["prepare", "execute", "render", "restore", "cancel"])
def test_tool_internal_fault_and_cancel_settle_original_turn(
    client, database_settings, monkeypatch, phase
):
    turn = start_turn(client, with_candidate=False)
    sessions = client.app.state.database.sessions
    candidates = JdCandidateWorkflow(sessions)
    start = client.portal.call(candidates.start, turn.writer)
    completion = ConsultantCompletionWorkflow(sessions)
    binding = PublishedMemoryRead(turn.writer.scope, None, 1)
    profile = JdProfileWriteWorkflow(sessions)
    owner_execute = partial(execute_prepared_jd_edit, sessions)
    committed_candidates = []

    if phase == "prepare":
        original_prepare = profile.prepare

        async def prepare(*args, **kwargs):
            # 真 workflow 完成來源／候選核對後，注入內部驗證故障。
            await original_prepare(*args, **kwargs)
            internal_fault()

        monkeypatch.setattr(profile, "prepare", prepare)

    async def execute(writer, prepared):
        result = await owner_execute(writer, prepared)
        committed_candidates.append(await candidates.read(writer.scope))
        if phase == "execute":
            internal_fault()
        if phase == "cancel":
            await completion.stop(writer, ExecutionStatus.CANCELLED)
        return result

    tools = JdWriteTools(
        profile,
        JdTaskWriteWorkflow(sessions),
        binding,
        turn.writer,
        references=JdModelReferences(sessions, turn.writer.scope.job_file_id),
        execute_edit=execute,
        creations=JdItemCreationWorkflow(sessions),
        revisions=JdItemRevisionWorkflow(sessions),
        deletions=JdItemDeletionWorkflow(sessions),
        movements=JdItemMovementWorkflow(sessions),
    )
    if phase == "render":

        async def render(*args):
            internal_fault()

        monkeypatch.setattr(jd_writes, "render_jd_write_result", render)
    if phase == "restore":
        from caliburn.agents.job_consultant import tools as composition

        original_snapshot = composition.snapshot_jd_write

        def corrupt(prepared):
            saved = original_snapshot(prepared)
            saved["payload"] = "{}"
            return saved

        monkeypatch.setattr(composition, "snapshot_jd_write", corrupt)

    first = response_at(1, tools=1)
    first.output[-1].name = "revise_jd_profile"
    first.output[-1].arguments = VALID_PROFILE
    probe = LoopProbe([first, response_at(2, final=True)])

    async def unused(*args):
        raise AssertionError("unrelated tool")

    empty = SimpleNamespace(definitions=lambda: [], invoke=unused, execute=unused)
    composition = ConsultantTools(empty, empty, tools, empty, empty, empty)
    failures = []

    async def ensure_active():
        async with sessions.begin() as session:
            await executions.lock_active_writer(session, turn.writer)

    async def run(writer):
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        async with AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer()
        ) as saver:
            await saver.setup()
            runtime = probe.runtime()
            return await run_native_agent(
                saver,
                thread_id=str(uuid4()),
                request=initial_request(),
                runtime=replace(runtime, ensure_active=ensure_active),
                tools=composition.standard_tools(ensure_active),
                unknown_tool_output="unknown",
                max_tool_calls=2,
                max_model_steps=2,
            )

    async def settle(writer, error):
        failures.append(error)
        return await completion.stop(writer, ExecutionStatus.FAILED)

    outcome = client.portal.call(
        partial(run_with_failure_boundary, turn.writer, run=run, settle_failure=settle)
    )
    expected = ExecutionStatus.CANCELLED if phase == "cancel" else ExecutionStatus.FAILED
    assert outcome.status == expected
    assert (
        transact(client, lambda s: executions.read_execution(s, turn.writer.scope)).status
        == expected
    )
    assert len(probe.requests) == 1
    assert len(failures) == 1
    if phase != "cancel":
        assert str(failures[0]) == "Internal tool validation failed"
    assert bool(committed_candidates) == (phase in ("execute", "render", "cancel"))
    if committed_candidates:
        assert committed_candidates[0].profile.job_title == "工程師"
        assert committed_candidates[0].position.revision_id != start.revision_id
    with pytest.raises(CandidateStateError):
        transact(
            client,
            lambda s: candidate_service.read_position(
                s, turn.writer.scope.job_file_id, turn.writer.scope.execution_id
            ),
        )
    formal = client.get(f"/api/job-files/{turn.writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(start.base_revision_id)
    assert (
        transact(client, lambda s: queries.read_history_frontier(s, turn.writer.scope.job_file_id))
        == 1
    )
