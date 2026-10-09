"""Model locators stay short and durable without becoming domain identities."""

import asyncio
import json
import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.job_description.navigation import jd_read_ref
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.workflows.jd_model_references import JdModelReferences
from caliburn.workflows.jd_reads import JdReadWorkflow
from caliburn.workflows.memory_reads import PublishedMemoryRead
from tests.integration.test_jd_item_revision import setup_item
from tests.integration.test_jd_source_tool_actions import invoke, source_tools

pytestmark = pytest.mark.postgres


def read(client, reader, view="map", read_ref=None):
    return json.loads(
        client.portal.call(
            reader.invoke, "read_jd", json.dumps({"view": view, "read_ref": read_ref})
        )
    )


def reader_for(client, writer):
    return JdReadTools(
        JdReadWorkflow(client.app.state.database.sessions),
        PublishedMemoryRead(writer.scope, None, 1),
    )


def test_short_map_item_citation_roundtrip_preserves_original_identity(client: TestClient):
    writer, candidates, before = setup_item(client)
    reader = reader_for(client, writer)
    tools = source_tools(client, writer)
    task_ref = read(client, reader)["unassigned_work_tasks"][0]["read_ref"]
    assert re.fullmatch(r"task_[1-9][0-9]{0,9}", task_ref), task_ref
    detail = read(client, reader, "item", task_ref)
    assert re.fullmatch(r"outcome_[1-9][0-9]{0,9}", detail["outcomes"][0]["read_ref"])
    literal = "保留正文中的 task_1 與 " + jd_read_ref(before.work.tasks[0])
    assert (
        invoke(
            client,
            tools,
            "revise_jd_item",
            {
                "read_ref": task_ref,
                "changes": [
                    {"action": "set_field", "field": "description", "value": literal},
                    {
                        "action": "add_source",
                        "target": {"kind": "item"},
                        "source": {"kind": "current_input"},
                    },
                ],
            },
        )
        == "updated"
    )
    # A fresh handler (as on recovery) must resolve the same locator and untouched text.
    reader = reader_for(client, writer)
    current = read(client, reader, "item", task_ref)
    assert current["description"] == literal
    citation_ref = current["supporting_sources"][0]["citation_ref"]
    assert re.fullmatch(r"citation_[1-9][0-9]{0,9}", citation_ref)
    assert invoke(
        client,
        tools,
        "revise_jd_item",
        {
            "read_ref": task_ref,
            "changes": [
                {
                    "action": "confirm_reference_alignment",
                    "target": {"kind": "item"},
                    "citation_ref": citation_ref,
                },
            ],
        },
    ) in {"aligned", "unchanged"}
    after = client.portal.call(candidates.read, writer.scope)
    assert after.work.tasks[0].task_id == before.work.tasks[0].task_id
    # Model inputs use issued short locators; canonical identities stay internal.
    assert (
        read(client, reader, "item", jd_read_ref(before.work.tasks[0]))["code"]
        == "target_not_found"
    )


def test_short_locator_cannot_cross_file_or_retarget_after_deletion(client: TestClient):
    writer, candidates, before = setup_item(client)
    reader = reader_for(client, writer)
    task_ref = read(client, reader)["unassigned_work_tasks"][0]["read_ref"]
    assert re.fullmatch(r"task_[1-9][0-9]{0,9}", task_ref), task_ref
    foreign_writer, _, _ = setup_item(client)
    foreign = reader_for(client, foreign_writer)
    read(client, foreign)  # Both files have their own tasks, not a positional alias.
    assert read(client, foreign, "item", task_ref)["code"] == "target_not_found"
    tools = source_tools(client, writer)
    assert invoke(client, tools, "delete_jd_item", {"read_ref": task_ref}) == "deleted"
    assert read(client, reader, "item", task_ref)["code"] == "target_not_found"
    assert read(client, reader, "item", "task_9999999999")["code"] == "target_not_found"
    created = invoke(
        client,
        tools,
        "create_jd_task",
        {
            "parent_read_ref": None,
            "title": before.work.tasks[0].title,
            "description": None,
            "outcomes": [],
            "requirements": [],
            "required_knowledge": [],
            "required_skills": [],
            "supporting_sources": [],
        },
    )
    new_ref = created.removeprefix("created · read_ref: ")
    assert re.fullmatch(r"task_[1-9][0-9]{0,9}", new_ref)
    assert new_ref != task_ref
    assert read(client, reader, "item", task_ref)["code"] == "target_not_found"
    assert read(client, reader)["unassigned_work_tasks"][0]["read_ref"] == new_ref


def test_creation_replay_recovers_after_alias_storage_failure(client, monkeypatch):
    writer, candidates, _ = setup_item(client)
    tools = source_tools(client, writer)
    command = client.portal.call(
        tools.prepare,
        "create_jd_item",
        json.dumps(
            {
                "item": {
                    "kind": "responsibility_area",
                    "title": "盤點",
                    "scope_text": None,
                    "supporting_sources": [],
                }
            }
        ),
        uuid4(),
    )
    assert not isinstance(command, str), command
    saved = snapshot_jd_write(command)

    async def failed_assignment(_refs):
        raise TimeoutError("synthetic alias storage outage after JD commit")

    with monkeypatch.context() as patch:
        patch.setattr(tools.references, "assign", failed_assignment)
        with pytest.raises(TimeoutError):
            client.portal.call(tools.execute, restore_jd_write(saved))
    committed = client.portal.call(candidates.read, writer.scope)
    assert len(committed.work.areas) == 1
    restored_tools = source_tools(client, writer)
    result = client.portal.call(restored_tools.execute, restore_jd_write(saved))
    assert re.fullmatch(r"created · read_ref: area_[1-9][0-9]*", result)
    assert client.portal.call(restored_tools.execute, restore_jd_write(saved)) == result
    assert client.portal.call(candidates.read, writer.scope) == committed
    assert (
        read(client, reader_for(client, writer))["responsibility_areas"][0]["read_ref"]
        == result.split(": ")[1]
    )


def test_alias_allocation_is_concurrent_durable_and_type_checked(client):
    writer, _, before = setup_item(client)
    sessions = client.app.state.database.sessions
    canonical = jd_read_ref(before.work.tasks[0])

    async def scenario():
        # Independent sessions contend for one identity, not one alias per process.
        first, second = await asyncio.gather(
            *(
                JdModelReferences(sessions, writer.scope.job_file_id).assign((canonical,))
                for _ in range(2)
            )
        )
        assert first == second
        fresh = JdModelReferences(sessions, writer.scope.job_file_id)
        assert await fresh.resolve((first[canonical],)) == {first[canonical]: canonical}
        return first[canonical]

    task_ref = client.portal.call(scenario)
    reader = reader_for(client, writer)
    assert (
        read(client, reader, "item", task_ref.replace("task_", "skill_"))["code"]
        == "target_not_found"
    )
    assert read(client, reader, "item", "task_9223372036854775808")["code"] == "target_not_found"


def test_nested_locators_move_and_link_without_rewriting_text(client):
    writer, _, _ = setup_item(client)
    reader = reader_for(client, writer)
    tools = source_tools(client, writer)
    jd_map = read(client, reader)
    task_ref = jd_map["unassigned_work_tasks"][0]["read_ref"]
    skill_ref = jd_map["required_skills"][0]["read_ref"]
    outcome_ref = read(client, reader, "item", task_ref)["outcomes"][0]["read_ref"]
    assert (
        invoke(
            client,
            tools,
            "revise_jd_item",
            {
                "read_ref": task_ref,
                "changes": [
                    {"action": "revise_detail", "detail_read_ref": outcome_ref, "text": "修訂成果"},
                    {
                        "action": "set_capability",
                        "capability_read_ref": skill_ref,
                        "relationship": "link",
                        "supporting_sources": [],
                    },
                ],
            },
        )
        == "updated"
    )
    area_ref = invoke(
        client,
        tools,
        "create_jd_item",
        {
            "item": {
                "kind": "responsibility_area",
                "title": "網站",
                "scope_text": None,
                "supporting_sources": [],
            }
        },
    ).split(": ")[1]
    assert (
        invoke(
            client,
            tools,
            "move_jd_item",
            {
                "read_ref": task_ref,
                "destination": {"kind": "task_parent", "parent_read_ref": area_ref},
                "position": {"kind": "last"},
                "content_changes": [],
            },
        )
        == "moved"
    )
    moved = read(client, reader)["responsibility_areas"][0]["work_tasks"][0]
    assert moved["read_ref"] == task_ref
    detail = read(client, reader, "item", task_ref)
    assert detail["outcomes"][0] == {
        "read_ref": outcome_ref,
        "text": "修訂成果",
        "supporting_sources": [],
    }
    assert detail["required_skills"][0]["read_ref"] == skill_ref


@pytest.mark.parametrize("operation", ["delete_jd_item", "move_jd_item"])
def test_lifecycle_facts_survive_commit_before_output_and_later_edit(
    client, monkeypatch, operation
):
    writer, candidates, _ = setup_item(client)
    tools = source_tools(client, writer)
    reader = reader_for(client, writer)
    task_ref = read(client, reader)["unassigned_work_tasks"][0]["read_ref"]
    created = invoke(
        client,
        tools,
        "create_jd_item",
        {
            "item": {
                "kind": "responsibility_area",
                "title": "盤點",
                "scope_text": None,
                "supporting_sources": [],
            }
        },
    )
    area_ref = created.split(": ")[1]
    assert (
        invoke(
            client,
            tools,
            "move_jd_item",
            {
                "read_ref": task_ref,
                "destination": {"kind": "task_parent", "parent_read_ref": area_ref},
                "position": {"kind": "last"},
                "content_changes": [],
            },
        )
        == "moved"
    )
    arguments = (
        {"read_ref": area_ref}
        if operation == "delete_jd_item"
        else {
            "read_ref": task_ref,
            "destination": {"kind": "task_parent", "parent_read_ref": None},
            "position": {"kind": "last"},
            "content_changes": [],
        }
    )
    prepared = client.portal.call(tools.prepare, operation, json.dumps(arguments), uuid4())
    assert not isinstance(prepared, str)
    saved = snapshot_jd_write(prepared)
    payload = json.loads(saved["payload"])
    assert "result_message" not in payload
    assert payload.get("detached_task_count", payload.get("detached_from_area")) == 1
    workflow = tools.deletions if operation == "delete_jd_item" else tools.movements
    execute = workflow.execute

    async def committed_without_output(writer, command):
        await execute(writer, command)
        raise ConnectionError("synthetic interruption after lifecycle commit")

    with monkeypatch.context() as patch:
        patch.setattr(workflow, "execute", committed_without_output)
        with pytest.raises(ConnectionError, match="after lifecycle commit"):
            client.portal.call(tools.execute, restore_jd_write(saved))
    committed = client.portal.call(candidates.read, writer.scope)
    assert committed.work.tasks[0].area_id is None
    assert (
        invoke(
            client,
            tools,
            "revise_jd_profile",
            {
                "changes": [
                    {"action": "set_field", "field": "job_title", "value": "後續編輯"},
                ]
            },
        )
        == "updated"
    )
    later = client.portal.call(candidates.read, writer.scope)
    fresh_tools = source_tools(client, writer)
    expected = (
        "deleted · 1 項任務保留並轉為未歸屬"
        if operation == "delete_jd_item"
        else "moved · 原所屬職責已解除，任務現在未歸屬"
    )
    assert client.portal.call(fresh_tools.execute, restore_jd_write(saved)) == expected
    assert client.portal.call(fresh_tools.execute, restore_jd_write(saved)) == expected
    assert client.portal.call(candidates.read, writer.scope) == later
