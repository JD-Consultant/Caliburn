"""Canonical revise tools modify and confirm evidence through the existing source owner."""

import json
from dataclasses import replace
from functools import partial
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import InterviewSource, SourceTargetKind
from caliburn.transport.model_tools.jd_reference_fields import map_jd_reference_fields
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.compound_writes import execute_prepared_jd_edit
from caliburn.workflows.job_description.item_creation import JdItemCreationWorkflow
from caliburn.workflows.job_description.item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.job_description.item_movement import JdItemMovementWorkflow
from caliburn.workflows.job_description.item_revision import JdItemRevisionWorkflow
from caliburn.workflows.job_description.profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.job_description.task_writes import JdTaskWriteWorkflow
from caliburn.workflows.work_memory.reads import PublishedMemoryRead
from tests.fixtures.consultant_turn import transact
from tests.integration.test_consultant_completion import complete, start_turn
from tests.integration.test_jd_item_revision import setup_item
from tests.integration.test_jd_manual_changes import manual_profile

pytestmark = pytest.mark.postgres


def source_tools(client, writer, binding=None):
    sessions = client.app.state.database.sessions
    return JdWriteTools(
        JdProfileWriteWorkflow(sessions),
        JdTaskWriteWorkflow(sessions),
        binding or PublishedMemoryRead(writer.scope, None, 1),
        writer,
        references=JdModelReferences(sessions, writer.scope.job_file_id),
        execute_edit=partial(execute_prepared_jd_edit, sessions),
        creations=JdItemCreationWorkflow(sessions),
        revisions=JdItemRevisionWorkflow(sessions),
        deletions=JdItemDeletionWorkflow(sessions),
        movements=JdItemMovementWorkflow(sessions),
    )


def prepare(client, tools, name, payload):
    canonical = set()

    def collect(ref):
        if len(ref.rsplit("_", 1)[-1]) == 32:
            canonical.add(ref)
        return ref

    map_jd_reference_fields(payload, collect)
    aliases = client.portal.call(tools.references.assign, canonical)
    model_payload = map_jd_reference_fields(payload, lambda ref: aliases.get(ref, ref))
    result = client.portal.call(tools.prepare, name, json.dumps(model_payload), uuid4())
    assert not isinstance(result, str), result
    return restore_jd_write(snapshot_jd_write(result))


def invoke(client, tools, name, payload):
    return client.portal.call(tools.execute, prepare(client, tools, name, payload))


def references(client, writer, revision):
    return transact(
        client,
        lambda session: source_persistence.read_source_references(
            session, writer.scope.job_file_id, revision
        ),
    )


@pytest.mark.parametrize("change_kind", ["profile", "task", "outcome", "capability_link"])
def test_consultant_content_edits_review_existing_sources_without_another_confirmation(
    client: TestClient, change_kind
):
    writer, candidates, before = setup_item(client)
    task = before.work.tasks[0]
    skill = before.work.capabilities[0]
    tools = source_tools(client, writer)
    name = "revise_jd_profile" if change_kind == "profile" else "revise_jd_item"
    outer = {} if change_kind == "profile" else {"read_ref": jd_read_ref(task)}
    selected = {"field": "job_title"} if change_kind == "profile" else {"target": {"kind": "item"}}
    text_change = {
        "action": "set_field",
        "field": "job_title" if change_kind == "profile" else "description",
        "value": "已確認的新內容",
    }
    if change_kind == "outcome":
        text_change = {
            "action": "revise_detail",
            "detail_read_ref": jd_read_ref(task.details[0]),
            "text": "已確認的新成果",
        }
    if change_kind == "capability_link":
        text_change = {
            "action": "set_capability",
            "capability_read_ref": jd_read_ref(skill),
            "relationship": "link",
        }
    if change_kind == "profile":
        invoke(
            client,
            tools,
            name,
            {"changes": [{"action": "set_field", "field": "job_title", "value": "原職称"}]},
        )
    additions = [
        {"action": "add_source", **selected, "source": source}
        for source in (
            {"kind": "interview", "interview_sequence": 2},
            {"kind": "interview", "interview_sequence": 1},
        )
    ]
    assert invoke(client, tools, name, {**outer, "changes": additions}) == "updated"
    linked = client.portal.call(candidates.read, writer.scope)
    original = references(client, writer, linked.position.revision_id)
    assert len(original) == 2 and all(isinstance(ref.source, InterviewSource) for ref in original)
    expected_kind = (
        SourceTargetKind.PROFILE_FIELD if change_kind == "profile" else SourceTargetKind.TASK
    )
    assert all(ref.target.kind == expected_kind for ref in original)
    assert invoke(client, tools, name, {**outer, "changes": [text_change]}) == "updated"
    assert invoke(client, tools, name, {**outer, "changes": additions}) == "unchanged"
    pending = client.portal.call(candidates.read, writer.scope)
    assert all(
        not ref.needs_review and ref.reviewed_revision_id == pending.position.revision_id
        for ref in references(client, writer, pending.position.revision_id)
    )

    citation = f"citation_{original[0].citation_id.hex}"
    confirmation = {"action": "confirm_reference_alignment", **selected, "citation_ref": citation}
    prepared = prepare(client, tools, name, {**outer, "changes": [confirmation]})
    assert client.portal.call(tools.execute, prepared) == "unchanged"
    aligned = client.portal.call(candidates.read, writer.scope)
    current = references(client, writer, aligned.position.revision_id)
    assert [(ref.source, ref.needs_review) for ref in current] == [
        (original[0].source, False),
        (original[1].source, False),
    ]
    assert invoke(client, tools, name, {**outer, "changes": [confirmation]}) == "unchanged"
    # Restored original command still returns its original effect, not the later head.
    next_text = (
        {**text_change, "relationship": "unlink"}
        if change_kind == "capability_link"
        else {**text_change, "text" if change_kind == "outcome" else "value": "後續不同內容"}
    )
    invoke(client, tools, name, {**outer, "changes": [next_text]})
    later = client.portal.call(candidates.read, writer.scope)
    assert client.portal.call(tools.execute, prepared) == "unchanged"
    assert client.portal.call(candidates.read, writer.scope).position == later.position
    assert all(
        not ref.needs_review and ref.reviewed_revision_id == later.position.revision_id
        for ref in references(client, writer, later.position.revision_id)
    )
    assert (
        invoke(
            client, tools, name, {**outer, "changes": [{**confirmation, "action": "remove_source"}]}
        )
        == "updated"
    )
    remaining = references(
        client, writer, client.portal.call(candidates.read, writer.scope).position.revision_id
    )
    assert [ref.citation_id for ref in remaining] == [original[1].citation_id]
    assert references(client, writer, linked.position.revision_id) == original


def test_source_conflicts_wrong_target_and_late_failure_leave_no_partial_effect(
    client, monkeypatch
):
    writer, candidates, before = setup_item(client)
    formal_before = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()
    tools = source_tools(client, writer)
    task = before.work.tasks[0]
    outer = {"read_ref": jd_read_ref(task)}
    add = {
        "action": "add_source",
        "target": {"kind": "item"},
        "source": {"kind": "interview", "interview_sequence": 2},
    }
    invoke(client, tools, "revise_jd_item", {**outer, "changes": [add]})
    before = client.portal.call(candidates.read, writer.scope)
    citation = (
        f"citation_{references(client, writer, before.position.revision_id)[0].citation_id.hex}"
    )
    confirm = {
        "action": "confirm_reference_alignment",
        "target": {"kind": "item"},
        "citation_ref": citation,
    }
    for changes in (
        [confirm, {**confirm, "action": "remove_source"}],
        [
            {
                **confirm,
                "target": {"kind": "detail", "detail_read_ref": jd_read_ref(task.details[0])},
            }
        ],
    ):
        rejected = client.portal.call(
            tools.prepare, "revise_jd_item", json.dumps({**outer, "changes": changes}), uuid4()
        )
        assert isinstance(rejected, str) and json.loads(rejected)["status"] == "rejected"
        assert client.portal.call(candidates.read, writer.scope).position == before.position
    # The first source group and text can write before a later group fails: whole call rolls back.
    prepared = prepare(
        client,
        tools,
        "revise_jd_item",
        {
            **outer,
            "changes": [
                {"action": "set_field", "field": "description", "value": "不得留下"},
                confirm,
                {
                    **add,
                    "target": {"kind": "item"},
                    "source": {"kind": "interview", "interview_sequence": 1},
                },
            ],
        },
    )
    original_insert = source_persistence.insert_source_references

    async def fail_after_detail(session, file_id, revision_id, refs):
        await original_insert(session, file_id, revision_id, refs)
        if len(refs) == 2:
            raise ConnectionError("synthetic failure after second source group")

    with monkeypatch.context() as patch:
        patch.setattr(source_persistence, "insert_source_references", fail_after_detail)
        with pytest.raises(ConnectionError, match="second source group"):
            client.portal.call(tools.execute, prepared)
    assert client.portal.call(candidates.read, writer.scope).position == before.position
    assert client.portal.call(tools.execute, prepared) == "updated"
    # Cancellation does not grant late prepared evidence another write opportunity.
    pending = prepare(client, tools, "revise_jd_item", {**outer, "changes": [confirm]})
    client.portal.call(
        ConsultantCompletionWorkflow(client.app.state.database.sessions).stop,
        writer,
        ExecutionStatus.CANCELLED,
    )
    with pytest.raises(ExecutionStateError):
        client.portal.call(tools.execute, pending)
    formal = client.get(f"/api/job-files/{writer.scope.job_file_id}/jd/profile").json()
    assert formal == formal_before
    assert (
        len(client.get(f"/api/job-files/{writer.scope.job_file_id}/interviews").json()["messages"])
        == 1
    )


def test_manual_pending_requires_precise_confirmation_or_actual_consultant_revision(client):
    first = start_turn(client)
    tools = source_tools(client, first.writer)
    invoke(
        client,
        tools,
        "revise_jd_profile",
        {
            "changes": [
                {"action": "set_field", "field": "purpose", "value": "交付網站"},
                *[
                    {
                        "action": "add_source",
                        "field": field,
                        "source": {"kind": "interview", "interview_sequence": sequence},
                    }
                    for field, sequence in (("job_title", 2), ("job_title", 1), ("purpose", 2))
                ],
            ]
        },
    )
    candidates = JdCandidateWorkflow(client.app.state.database.sessions)
    position = client.portal.call(candidates.read, first.writer.scope).position
    complete(client, replace(first, candidate=position))
    file_id = first.writer.scope.job_file_id
    manual_profile(client, file_id, "job_title", "人工職稱")
    manual_profile(client, file_id, "purpose", "人工使命")
    turn = start_turn(client, file_id=file_id, with_candidate=False)
    position = client.portal.call(candidates.start, turn.writer)
    pending = references(client, turn.writer, position.revision_id)
    assert len(pending) == 3 and all(ref.needs_review for ref in pending)
    tools = source_tools(client, turn.writer, PublishedMemoryRead(turn.writer.scope, None, 3))
    assert (
        invoke(
            client,
            tools,
            "revise_jd_profile",
            {
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "人工職稱"},
                ]
            },
        )
        == "unchanged"
    )
    assert references(client, turn.writer, position.revision_id) == pending
    confirmation = prepare(
        client,
        tools,
        "revise_jd_profile",
        {
            "changes": [
                {
                    "action": "confirm_reference_alignment",
                    "field": "job_title",
                    "citation_ref": f"citation_{pending[0].citation_id.hex}",
                }
            ]
        },
    )
    assert client.portal.call(tools.execute, confirmation) == "aligned"
    aligned = client.portal.call(candidates.read, turn.writer.scope).position
    assert [ref.needs_review for ref in references(client, turn.writer, aligned.revision_id)] == [
        False,
        True,
        True,
    ]
    invoke(
        client,
        tools,
        "revise_jd_profile",
        {
            "changes": [
                {"action": "set_field", "field": "job_title", "value": "顧問分析後職稱"},
            ]
        },
    )
    revised = client.portal.call(candidates.read, turn.writer.scope).position
    actual = references(client, turn.writer, revised.revision_id)
    assert [ref.needs_review for ref in actual] == [False, False, True]
    assert [ref.reviewed_revision_id for ref in actual[:2]] == [revised.revision_id] * 2
    assert actual[2] == pending[2]
    assert [ref.source for ref in actual] == [ref.source for ref in pending]
    assert client.portal.call(tools.execute, confirmation) == "aligned"
    assert client.portal.call(candidates.read, turn.writer.scope).position == revised


def test_removing_task_detail_reviews_support_and_deleting_task_removes_its_reference(client):
    writer, candidates, before = setup_item(client)
    tools = source_tools(client, writer)
    task = before.work.tasks[0]
    invoke(
        client,
        tools,
        "revise_jd_item",
        {
            "read_ref": jd_read_ref(task),
            "changes": [
                {
                    "action": "add_source",
                    "target": {"kind": "item"},
                    "source": {"kind": "interview", "interview_sequence": 2},
                }
            ],
        },
    )
    invoke(
        client,
        tools,
        "revise_jd_item",
        {
            "read_ref": jd_read_ref(task),
            "changes": [
                {
                    "action": "remove_detail",
                    "detail_read_ref": jd_read_ref(task.details[0]),
                }
            ],
        },
    )
    revised = client.portal.call(candidates.read, writer.scope)
    assert revised.work.tasks[0].details == ()
    (reference,) = references(client, writer, revised.position.revision_id)
    assert not reference.needs_review
    assert reference.reviewed_revision_id == revised.position.revision_id
    assert invoke(client, tools, "delete_jd_item", {"read_ref": jd_read_ref(task)}) == "deleted"
    deleted = client.portal.call(candidates.read, writer.scope)
    assert deleted.work.tasks == ()
    assert references(client, writer, deleted.position.revision_id) == ()
    assert references(client, writer, revised.position.revision_id) == (reference,)
