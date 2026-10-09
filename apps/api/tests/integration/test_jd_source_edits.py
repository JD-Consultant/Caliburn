"""JD direct evidence survives edits, replay and candidate recovery without implicit refresh."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions.models import ExecutionWriter
from caliburn.features.interviews import queries as interviews
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InterviewSource,
    JdSourceReference,
    JdSourceTarget,
    RemoveJdSource,
    ReviseJdSources,
    SourceTargetKind,
)
from caliburn.workflows.jd_candidates import JdCandidateWorkflow
from tests.fixtures.consultant_turn import start_consultant_turn as start
from tests.fixtures.consultant_turn import transact

pytestmark = pytest.mark.postgres


def references(
    client: TestClient, writer: ExecutionWriter, revision_id: UUID
) -> tuple[JdSourceReference, ...]:
    return transact(
        client,
        lambda s: source_persistence.read_source_references(
            s, writer.scope.job_file_id, revision_id
        ),
    )


def test_candidate_source_edit_replay_content_change_and_explicit_alignment(
    client: TestClient,
) -> None:
    writer = start(client)
    workflow = JdCandidateWorkflow(client.app.state.database.sessions)
    initial = client.portal.call(workflow.start, writer)
    current = client.portal.call(
        workflow.edit,
        writer,
        initial.scope,
        ReviseJdProfile(
            uuid4(), initial.revision_id, (SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),)
        ),
    )
    original = transact(
        client,
        lambda s: interviews.read_execution_input(
            s, job_file_id=writer.scope.job_file_id, execution_id=writer.scope.execution_id
        ),
    )
    source = InterviewSource(original.source_id)
    target = JdSourceTarget(SourceTargetKind.PROFILE_FIELD, field=ProfileField.JOB_TITLE)
    add = ReviseJdSources(uuid4(), current.revision_id, target, (AddJdSource(source),))
    linked = client.portal.call(workflow.edit, writer, initial.scope, add)
    basis = references(client, writer, linked.revision_id)[0]
    assert basis.source == source
    assert not basis.needs_review
    assert basis.reviewed_revision_id == linked.revision_id
    changed = client.portal.call(
        workflow.edit,
        writer,
        initial.scope,
        ReviseJdProfile(
            uuid4(), linked.revision_id, (SetProfileField(ProfileField.JOB_TITLE, "後端工程師"),)
        ),
    )
    reverted = client.portal.call(
        workflow.edit,
        writer,
        initial.scope,
        ReviseJdProfile(
            uuid4(), changed.revision_id, (SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),)
        ),
    )
    pending = references(client, writer, reverted.revision_id)[0]
    assert pending.needs_review
    assert pending.reviewed_revision_id == basis.reviewed_revision_id
    assert client.portal.call(workflow.edit, writer, initial.scope, add) == linked
    assert client.portal.call(workflow.read, writer.scope).position == reverted
    duplicate = client.portal.call(
        workflow.edit,
        writer,
        initial.scope,
        ReviseJdSources(uuid4(), reverted.revision_id, target, (AddJdSource(source),)),
    )
    assert duplicate.revision_id == reverted.revision_id
    assert references(client, writer, duplicate.revision_id)[0].needs_review
    aligned = client.portal.call(
        workflow.edit,
        writer,
        initial.scope,
        ReviseJdSources(
            uuid4(), reverted.revision_id, target, (AlignJdSource(basis.citation_id, source),)
        ),
    )
    assert not references(client, writer, aligned.revision_id)[0].needs_review
    assert (
        references(client, writer, aligned.revision_id)[0].reviewed_revision_id
        == aligned.revision_id
    )
    removed = client.portal.call(
        workflow.edit,
        writer,
        initial.scope,
        ReviseJdSources(uuid4(), aligned.revision_id, target, (RemoveJdSource(basis.citation_id),)),
    )
    assert references(client, writer, removed.revision_id) == ()
    assert references(client, writer, linked.revision_id) == (basis,)
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()
    assert formal["revision_id"] == str(initial.revision_id)
