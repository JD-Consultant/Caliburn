"""Fixed JD source comparison on PostgreSQL, through actual completion and publication owners."""

from dataclasses import replace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError
from caliburn.features.job_description.sources import (
    AddJdSource,
    InterviewSource,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from caliburn.workflows.jd_changes import JdChangesWorkflow, UnsupportedJdSourceKindError
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


def test_source_diff_is_pinned_same_identity_with_related_changes_and_no_alignment(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    source_ids = [complete(client, first).employee_input.source_id]
    for _ in range(2):
        source_ids.append(
            complete(client, start_turn(client, file_id=file_id)).employee_input.source_id
        )

    async def scenario():
        sessions = client.app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)

        async def batch(index):
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            stage = await memory.start(writer, source_ids[index])
            assert stage is not None
            return writer, stage

        writer, stage = await batch(0)
        situation = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("盤點", "庫存", "每月盤點。"),
                reference_ids=frozenset({source_ids[0]}),
            ),
        )
        phase = await memory.handoff(writer, situation.position, uuid4())
        understanding = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "庫存理解", "理解正文不變。"),
                reference_ids=frozenset({situation.object_id}),
            ),
        )
        old_snapshot = await memory.publish(writer, understanding.position, uuid4())
        writer, stage = await batch(1)
        changed = await memory.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                situation.object_id,
                MemoryContentChanges(title="季度盤點", body="每季盤點。"),
            ),
        )
        phase = await memory.handoff(writer, changed.position, uuid4())
        pinned = await memory.publish(writer, phase, uuid4())
        return old_snapshot, pinned, situation.object_id, understanding.object_id, batch

    # Keep the async batch closure on the TestClient portal's single event loop.
    old_snapshot, pinned, situation_id, understanding_id, batch = client.portal.call(scenario)
    turn = start_turn(client, file_id=file_id)
    binding = PublishedMemoryRead(turn.writer.scope, pinned.snapshot_id, 7)
    jd = JdCandidateWorkflow(client.app.state.database.sessions)
    old = transact(
        client,
        lambda s: candidate_queries.read_snapshot_object(
            s, file_id, old_snapshot.snapshot_id, understanding_id
        ),
    )
    position = client.portal.call(
        jd.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            (
                AddJdSource(
                    MemorySource(
                        MemorySourceLayer.WORK_UNDERSTANDING,
                        old_snapshot.snapshot_id,
                        old.object_id,
                        old.revision_id,
                    )
                ),
            ),
        ),
    )
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(s, file_id, position.revision_id),
    )
    citation = f"citation_{references[0].citation_id.hex}"
    reader = JdChangesWorkflow(client.app.state.database.sessions)
    result = client.portal.call(reader.read_source, binding, citation)
    assert result.changes[0].before.content == result.changes[0].after.content
    assert len(result.changes) == 2
    assert result.changes[1].before.content.body == "每月盤點。"
    assert result.changes[1].after.content.body == "每季盤點。"
    assert result.changes[1].before_interviews == (2,)
    from functools import partial

    from caliburn.transport.model_tools.jd_changes import (
        project_jd_source_changes,
        read_jd_source_changes,
    )

    output = project_jd_source_changes(result)
    assert "-每月盤點。" in output and "+每季盤點。" in output
    assert "理解正文不變。" not in output
    assert "可讀 target_title：庫存管理" in output
    assert "未解除待核對" in output
    limited = client.portal.call(
        partial(read_jd_source_changes, reader, binding, citation, max_result_characters=5)
    )
    assert limited.startswith("rejected: read_limit_exceeded")
    assert "每月盤點" not in limited

    async def late_publication():
        writer, stage = await batch(2)
        memory = MemoryCandidateWorkflow(client.app.state.database.sessions)
        deleted = await memory.edit(
            writer, DeleteMemoryObject(uuid4(), stage, MemoryLayer.WORK_SITUATION, situation_id)
        )
        recreated = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                deleted.position,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("季度盤點", "新物件", "不得替代舊身分。"),
            ),
        )
        phase = await memory.handoff(writer, recreated.position, uuid4())
        deleted_understanding = await memory.edit(
            writer,
            DeleteMemoryObject(uuid4(), phase, MemoryLayer.WORK_UNDERSTANDING, understanding_id),
        )
        recreated_understanding = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                deleted_understanding.position,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "全新理解", "同名理解也不得替代舊身分。"),
            ),
        )
        return await memory.publish(writer, recreated_understanding.position, uuid4())

    late = client.portal.call(late_publication)
    assert client.portal.call(reader.read_source, binding, citation) == result
    assert (
        transact(
            client,
            lambda s: source_persistence.read_source_references(s, file_id, position.revision_id),
        )
        == references
    )
    with pytest.raises(MemoryRevisionNotFoundError):
        client.portal.call(reader.read_source, replace(binding, snapshot_id=uuid4()), citation)
    with pytest.raises(MemoryRevisionNotFoundError):
        client.portal.call(reader.read_source, replace(binding, snapshot_id=None), citation)
    return_to_late = client.portal.call(
        reader.read_source, replace(binding, snapshot_id=late.snapshot_id), citation
    )
    assert return_to_late.changes[1].after is None
    assert return_to_late.changes[0].after is None
    assert "同一物件已不在本 Turn 固定 Memory" in project_jd_source_changes(return_to_late)
    assert "不得替代舊身分" not in project_jd_source_changes(return_to_late)
    unavailable = client.portal.call(
        read_jd_source_changes, reader, replace(binding, snapshot_id=uuid4()), citation
    )
    assert unavailable.startswith("rejected: source_not_available")
    outside_frontier = client.portal.call(
        read_jd_source_changes,
        reader,
        replace(binding, interview_through_sequence=1),
        citation,
    )
    assert outside_frontier.startswith("rejected: scope_not_allowed")

    async def failed_storage(*args, **kwargs):
        raise OSError("storage failed")

    with monkeypatch.context() as patch:
        patch.setattr(candidate_queries, "read_snapshot", failed_storage)
        with pytest.raises(OSError, match="storage failed"):
            client.portal.call(read_jd_source_changes, reader, binding, citation)


def test_interview_diff_points_to_qualified_sequence_or_current_input_and_never_forges_diff(
    client: TestClient,
) -> None:
    previous = start_turn(client)
    formal = complete(client, previous).employee_input
    turn = start_turn(client, file_id=previous.writer.scope.job_file_id)
    sessions = client.app.state.database.sessions
    current = transact(
        client,
        lambda s: interviews.read_execution_input(
            s,
            job_file_id=turn.writer.scope.job_file_id,
            execution_id=turn.writer.scope.execution_id,
        ),
    )
    jd = JdCandidateWorkflow(sessions)
    position = client.portal.call(
        jd.edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE),
            tuple(
                AddJdSource(InterviewSource(source_id))
                for source_id in (formal.source_id, current.source_id)
            ),
        ),
    )
    references = transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, turn.writer.scope.job_file_id, position.revision_id
        ),
    )
    binding = PublishedMemoryRead(turn.writer.scope, None, 3)
    reader = JdChangesWorkflow(sessions)
    for reference in references:
        message = (
            "正式序號 2" if reference.source.source_id == formal.source_id else "current_input"
        )
        with pytest.raises(UnsupportedJdSourceKindError, match=message):
            client.portal.call(reader.read_source, binding, f"citation_{reference.citation_id.hex}")
        from caliburn.transport.model_tools.jd_changes import read_jd_source_changes

        rejection = client.portal.call(
            read_jd_source_changes, reader, binding, f"citation_{reference.citation_id.hex}"
        )
        assert rejection.startswith("rejected: source_kind_not_supported")
        assert message in rejection

    other = start_turn(client)
    with pytest.raises(JdReadTargetNotFoundError):
        client.portal.call(
            reader.read_source,
            PublishedMemoryRead(other.writer.scope, None, 1),
            f"citation_{references[0].citation_id.hex}",
        )
    client.portal.call(
        ConsultantCompletionWorkflow(sessions).stop, turn.writer, ExecutionStatus.CANCELLED
    )
    with pytest.raises(ExecutionStateError):
        client.portal.call(reader.read_source, binding, f"citation_{references[0].citation_id.hex}")
