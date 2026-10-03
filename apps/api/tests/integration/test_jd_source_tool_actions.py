"""Canonical revise tools modify and confirm evidence through the existing source owner."""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions.models import ExecutionStateError, ExecutionStatus
from caliburn.features.job_description import source_persistence
from caliburn.features.job_description.capabilities import EditJdCapabilities, SetTaskCapability
from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.features.job_description.sources import InterviewSource, SourceTargetKind
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.jd_item_creation import JdItemCreationWorkflow
from caliburn.workflows.jd_item_deletion import JdItemDeletionWorkflow
from caliburn.workflows.jd_item_movement import JdItemMovementWorkflow
from caliburn.workflows.jd_item_revision import JdItemRevisionWorkflow
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.integration.test_jd_item_revision import setup_item
from tests.integration.test_jd_source_edits import transact

pytestmark = pytest.mark.postgres


def source_tools(client, writer, binding=None):
    sessions = client.app.state.database.sessions
    return JdWriteTools(
        JdProfileWriteWorkflow(sessions),
        JdTaskWriteWorkflow(sessions),
        binding or PublishedMemoryRead(writer.scope, None, 1),
        writer,
        creations=JdItemCreationWorkflow(sessions),
        revisions=JdItemRevisionWorkflow(sessions),
        deletions=JdItemDeletionWorkflow(sessions),
        movements=JdItemMovementWorkflow(sessions),
    )


def prepare(client, tools, name, payload):
    result = client.portal.call(tools.prepare, name, json.dumps(payload), uuid4())
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


@pytest.mark.parametrize("target_kind", ["profile", "item", "detail", "capability_relation"])
def test_source_only_confirmation_is_explicit_precise_and_replayable(
    client: TestClient, target_kind
):
    writer, candidates, before = setup_item(client)
    task = before.work.tasks[0]
    skill = before.work.capabilities[0]
    if target_kind == "capability_relation":
        client.portal.call(
            candidates.edit,
            writer,
            before.position.scope,
            EditJdCapabilities(
                uuid4(),
                before.position.revision_id,
                SetTaskCapability(task.task_id, skill.capability_id, True),
            ),
        )
    tools = source_tools(client, writer)
    name = "revise_jd_profile" if target_kind == "profile" else "revise_jd_item"
    outer = {} if target_kind == "profile" else {"read_ref": jd_read_ref(task)}
    selected = (
        {"field": "job_title"} if target_kind == "profile" else {"target": {"kind": target_kind}}
    )
    if target_kind == "detail":
        selected["target"]["detail_read_ref"] = jd_read_ref(task.details[0])
    if target_kind == "capability_relation":
        selected["target"]["capability_read_ref"] = jd_read_ref(skill)
    text_change = {
        "action": "set_field",
        "field": "job_title" if target_kind == "profile" else "description",
        "value": "已確認的新內容",
    }
    if target_kind == "detail":
        text_change = {
            "action": "revise_detail",
            "detail_read_ref": jd_read_ref(task.details[0]),
            "text": "已確認的新成果",
        }
    if target_kind == "profile":
        invoke(
            client,
            tools,
            name,
            {"changes": [{"action": "set_field", "field": "job_title", "value": "原職称"}]},
        )
    additions = [
        {"action": "add_source", **selected, "source": source}
        for source in ({"kind": "current_input"}, {"kind": "interview", "interview_sequence": 1})
    ]
    assert invoke(client, tools, name, {**outer, "changes": additions}) == "updated"
    linked = client.portal.call(candidates.read, writer.scope)
    original = references(client, writer, linked.position.revision_id)
    assert len(original) == 2 and all(isinstance(ref.source, InterviewSource) for ref in original)
    expected_kind = {
        "profile": SourceTargetKind.PROFILE_FIELD,
        "item": SourceTargetKind.TASK,
        "detail": SourceTargetKind.DETAIL,
        "capability_relation": SourceTargetKind.TASK_CAPABILITY,
    }[target_kind]
    assert all(ref.target.kind == expected_kind for ref in original)
    assert invoke(client, tools, name, {**outer, "changes": [text_change]}) == "updated"
    assert invoke(client, tools, name, {**outer, "changes": additions}) == "unchanged"
    pending = client.portal.call(candidates.read, writer.scope)
    assert all(ref.needs_review for ref in references(client, writer, pending.position.revision_id))

    citation = f"citation_{original[0].citation_id.hex}"
    confirmation = {"action": "confirm_reference_alignment", **selected, "citation_ref": citation}
    prepared = prepare(client, tools, name, {**outer, "changes": [confirmation]})
    assert client.portal.call(tools.execute, prepared) == "aligned"
    aligned = client.portal.call(candidates.read, writer.scope)
    current = references(client, writer, aligned.position.revision_id)
    assert [(ref.source, ref.needs_review) for ref in current] == [
        (original[0].source, False),
        (original[1].source, True),
    ]
    assert invoke(client, tools, name, {**outer, "changes": [confirmation]}) == "unchanged"
    # Restored original command still returns its original effect, not the later head.
    next_text = {**text_change, "text" if target_kind == "detail" else "value": "後續不同內容"}
    invoke(client, tools, name, {**outer, "changes": [next_text]})
    later = client.portal.call(candidates.read, writer.scope)
    assert client.portal.call(tools.execute, prepared) == "aligned"
    assert client.portal.call(candidates.read, writer.scope).position == later.position
    assert all(ref.needs_review for ref in references(client, writer, later.position.revision_id))
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
    add = {"action": "add_source", "target": {"kind": "item"}, "source": {"kind": "current_input"}}
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
                    "target": {"kind": "detail", "detail_read_ref": jd_read_ref(task.details[0])},
                },
            ],
        },
    )
    original_insert = source_persistence.insert_source_references

    async def fail_after_detail(session, file_id, revision_id, refs):
        await original_insert(session, file_id, revision_id, refs)
        if any(ref.target.kind == SourceTargetKind.DETAIL for ref in refs):
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
