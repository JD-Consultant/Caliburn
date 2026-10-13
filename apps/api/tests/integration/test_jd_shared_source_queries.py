"""Shared fixed-source reads need no active A and retain Memory owner validation."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.source_changes import AddJdSource, ReviseJdSources
from caliburn.features.job_description.sources import (
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    MemorySource,
    MemorySourceLayer,
    SourceTargetKind,
)
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    MemoryPermissionError,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import (
    MemoryContent,
    MemoryContentChanges,
    ReferenceChanges,
)
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.evidence import JdEvidenceWorkflow, MemoryEvidence
from caliburn.workflows.job_description.source_queries import (
    read_fixed_memory_source,
    read_memory_source_changes,
    read_memory_source_metadata_batch,
)
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


async def read_memory_source_titles(session, *, source, **scope):
    metadata = await read_memory_source_metadata_batch(session, sources=(source,), **scope)
    item = metadata[source]
    return item.target_title, item.historical_title, item.source_changed


def test_interview_overview_reads_one_header_batch_without_original_bodies(
    client: TestClient,
) -> None:
    turn = start_turn(client)
    file_id = turn.writer.scope.job_file_id
    messages = client.get(f"/api/job-files/{file_id}/interviews").json()["messages"]
    opening_id = UUID(messages[0]["source_id"])
    accepted_id = transact(
        client,
        lambda session: interviews.read_execution_input_source_id(
            session, job_file_id=file_id, execution_id=turn.writer.scope.execution_id
        ),
    )
    jd = JdCandidateWorkflow(client.app.state.database.sessions)
    position = turn.candidate
    for field, source_id in (
        (ProfileField.JOB_TITLE, opening_id),
        (ProfileField.PURPOSE, accepted_id),
        (ProfileField.REPORTS_TO, opening_id),
    ):
        position = client.portal.call(
            jd.edit,
            turn.writer,
            position.scope,
            ReviseJdSources(
                uuid4(),
                position.revision_id,
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field),
                (AddJdSource(InterviewSource(source_id)),),
            ),
        )
    complete(client, replace(turn, candidate=position))
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        overview = client.portal.call(
            JdEvidenceWorkflow(client.app.state.database.sessions).read_overview, file_id
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert sorted(entry.source_label for entry in overview.references) == [
        "訪談序號 1 · 系統開場",
        "訪談序號 1 · 系統開場",
        "訪談序號 2 · 員工",
    ]
    source_reads = [statement for statement in statements if "interview_texts" in statement]
    assert len(source_reads) == 1
    assert "interview_texts.interview_text" not in source_reads[0]


@dataclass(frozen=True)
class SourceComparison:
    job_file_id: UUID
    source: MemorySource
    snapshot_id: UUID
    interview_through_sequence: int

    def reference(self) -> JdSourceReference:
        return JdSourceReference(
            uuid4(),
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
            self.source,
            needs_review=True,
        )


@pytest.fixture
def comparison(client: TestClient) -> Iterator[SourceComparison]:
    first_turn = start_turn(client)
    file_id = first_turn.writer.scope.job_file_id
    first_input = complete(client, first_turn).employee_input
    second_input = complete(client, start_turn(client, file_id=file_id)).employee_input

    async def publish() -> SourceComparison:
        sessions = client.app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)

        async def batch(source_id: UUID):
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            stage = await memory.start(writer, source_id)
            assert stage is not None
            return writer, stage

        writer, stage = await batch(first_input.source_id)
        created = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("每月盤點", "盤點情境", "每月核對庫存。"),
                reference_ids=frozenset({first_input.source_id}),
            ),
        )
        phase = await memory.handoff(writer, created.position, uuid4())
        original = await publish_memory_owner_fixture(memory.sessions, writer, phase, uuid4())
        async with sessions() as session:
            selected = await candidate_queries.read_snapshot_object(
                session, file_id, original.snapshot_id, created.object_id
            )

        writer, stage = await batch(second_input.source_id)
        revised = await memory.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                created.object_id,
                MemoryContentChanges(title="季度盤點", body="每季核對庫存。"),
            ),
        )
        phase = await memory.handoff(writer, revised.position, uuid4())
        current = await publish_memory_owner_fixture(memory.sessions, writer, phase, uuid4())
        return SourceComparison(
            file_id,
            MemorySource(
                MemorySourceLayer.WORK_SITUATION,
                original.snapshot_id,
                selected.object_id,
                selected.revision_id,
            ),
            current.snapshot_id,
            current.covered_through_sequence,
        )

    yield client.portal.call(publish)


def test_shared_queries_read_fixed_source_without_an_active_turn_or_writes(
    client: TestClient, comparison: SourceComparison
) -> None:
    reference = comparison.reference()

    async def read(session: AsyncSession) -> None:
        # PG itself rejects any attempted write by these queries.
        await session.execute(text("SET TRANSACTION READ ONLY"))
        original = await read_fixed_memory_source(
            session,
            job_file_id=comparison.job_file_id,
            source=comparison.source,
            interview_through_sequence=comparison.interview_through_sequence,
        )
        assert original.revision_id == comparison.source.revision_id
        assert original.content.title == "每月盤點"
        assert original.content.body == "每月核對庫存。"
        assert await read_memory_source_titles(
            session,
            job_file_id=comparison.job_file_id,
            source=comparison.source,
            snapshot_id=comparison.snapshot_id,
            interview_through_sequence=comparison.interview_through_sequence,
        ) == ("季度盤點", "每月盤點", True)
        assert await read_memory_source_titles(
            session,
            job_file_id=comparison.job_file_id,
            source=comparison.source,
            snapshot_id=None,
            interview_through_sequence=comparison.interview_through_sequence,
        ) == (None, "每月盤點", True)
        result = await read_memory_source_changes(
            session,
            job_file_id=comparison.job_file_id,
            reference=reference,
            snapshot_id=comparison.snapshot_id,
            interview_through_sequence=comparison.interview_through_sequence,
        )
        assert result.reference == reference
        assert result.reference.needs_review
        (change,) = result.changes
        assert change.before == original
        assert change.after is not None
        assert change.after.content.body == "每季核對庫存。"
        assert change.before_interviews == change.after_interviews == (2,)

    transact(client, read)


def test_new_snapshot_with_same_revisions_does_not_recheck(
    client: TestClient,
    comparison: SourceComparison,
) -> None:
    file_id = comparison.job_file_id
    new_input = complete(client, start_turn(client, file_id=file_id)).employee_input

    async def publish_and_read():
        sessions = client.app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        async with sessions.begin() as session:
            current = await candidate_queries.read_snapshot_object(
                session,
                file_id,
                comparison.snapshot_id,
                comparison.source.object_id,
            )
            await executions.admit_execution(session, scope)
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        stage = await memory.start(writer, new_input.source_id)
        assert stage is not None
        phase = await memory.handoff(writer, stage, uuid4())
        snapshot = await publish_memory_owner_fixture(sessions, writer, phase, uuid4())
        source = replace(
            comparison.source, snapshot_id=comparison.snapshot_id, revision_id=current.revision_id
        )
        async with sessions() as session:
            metadata = await read_memory_source_metadata_batch(
                session,
                job_file_id=file_id,
                sources=(source,),
                snapshot_id=snapshot.snapshot_id,
                interview_through_sequence=snapshot.covered_through_sequence,
            )
        item = metadata[source]
        assert not item.source_changed
        assert item.comparison_version.revision_id == item.source_version.revision_id
        assert item.comparison_version.snapshot_id != item.source_version.snapshot_id
        assert (
            item.comparison_version.covered_through_sequence
            > item.source_version.covered_through_sequence
        )

    client.portal.call(publish_and_read)


def test_source_diff_uses_union_of_direct_situations_without_claiming_global_deletion(
    client: TestClient,
    comparison: SourceComparison,
) -> None:
    file_id = comparison.job_file_id
    first_input = complete(client, start_turn(client, file_id=file_id)).employee_input
    second_input = complete(client, start_turn(client, file_id=file_id)).employee_input

    async def read():
        sessions = client.app.state.database.sessions
        memory = MemoryCandidateWorkflow(sessions)

        async def batch(source_id):
            scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            return writer, await memory.start(writer, source_id)

        writer, stage = await batch(first_input.source_id)
        phase = await memory.handoff(writer, stage, uuid4())
        root = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("範圍管理", "依據", "理解正文不變"),
                reference_ids=frozenset({comparison.source.object_id}),
            ),
        )
        original = await publish_memory_owner_fixture(sessions, writer, root.position, uuid4())
        writer, stage = await batch(second_input.source_id)
        new_child = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("補貨", "新情境", "另一項依據"),
                reference_ids=frozenset({second_input.source_id}),
            ),
        )
        phase = await memory.handoff(writer, new_child.position, uuid4())
        updated = await memory.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                root.object_id,
                reference_changes=ReferenceChanges(
                    add=frozenset({new_child.object_id}),
                    remove=frozenset({comparison.source.object_id}),
                ),
            ),
        )
        latest = await publish_memory_owner_fixture(sessions, writer, updated.position, uuid4())
        async with sessions() as session:
            fixed_root = await candidate_queries.read_snapshot_object(
                session, file_id, original.snapshot_id, root.object_id
            )
            source = MemorySource(
                MemorySourceLayer.WORK_UNDERSTANDING,
                original.snapshot_id,
                root.object_id,
                fixed_root.revision_id,
            )
            reference = replace(comparison.reference(), source=source)
            result = await read_memory_source_changes(
                session,
                job_file_id=file_id,
                reference=reference,
                snapshot_id=latest.snapshot_id,
                interview_through_sequence=latest.covered_through_sequence,
            )
            old_child = await candidate_queries.read_snapshot_object(
                session, file_id, latest.snapshot_id, comparison.source.object_id
            )
        assert result.changes[0].before.content == result.changes[0].after.content
        assert len(result.changes) == 3
        removed = next(change for change in result.changes[1:] if change.after is None)
        added = next(change for change in result.changes[1:] if change.before is None)
        assert removed.before.object_id == old_child.object_id
        assert added.after.object_id == new_child.object_id
        from caliburn.transport.jd_source_markdown import project_jd_source_changes

        rendered = project_jd_source_changes(result)
        assert "移除直接情境引用（不據此推論物件全域刪除）" in rendered
        assert "新增直接情境引用（不代表新建物件）" in rendered

    client.portal.call(read)


@pytest.mark.parametrize("invalid", ["revision", "layer", "job_file", "interview_boundary"])
def test_shared_queries_reject_unqualified_fixed_source(
    client: TestClient, comparison: SourceComparison, invalid: str
) -> None:
    if invalid == "revision":
        # A real later revision is still not selected in the cited original snapshot.
        current = transact(
            client,
            lambda session: candidate_queries.read_snapshot_object(
                session,
                comparison.job_file_id,
                comparison.snapshot_id,
                comparison.source.object_id,
            ),
        )
        comparison = replace(
            comparison, source=replace(comparison.source, revision_id=current.revision_id)
        )
    elif invalid == "layer":
        comparison = replace(
            comparison,
            source=replace(comparison.source, layer=MemorySourceLayer.WORK_UNDERSTANDING),
        )
    elif invalid == "job_file":
        other_turn = start_turn(client)
        complete(client, other_turn)
        comparison = replace(comparison, job_file_id=other_turn.writer.scope.job_file_id)
    else:
        comparison = replace(comparison, interview_through_sequence=1)

    async def read(session: AsyncSession) -> None:
        error = (
            MemoryPermissionError
            if invalid == "interview_boundary"
            else MemoryRevisionNotFoundError
        )
        with pytest.raises(error):
            await read_fixed_memory_source(
                session,
                job_file_id=comparison.job_file_id,
                source=comparison.source,
                interview_through_sequence=comparison.interview_through_sequence,
            )
        with pytest.raises(error):
            await read_memory_source_titles(
                session,
                job_file_id=comparison.job_file_id,
                source=comparison.source,
                snapshot_id=comparison.snapshot_id,
                interview_through_sequence=comparison.interview_through_sequence,
            )
        with pytest.raises(error):
            await read_memory_source_changes(
                session,
                job_file_id=comparison.job_file_id,
                reference=comparison.reference(),
                snapshot_id=comparison.snapshot_id,
                interview_through_sequence=comparison.interview_through_sequence,
            )

    transact(client, read)


def test_comparison_endpoint_cannot_exceed_interview_boundary(
    client: TestClient, comparison: SourceComparison
) -> None:
    async def read(session: AsyncSession) -> None:
        # The original snapshot covers sequence 2, the comparison covers sequence 4.
        original = await read_fixed_memory_source(
            session,
            job_file_id=comparison.job_file_id,
            source=comparison.source,
            interview_through_sequence=2,
        )
        assert original.content.title == "每月盤點"
        with pytest.raises(MemoryPermissionError):
            await read_memory_source_titles(
                session,
                job_file_id=comparison.job_file_id,
                source=comparison.source,
                snapshot_id=comparison.snapshot_id,
                interview_through_sequence=2,
            )
        with pytest.raises(MemoryPermissionError):
            await read_memory_source_changes(
                session,
                job_file_id=comparison.job_file_id,
                reference=comparison.reference(),
                snapshot_id=comparison.snapshot_id,
                interview_through_sequence=2,
            )

    transact(client, read)


@pytest.mark.parametrize("titles_only", [False, True])
def test_fixed_source_queries_only_load_selected_members_and_requested_content(
    client: TestClient, comparison: SourceComparison, titles_only: bool
) -> None:
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        if titles_only:
            result = transact(
                client,
                lambda session: read_memory_source_titles(
                    session,
                    job_file_id=comparison.job_file_id,
                    source=comparison.source,
                    snapshot_id=comparison.snapshot_id,
                    interview_through_sequence=comparison.interview_through_sequence,
                ),
            )
            assert result == ("季度盤點", "每月盤點", True)
        else:
            result = transact(
                client,
                lambda session: read_fixed_memory_source(
                    session,
                    job_file_id=comparison.job_file_id,
                    source=comparison.source,
                    interview_through_sequence=comparison.interview_through_sequence,
                ),
            )
            assert result.content.body == "每月核對庫存。"
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    member_reads = [statement for statement in statements if "memory_position_members" in statement]
    assert member_reads
    # 每次只查來源指定的物件，不能把整個 position 帶回 Python 再篩選。
    assert all("memory_position_members.object_id IN (" in statement for statement in member_reads)
    if titles_only:
        assert all("memory_bodies" not in statement for statement in statements)


def test_overview_groups_fixed_source_headers_by_snapshot(
    client: TestClient, comparison: SourceComparison
) -> None:
    current = transact(
        client,
        lambda session: candidate_queries.read_snapshot_object(
            session, comparison.job_file_id, comparison.snapshot_id, comparison.source.object_id
        ),
    )
    turn = start_turn(client, file_id=comparison.job_file_id)
    writer = JdCandidateWorkflow(client.app.state.database.sessions)
    position = turn.candidate
    for field, source in (
        (ProfileField.JOB_TITLE, comparison.source),
        (
            ProfileField.PURPOSE,
            replace(
                comparison.source,
                snapshot_id=comparison.snapshot_id,
                revision_id=current.revision_id,
            ),
        ),
    ):
        position = client.portal.call(
            writer.edit,
            turn.writer,
            position.scope,
            ReviseJdSources(
                uuid4(),
                position.revision_id,
                JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=field),
                (AddJdSource(source),),
            ),
        )
    complete(client, replace(turn, candidate=position))
    statements: list[str] = []

    def capture(_connection, _cursor, statement, _parameters, _context, _many):
        statements.append(statement)

    engine = client.app.state.database.engine.sync_engine
    event.listen(engine, "before_cursor_execute", capture)
    try:
        overview = client.portal.call(
            JdEvidenceWorkflow(client.app.state.database.sessions).read_overview,
            comparison.job_file_id,
        )
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert {reference.source_label for reference in overview.references} == {"每月盤點", "季度盤點"}
    assert len(overview.references) == 2
    assert not any("memory_bodies" in statement for statement in statements)
    # 兩份歷史快照加上一次比較位置，不能為每條引用重讀目前位置。
    assert sum("memory_position_members" in statement for statement in statements) <= 3


def test_memory_evidence_chain_survives_deletion_between_snapshot_and_body(
    client: TestClient,
    comparison: SourceComparison,
    database_connection: psycopg.Connection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_id = comparison.job_file_id
    turn = start_turn(client, file_id=file_id)
    sessions = client.app.state.database.sessions
    position = client.portal.call(
        JdCandidateWorkflow(sessions).edit,
        turn.writer,
        turn.candidate.scope,
        ReviseJdSources(
            uuid4(),
            turn.candidate.revision_id,
            JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.PURPOSE),
            (AddJdSource(comparison.source),),
        ),
    )
    complete(client, replace(turn, candidate=position))
    workflow = JdEvidenceWorkflow(sessions)
    overview = client.portal.call(workflow.read_overview, file_id)
    original = candidate_queries.read_snapshot
    deleted = False

    async def delete_after_snapshot(session, requested_file, snapshot_id):
        nonlocal deleted
        snapshot = await original(session, requested_file, snapshot_id)
        if not deleted:
            deleted = True
            database_connection.execute("DELETE FROM job_files WHERE job_file_id=%s", (file_id,))
        return snapshot

    monkeypatch.setattr(candidate_queries, "read_snapshot", delete_after_snapshot)
    result = client.portal.call(
        workflow.read_content, file_id, overview.revision_id, overview.references[0].citation_id
    )
    assert isinstance(result, MemoryEvidence)
    assert result.revision.content.body == "每月核對庫存。"
    assert [link.label for link in result.references] == ["訪談序號 2 · 員工"]
    assert deleted
