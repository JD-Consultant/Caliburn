"""Shared fixed-source reads need no active A and retain Memory owner validation."""

from collections.abc import Iterator
from dataclasses import dataclass, replace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import (
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
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError
from caliburn.workflows.jd_source_queries import (
    read_fixed_memory_source,
    read_memory_source_changes,
    read_memory_source_titles,
)
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from tests.integration.test_consultant_completion import complete, start_turn, transact

pytestmark = pytest.mark.postgres


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
        original = await memory.publish(writer, phase, uuid4())
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
        current = await memory.publish(writer, phase, uuid4())
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
