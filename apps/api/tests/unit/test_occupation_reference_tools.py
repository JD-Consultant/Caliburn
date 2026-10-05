"""Dormant tools project references and checkpoint only App-bound state changes."""

import json
from dataclasses import replace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.adapters.occupation_reference_models import (
    OccupationReference,
    OccupationReferenceHit,
    ReferenceCompetencyBlock,
    ReferenceEvidence,
    ReferenceNamedContent,
    ReferenceRetrievalPolicy,
    ReferenceSearchResult,
    ReferenceTaskDetail,
    ReferenceTaskName,
    ReferenceTaskSummary,
    ReferenceUnit,
)
from caliburn.adapters.occupation_references import OccupationReferenceClient, ReferenceClientError
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    ReferenceStatePosition,
    update_excluded_work,
)
from caliburn.transport.model_tools.occupation_references import (
    OccupationReferenceTools,
    occupation_reference_definitions,
)
from caliburn.workflows.occupation_references import (
    OccupationReferenceWorkflow,
    ReferenceStateChange,
)


def reference():
    return OccupationReference(
        "ref_frontend",
        "a" * 64,
        "前端.pdf",
        "ocs_frontend",
        "網站前端工程師",
        "設計及實作網站介面",
        "all_parsed_task_groups",
        (
            ReferenceUnit(
                "u1",
                "U1",
                "前端開發",
                (
                    ReferenceTaskSummary("u1-t1", (ReferenceTaskName("T1", "實作畫面"),), 1),
                    ReferenceTaskSummary("u1-t2", (ReferenceTaskName("T2", "可用性測試"),), 1),
                ),
            ),
        ),
    )


class RecordingClient(OccupationReferenceClient):
    def __init__(self):
        self.calls = []
        self.error = None

    async def search(self, query, *, limit=5):
        self.calls.append(("search", query, limit))
        if self.error:
            raise self.error
        return ReferenceSearchResult(
            (
                OccupationReferenceHit(
                    reference(),
                    ReferenceEvidence(0.8, 0.9, ("u1-t1",), True, "not_evaluated"),
                    7.8,
                ),
            ),
            ReferenceRetrievalPolicy(
                "plain",
                20,
                1,
                "exact_dense_cosine",
                "full_union_before_rerank",
                "bge-m3",
                1024,
                "reranker",
                "pinned",
            ),
        )

    async def read(self, reference_id):
        self.calls.append(("read", reference_id))
        return reference()

    async def read_task(self, reference_id, task_id):
        self.calls.append(("read_task", reference_id, task_id))
        return ReferenceTaskDetail(
            reference_id,
            "a" * 64,
            task_id,
            "u1",
            (ReferenceTaskName("T1", "實作畫面"),),
            (
                ReferenceCompetencyBlock(
                    3,
                    (ReferenceNamedContent("O1", "可操作畫面"),),
                    (),
                    (),
                    (),
                ),
            ),
        )


class RecordingWorkflow(OccupationReferenceWorkflow):
    def __init__(self, writer):
        self.position = ReferenceStatePosition(
            writer.scope.execution_id,
            uuid4(),
            uuid4(),
            OccupationReferenceState(),
        )
        self.preparations = []
        self.executions = []
        self.reads = []
        self.error = None
        self.projected_state = {"selected_reference_ids": None, "excluded_work": []}

    async def read(self, writer):
        self.reads.append(writer)
        return self.projected_state

    async def prepare_select(self, writer, reference_ids, operation_id):
        self.preparations.append(("select", writer, reference_ids, operation_id))
        return ReferenceStateChange(
            writer.scope.job_file_id,
            operation_id,
            self.position,
            replace(self.position.state, selected_reference_ids=reference_ids),
        )

    async def prepare_excluded_work(self, writer, add, remove, operation_id):
        self.preparations.append(("exclude", writer, add, remove, operation_id))
        if self.error:
            raise self.error
        return ReferenceStateChange(
            writer.scope.job_file_id,
            operation_id,
            self.position,
            update_excluded_work(self.position.state, add, remove),
        )

    async def execute(self, writer, change):
        self.executions.append((writer, change))
        return self.projected_state


def bound_tools():
    writer = ExecutionWriter(
        ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN),
        uuid4(),
    )
    workflow = RecordingWorkflow(writer)
    client = RecordingClient()
    return OccupationReferenceTools(workflow, client, writer), workflow, client


def test_five_dormant_tools_have_generated_strict_contracts_and_no_app_identity_inputs():
    tools, _, _ = bound_tools()
    definitions = occupation_reference_definitions()
    assert tools.definitions() == definitions
    assert tuple(item["name"] for item in definitions) == tools.names
    assert len(definitions) == 5
    assert set(tools.names).isdisjoint(item["name"] for item in consultant_tool_definitions())
    for definition in definitions:
        assert definition["strict"] is True
        schema = definition["parameters"]
        assert schema["additionalProperties"] is False
        assert set(schema["properties"]) == set(schema["required"])
        assert {"job_file_id", "execution_id", "operation_id", "revision_id"}.isdisjoint(
            schema["properties"],
        )


async def test_explicit_excluded_work_is_a_mutation_without_answer_source_arguments():
    tools, workflow, _ = bound_tools()
    result = await tools.prepare(
        "update_excluded_work",
        '{"add":["正式環境部署"],"remove":[]}',
        uuid4(),
    )
    assert isinstance(result, dict)
    assert workflow.executions == []


async def test_search_keeps_unmatched_tasks_and_text_but_omits_ranking_diagnostics():
    tools, workflow, client = bound_tools()
    query = "我把畫面和自己寫的服務接起來。"
    result = json.loads(
        await tools.invoke("search_occupation_references", json.dumps({"query": query}))
    )
    assert client.calls == [("search", query, 5)]
    assert set(result) == {"references"}
    assert result["references"][0]["catalog_scope"] == "all_parsed_task_groups"
    tasks = result["references"][0]["units"][0]["tasks"]
    assert [task["task_id"] for task in tasks] == ["u1-t1", "u1-t2"]
    assert "rerank_logit" not in json.dumps(result)
    assert workflow.preparations == []


@pytest.mark.parametrize("task_id", [None, "u1-t1"])
async def test_reference_read_selects_full_catalog_or_task_without_selection_gate(task_id):
    tools, workflow, client = bound_tools()
    output = json.loads(
        await tools.invoke(
            "read_occupation_reference",
            json.dumps(
                {
                    "reference_id": "ref_frontend",
                    "task_id": task_id,
                }
            ),
        )
    )
    assert output["reference_id"] == "ref_frontend"
    if task_id is None:
        assert client.calls == [("read", "ref_frontend")]
        assert len(output["units"][0]["tasks"]) == 2
    else:
        assert client.calls == [("read_task", "ref_frontend", task_id)]
        assert output["competency_blocks"][0]["outputs"][0]["name"] == "可操作畫面"
    assert workflow.preparations == []


@pytest.mark.parametrize("selection", [None, []])
async def test_state_read_preserves_not_selected_and_reviewed_empty(selection):
    tools, workflow, client = bound_tools()
    workflow.projected_state["selected_reference_ids"] = selection
    result = json.loads(await tools.invoke("read_occupation_reference_state", "{}"))
    assert result == {"selected_reference_ids": selection, "excluded_work": []}
    assert len(workflow.reads) == 1
    assert client.calls == []
    assert workflow.preparations == []


@pytest.mark.parametrize(
    ("name", "arguments"),
    [
        ("search_occupation_references", '{"query":"   "}'),
        ("search_occupation_references", '{"query":42}'),
        ("search_occupation_references", '{"query":"介面","limit":100}'),
        ("read_occupation_reference", '{"reference_id":"ref_frontend"}'),
        ("read_occupation_reference", '{"reference_id":"../secret","task_id":null}'),
        ("read_occupation_reference_state", '{"job_file_id":"other"}'),
    ],
)
async def test_invalid_read_arguments_do_not_reach_workflow_or_provider(name, arguments):
    tools, workflow, client = bound_tools()
    assert json.loads(await tools.invoke(name, arguments))["code"] == "invalid_arguments"
    assert client.calls == workflow.reads == []


@pytest.mark.parametrize("code", ["timeout", "reference_service_unavailable", "invalid_response"])
async def test_provider_failure_is_explicit_and_never_becomes_empty_success(code):
    tools, _, client = bound_tools()
    client.error = ReferenceClientError(code)
    output = json.loads(await tools.invoke("search_occupation_references", '{"query":"開發介面"}'))
    assert output["status"] == "rejected"
    assert output["code"] == code
    assert "references" not in output


async def test_select_prepares_fixed_change_and_json_replay_preserves_app_identities():
    tools, workflow, _ = bound_tools()
    operation_id = uuid4()
    prepared = await tools.prepare(
        "select_occupation_references", '{"reference_ids":[]}', operation_id
    )
    assert isinstance(prepared, dict)
    assert workflow.executions == []
    saved_position = workflow.position
    workflow.position = replace(workflow.position, revision_id=uuid4())
    result = await tools.execute(json.loads(json.dumps(prepared)))
    assert json.loads(result) == {"status": "updated"}
    change = workflow.executions[0][1]
    assert change.operation_id == operation_id
    assert change.position == saved_position
    assert change.state.selected_reference_ids == ()


async def test_excluded_work_update_freezes_exact_scopes_without_calling_reference_service():
    tools, workflow, client = bound_tools()
    operation_id = uuid4()
    prepared = await tools.prepare(
        "update_excluded_work",
        '{"add":["正式環境部署","正式環境部署"],"remove":[]}',
        operation_id,
    )
    assert isinstance(prepared, dict)
    assert workflow.preparations[0][2:] == (("正式環境部署", "正式環境部署"), (), operation_id)
    assert prepared["change"]["state"]["excluded_work"] == ["正式環境部署"]
    assert workflow.executions == client.calls == []


async def test_employee_correction_can_remove_previous_excluded_scope():
    tools, workflow, client = bound_tools()
    workflow.position = replace(
        workflow.position,
        state=OccupationReferenceState(excluded_work=("正式環境部署", "薪資核算")),
    )
    prepared = await tools.prepare(
        "update_excluded_work",
        '{"add":[],"remove":["正式環境部署"]}',
        uuid4(),
    )
    assert isinstance(prepared, dict)
    assert prepared["change"]["state"]["excluded_work"] == ["薪資核算"]
    assert client.calls == []


@pytest.mark.parametrize(
    "arguments",
    [
        '{"add":["部署"]}',
        '{"add":[" "],"remove":[]}',
        '{"add":[42],"remove":[]}',
        '{"add":["部署"],"remove":[],"answer_refs":[{"kind":"current_input"}]}',
        '{"add":["部署"],"remove":[],"job_file_id":"other"}',
    ],
)
async def test_exclusion_schema_rejects_old_source_metadata_and_malformed_scopes(arguments):
    tools, workflow, _ = bound_tools()
    output = await tools.prepare("update_excluded_work", arguments, uuid4())
    assert json.loads(output)["code"] == "invalid_arguments"
    assert workflow.preparations == []


@pytest.mark.parametrize(
    "arguments",
    [
        '{"add":[],"remove":[]}',
        '{"add":["部署"],"remove":["部署"]}',
        '{"add":[],"remove":["未記錄的工作範圍"]}',
    ],
)
async def test_invalid_exclusion_change_reports_domain_rejection_without_write(arguments):
    tools, workflow, _ = bound_tools()
    output = await tools.prepare("update_excluded_work", arguments, uuid4())
    assert json.loads(output)["code"] == "invalid_arguments"
    assert workflow.executions == []


async def test_removed_confirmation_tool_is_not_accepted():
    tools, workflow, _ = bound_tools()
    output = await tools.prepare(
        "record_work_confirmation",
        '{"subject":"部署","answer_refs":[]}',
        uuid4(),
    )
    assert json.loads(output)["code"] == "scope_not_allowed"
    assert workflow.preparations == []


async def test_checkpoint_from_another_scope_never_reaches_execute():
    tools, workflow, _ = bound_tools()
    other, _, _ = bound_tools()
    prepared = await other.prepare("select_occupation_references", '{"reference_ids":[]}', uuid4())
    with pytest.raises(ValueError):
        await tools.execute(prepared)
    assert workflow.executions == []


@pytest.mark.parametrize("name", ["select_occupation_references", "update_excluded_work", "other"])
async def test_read_path_cannot_execute_mutations(name):
    tools, workflow, client = bound_tools()
    assert json.loads(await tools.invoke(name, "{}"))["code"] == "scope_not_allowed"
    assert workflow.preparations == workflow.executions == client.calls == []


async def test_multiple_searches_can_contribute_more_than_five_selected_references():
    tools, workflow, _ = bound_tools()
    output = await tools.prepare(
        "select_occupation_references",
        json.dumps(
            {
                "reference_ids": [f"ref_{index}" for index in range(6)],
            }
        ),
        uuid4(),
    )
    assert isinstance(output, dict)
    assert workflow.preparations[0][2] == tuple(f"ref_{index}" for index in range(6))


@pytest.mark.parametrize("location", ["envelope", "change", "state"])
async def test_saved_command_rejects_unknown_fields_including_nested_content(location):
    tools, workflow, _ = bound_tools()
    prepared = await tools.prepare("select_occupation_references", '{"reference_ids":[]}', uuid4())
    assert isinstance(prepared, dict)
    if location == "envelope":
        prepared["unexpected"] = "discarding a field could lose intent"
    elif location == "change":
        prepared["change"]["unexpected"] = "discarding a field could lose intent"
    else:
        prepared["change"]["state"]["complete"] = True
    with pytest.raises(ValidationError):
        await tools.execute(prepared)
    assert workflow.executions == []


@pytest.mark.parametrize("location", ["change", "position"])
@pytest.mark.parametrize("missing_field", ["selected_reference_ids", "excluded_work"])
async def test_saved_state_cannot_omit_a_field_and_silently_restore_a_domain_default(
    location,
    missing_field,
):
    tools, workflow, _ = bound_tools()
    workflow.position = replace(
        workflow.position,
        state=OccupationReferenceState(("ref_frontend",), ("正式環境部署",)),
    )
    prepared = await tools.prepare(
        "update_excluded_work",
        '{"add":["薪資核算"],"remove":[]}',
        uuid4(),
    )
    assert isinstance(prepared, dict)
    saved_state = prepared["change"] if location == "change" else prepared["change"]["position"]
    del saved_state["state"][missing_field]
    with pytest.raises(ValueError):
        await tools.execute(json.loads(json.dumps(prepared)))
    assert workflow.executions == []


async def test_large_reference_result_rejects_whole_read_instead_of_silent_truncation():
    tools, _, _ = bound_tools()
    tools.max_result_characters = 50
    result = json.loads(await tools.invoke("search_occupation_references", '{"query":"開發介面"}'))
    assert result["code"] == "read_limit_exceeded"
    assert "references" not in result


async def test_state_contains_only_selected_references_and_excluded_work():
    tools, workflow, _ = bound_tools()
    workflow.projected_state["excluded_work"] = ["正式環境部署"]
    result = json.loads(await tools.invoke("read_occupation_reference_state", "{}"))
    assert result == {"selected_reference_ids": None, "excluded_work": ["正式環境部署"]}


async def test_excluded_work_is_not_added_to_search_input_or_used_to_drop_public_references():
    tools, workflow, client = bound_tools()
    workflow.projected_state["excluded_work"] = ["正式環境部署"]
    result = json.loads(await tools.invoke("search_occupation_references", '{"query":"開發介面"}'))
    assert client.calls == [("search", "開發介面", 5)]
    assert result["references"][0]["reference_id"] == "ref_frontend"
    assert workflow.reads == []
