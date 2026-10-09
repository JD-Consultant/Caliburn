"""Model feedback must match its tool and preserve the full committed intent."""

import json
from uuid import uuid4

import pytest

from caliburn.adapters.occupation_references import ReferenceClientError
from caliburn.transport.model_tools.occupation_references import (
    occupation_reference_definitions,
)
from tests.unit.test_occupation_reference_tools import bound_tools


def test_selection_contract_explains_full_replacement_and_retained_references():
    definition = next(
        item
        for item in occupation_reference_definitions()
        if item["name"] == "select_occupation_references"
    )
    assert "取代" in definition["description"]
    assert "保留" in definition["parameters"]["properties"]["reference_ids"]["description"]
    assert "取代" in definition["parameters"]["properties"]["reference_ids"]["description"]


@pytest.mark.parametrize(
    ("name", "arguments", "expected", "unrelated"),
    [
        ("search_occupation_references", '{"query":" "}', "query", "add/remove"),
        ("read_occupation_reference", '{"reference_id":"ref_frontend"}', "task_id", "add/remove"),
        ("read_occupation_reference_state", '{"unexpected":1}', "{}", "add/remove"),
        ("select_occupation_references", '{"reference_ids":null}', "reference_ids", "add/remove"),
        ("update_excluded_work", '{"add":[],"remove":[]}', "add/remove", "query"),
    ],
)
async def test_invalid_arguments_offer_the_actual_tools_legal_next_step(
    name,
    arguments,
    expected,
    unrelated,
):
    tools, workflow, client = bound_tools()
    if name in tools.read_names:
        result = await tools.invoke(name, arguments)
    else:
        result = await tools.prepare(name, arguments, uuid4())
    assert isinstance(result, str)
    rejection = json.loads(result)
    assert rejection["status"] == "rejected"
    assert rejection["code"] == "invalid_arguments"
    assert expected in rejection["next_action"]
    assert unrelated not in rejection["next_action"]
    assert client.calls == workflow.executions == []


@pytest.mark.parametrize(
    ("code", "expected", "unrelated"),
    [
        ("timeout", "App", "核對公版定位"),
        ("reference_service_unavailable", "App", "核對公版定位"),
        ("reference_index_incompatible", "索引", "核對公版定位"),
        ("reference_not_found", "定位", "add/remove"),
    ],
)
async def test_external_failure_feedback_matches_the_failure_class(code, expected, unrelated):
    tools, _, client = bound_tools()
    client.error = ReferenceClientError(code)
    result = json.loads(await tools.invoke("search_occupation_references", '{"query":"網站開發"}'))
    assert result["code"] == code
    assert expected in result["next_action"]
    assert unrelated not in result["next_action"]
    assert "references" not in result


async def test_successful_large_write_returns_a_bounded_receipt_without_losing_saved_scope():
    tools, workflow, _ = bound_tools()
    tools.max_result_characters = 64
    scope = "正式環境部署由維運團隊負責；" * 100
    workflow.projected_state = {"selected_reference_ids": None, "excluded_work": [scope]}
    prepared = await tools.prepare(
        "update_excluded_work",
        json.dumps({"add": [scope], "remove": []}),
        uuid4(),
    )
    assert isinstance(prepared, dict)
    result = await tools.execute(json.loads(json.dumps(prepared)))
    assert json.loads(result) == {"status": "updated"}
    assert len(result) <= tools.max_result_characters
    assert workflow.executions[0][1].state.excluded_work == (scope,)
    assert scope not in result
    # Full state remains available through the read tool and its honest capacity refusal.
    read = json.loads(await tools.invoke("read_occupation_reference_state", "{}"))
    assert read["code"] == "read_limit_exceeded"
