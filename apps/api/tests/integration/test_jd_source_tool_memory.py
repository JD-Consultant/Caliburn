"""Alignment uses the Turn's published same-object revision, never latest or a reused title."""

import json
from dataclasses import replace
from functools import partial
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.job_description.sources import MemorySource
from caliburn.features.work_memory import candidate_queries
from caliburn.features.work_memory.candidates import (
    CreateMemoryObject,
    DeleteMemoryObject,
    ReviseMemoryObject,
)
from caliburn.features.work_memory.models import MemoryContent, MemoryContentChanges
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.workflows.job_description.candidates import JdCandidateWorkflow
from caliburn.workflows.job_description.reads import JdReadWorkflow
from caliburn.workflows.job_description.source_changes import JdChangesWorkflow
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from caliburn.workflows.work_memory.reads import PublishedMemoryRead
from tests.fixtures.memory_owner import publish_memory_owner_fixture
from tests.integration.test_consultant_completion import complete, start_turn, transact
from tests.integration.test_jd_source_tool_actions import invoke, prepare, references, source_tools

pytestmark = pytest.mark.postgres


def test_alignment_uses_pinned_revision_and_rejects_later_same_title_replacement(
    client: TestClient,
):
    first = start_turn(client)
    file_id = first.writer.scope.job_file_id
    formal_sources = [complete(client, first).employee_input.source_id]
    for _ in range(2):
        formal_sources.append(
            complete(client, start_turn(client, file_id=file_id)).employee_input.source_id
        )
    sessions = client.app.state.database.sessions
    memory = MemoryCandidateWorkflow(sessions)

    async def batch(index):
        scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
        async with sessions.begin() as session:
            await executions.admit_execution(session, scope)
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        stage = await memory.start(writer, formal_sources[index])
        assert stage is not None
        return writer, stage

    async def original_snapshot():
        writer, stage = await batch(0)
        situation = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("盤點", "盤點情境", "每月盤點。"),
            ),
        )
        phase = await memory.handoff(writer, situation.position, uuid4())
        understanding = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "工作理解", "維持庫存資料。"),
                reference_ids=frozenset({situation.object_id}),
            ),
        )
        return (
            await publish_memory_owner_fixture(
                memory.sessions, writer, understanding.position, uuid4()
            ),
            situation.object_id,
            understanding.object_id,
        )

    old_snapshot, situation_id, understanding_id = client.portal.call(original_snapshot)
    original_turn = start_turn(client, file_id=file_id)
    tools = source_tools(
        client,
        original_turn.writer,
        PublishedMemoryRead(original_turn.writer.scope, old_snapshot.snapshot_id, 7),
    )
    assert (
        invoke(
            client,
            tools,
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "add_source",
                        "field": "job_title",
                        "source": {"kind": layer, "target_title": title},
                    }
                    for layer, title in (
                        ("work_situation", "盤點"),
                        ("work_understanding", "庫存管理"),
                    )
                ]
            },
        )
        == "updated"
    )
    candidates = JdCandidateWorkflow(sessions)
    original_position = client.portal.call(candidates.read, original_turn.writer.scope).position
    old_references = references(client, original_turn.writer, original_position.revision_id)
    complete(client, replace(original_turn, candidate=original_position))

    async def pinned_snapshot():
        writer, stage = await batch(1)
        situation = await memory.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                stage,
                MemoryLayer.WORK_SITUATION,
                situation_id,
                MemoryContentChanges(title="季度盤點", body="每季盤點。"),
            ),
        )
        phase = await memory.handoff(writer, situation.position, uuid4())
        understanding = await memory.edit(
            writer,
            ReviseMemoryObject(
                uuid4(),
                phase,
                MemoryLayer.WORK_UNDERSTANDING,
                understanding_id,
                MemoryContentChanges(body="維持季度庫存。"),
            ),
        )
        return await publish_memory_owner_fixture(
            memory.sessions, writer, understanding.position, uuid4()
        )

    pinned = client.portal.call(pinned_snapshot)
    turn = start_turn(client, file_id=file_id)
    binding = PublishedMemoryRead(turn.writer.scope, pinned.snapshot_id, 9)
    tools = source_tools(client, turn.writer, binding)
    citations = [f"citation_{ref.citation_id.hex}" for ref in old_references]
    reader = JdChangesWorkflow(sessions)
    before = client.portal.call(candidates.read, turn.writer.scope)
    for citation in citations:
        result = client.portal.call(reader.read_source, binding, citation)
        assert result.changes
    # Public model reads/diffs/confirmations all use the same short citation locator.
    locators = JdModelReferences(sessions, binding.scope.job_file_id)
    read_tools = JdReadTools(JdReadWorkflow(sessions), binding, references=locators)
    profile = json.loads(
        client.portal.call(read_tools.invoke, "read_jd", '{"view":"profile","read_ref":null}')
    )
    citations = [item["citation_ref"] for item in profile["supporting_sources"]["job_title"]]
    assert all(len(ref) < 24 for ref in citations)
    changes_tools = JdChangesTools(
        reader,
        binding,
        references=locators,
    )
    for citation in citations:
        output = client.portal.call(
            changes_tools.invoke,
            "read_jd_changes",
            json.dumps({"query": {"kind": "source", "citation_ref": citation}}),
        )
        assert "## JD 來源差異" in output and f"citation_ref: {citation}" in output
        assert "每季盤點" in output
    # Reading differences and adding the same identity at a new version do not align it.
    assert (
        invoke(
            client,
            tools,
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "add_source",
                        "field": "job_title",
                        "source": {"kind": layer, "target_title": title},
                    }
                    for layer, title in (
                        ("work_situation", "季度盤點"),
                        ("work_understanding", "庫存管理"),
                    )
                ]
            },
        )
        == "unchanged"
    )
    assert client.portal.call(candidates.read, turn.writer.scope).position == before.position
    assert references(client, turn.writer, before.position.revision_id) == old_references
    assert (
        invoke(
            client,
            tools,
            "revise_jd_profile",
            {
                "changes": [
                    {
                        "action": "set_field",
                        "field": "job_title",
                        "value": "季度庫存專員",
                    }
                ]
            },
        )
        == "updated"
    )
    revised = client.portal.call(candidates.read, turn.writer.scope).position
    revised_references = references(client, turn.writer, revised.revision_id)
    assert [ref.source for ref in revised_references] == [ref.source for ref in old_references]
    assert all(not ref.needs_review for ref in revised_references)
    assert all(ref.reviewed_revision_id == revised.revision_id for ref in revised_references)
    revised_profile = json.loads(
        client.portal.call(read_tools.invoke, "read_jd", '{"view":"profile","read_ref":null}')
    )
    assert all(
        item["needs_recheck"] and item["source_changed"] and not item["jd_changed"]
        for item in revised_profile["supporting_sources"]["job_title"]
    )
    for reference in revised_references:
        result = client.portal.call(
            reader.read_source, binding, f"citation_{reference.citation_id.hex}"
        )
        assert result.changes, "顧問改稿不能自動確認 Memory 的新版來源"
    confirmations = [
        {"action": "confirm_reference_alignment", "field": "job_title", "citation_ref": citation}
        for citation in citations
    ]
    prepared = prepare(client, tools, "revise_jd_profile", {"changes": confirmations})

    async def later_snapshot():
        writer, stage = await batch(2)
        removed = await memory.edit(
            writer, DeleteMemoryObject(uuid4(), stage, MemoryLayer.WORK_SITUATION, situation_id)
        )
        recreated = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                removed.position,
                MemoryLayer.WORK_SITUATION,
                MemoryContent("季度盤點", "同名新身分", "不能替代原引用。"),
            ),
        )
        phase = await memory.handoff(writer, recreated.position, uuid4())
        removed_understanding = await memory.edit(
            writer,
            DeleteMemoryObject(uuid4(), phase, MemoryLayer.WORK_UNDERSTANDING, understanding_id),
        )
        recreated_understanding = await memory.edit(
            writer,
            CreateMemoryObject(
                uuid4(),
                removed_understanding.position,
                MemoryLayer.WORK_UNDERSTANDING,
                MemoryContent("庫存管理", "同名新理解", "不能替代原理解。"),
            ),
        )
        return await publish_memory_owner_fixture(
            memory.sessions, writer, recreated_understanding.position, uuid4()
        )

    latest = client.portal.call(later_snapshot)
    assert client.portal.call(tools.execute, prepared) == "aligned"
    aligned = client.portal.call(candidates.read, turn.writer.scope)
    confirmed = references(client, turn.writer, aligned.position.revision_id)
    for reference in confirmed:
        assert isinstance(reference.source, MemorySource)
        assert reference.source.snapshot_id == pinned.snapshot_id
        assert reference.source.object_id in {situation_id, understanding_id}
        selected = transact(
            client,
            partial(
                candidate_queries.read_snapshot_object,
                job_file_id=file_id,
                snapshot_id=pinned.snapshot_id,
                object_id=reference.source.object_id,
            ),
        )
        assert reference.source.revision_id == selected.revision_id
        assert not reference.needs_review
    assert invoke(client, tools, "revise_jd_profile", {"changes": confirmations}) == "unchanged"
    complete(client, replace(turn, candidate=aligned.position))

    following = start_turn(client, file_id=file_id, with_candidate=False)
    client.portal.call(candidates.start, following.writer)
    following_tools = source_tools(
        client,
        following.writer,
        PublishedMemoryRead(following.writer.scope, latest.snapshot_id, 11),
    )
    following_position = client.portal.call(candidates.read, following.writer.scope).position
    for confirmation in confirmations:
        rejection = client.portal.call(
            following_tools.prepare,
            "revise_jd_profile",
            json.dumps({"changes": [confirmation]}),
            uuid4(),
        )
        assert isinstance(rejection, str)
        assert json.loads(rejection)["code"] == "source_not_available"
    assert (
        client.portal.call(candidates.read, following.writer.scope).position == following_position
    )
    assert references(client, following.writer, following_position.revision_id) == confirmed
