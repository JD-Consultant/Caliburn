"""HTTP status describes this request; JD status describes the original write."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource
import pytest
from result_fixtures import observed_result

from jd_relational.generated.http_results import HttpProblem
from jd_relational.http_results import project_result
from jd_relational.result_transport import ResultValidationError


REQUEST = UUID("833da1c3-af89-4cdd-b4d5-65399e88a44b")
CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
RESULT_SCHEMA = json.loads((CONTRACTS / "jd-result.schema.json").read_text(encoding="utf-8"))
PROBLEM_SCHEMA = json.loads((CONTRACTS / "jd-http.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resource("jd-result.schema.json", Resource.from_contents(RESULT_SCHEMA))


def accepted_by_all_contracts(value, expected):
    source_accepts = Draft202012Validator(PROBLEM_SCHEMA, registry=REGISTRY).is_valid(value)
    published_accepts = Draft202012Validator(HttpProblem.model_json_schema(mode="validation")).is_valid(value)
    try:
        parsed = HttpProblem.model_validate(value, strict=True).model_dump(mode="json")
        dto_accepts = True
        assert parsed == value
    except ValidationError:
        dto_accepts = False
    assert (source_accepts, published_accepts, dto_accepts) == (expected,) * 3


def problem_with(value, status=500, title="Internal Server Error"):
    return {"type": "about:blank", "title": title, "status": status,
            "detail": "Synthetic observation for a contract counterexample.",
            "instance": f"urn:uuid:{REQUEST}", "jd_result": value}


@pytest.mark.parametrize("status,http_status", [
    ("invalid_input", 422), ("target_missing", 404), ("stale_view", 409), ("relationship_conflict", 409),
    ("dependent_items", 409), ("busy", 409), ("archived", 409), ("operation_conflict", 409), ("save_failed", 500),
])
def test_failed_write_and_successful_lookup_keep_the_same_observation(status, http_status):
    value = observed_result(status)
    before = deepcopy(value)
    write = project_result(value, request_id=REQUEST)
    assert write.status_code == http_status
    assert write.media_type == "application/problem+json"
    assert write.body["type"] == "about:blank"
    assert write.body["status"] == write.status_code
    assert write.body["instance"] == f"urn:uuid:{REQUEST}"
    assert write.body["jd_result"] == value
    assert write.body["detail"] == value["error"]["message"]
    accepted_by_all_contracts(write.body, True)
    found = project_result(value, request_id=REQUEST, context="lookup")
    assert found.status_code == 200
    assert found.media_type == "application/json"
    assert found.body == value == before
    assert write.headers == found.headers == {"Cache-Control": "no-store"}


@pytest.mark.parametrize("status", ["save_failed", "stale_view", "outcome_unknown"])
def test_unresolved_write_is_accepted_but_never_reported_as_confirmed(status):
    value = observed_result(status, "unconfirmed")
    response = project_result(value, request_id=REQUEST)
    assert response.status_code == 202
    assert response.media_type == "application/json"
    assert response.body == value
    assert response.body["receipt_durability"] == "unconfirmed"
    assert response.body["next_action"] == "reconcile_operation"
    assert "Retry-After" not in response.headers  # No hidden retry policy.
    assert project_result(value, request_id=REQUEST, context="lookup").status_code == 200


@pytest.mark.parametrize("status", ["committed", "no_change"])
def test_confirmed_result_remains_unchanged_in_http_projection(status):
    value = observed_result(status)
    response = project_result(value, request_id=REQUEST)
    assert response.status_code == 200
    assert response.body == value
    assert response.headers == {"Cache-Control": "no-store"}


def test_bad_projection_input_is_not_reclassified_as_a_failed_write():
    with pytest.raises(ResultValidationError, match="invalid_result"):
        project_result({"status": "committed"}, request_id=REQUEST)
    with pytest.raises(ValueError, match="invalid_http_context"):
        project_result(observed_result(), request_id="untrusted request id")


@pytest.mark.parametrize("status", ["committed", "no_change"])
def test_problem_cannot_contain_a_successful_write(status):
    accepted_by_all_contracts(problem_with(observed_result(status)), False)


@pytest.mark.parametrize("status", [
    "invalid_input", "target_missing", "stale_view", "relationship_conflict",
    "dependent_items", "save_failed", "outcome_unknown",
])
def test_problem_cannot_contain_an_unresolved_bound_write(status):
    accepted_by_all_contracts(problem_with(observed_result(status, "unconfirmed")), False)


@pytest.mark.parametrize("status,wrong_status,wrong_title", [
    ("invalid_input", 404, "Not Found"), ("target_missing", 500, "Internal Server Error"),
    ("stale_view", 500, "Internal Server Error"), ("relationship_conflict", 422, "Unprocessable Entity"),
    ("dependent_items", 404, "Not Found"), ("busy", 500, "Internal Server Error"),
    ("archived", 404, "Not Found"), ("operation_conflict", 422, "Unprocessable Entity"),
    ("save_failed", 409, "Conflict"),
])
def test_problem_status_cannot_contradict_its_write_observation(status, wrong_status, wrong_title):
    accepted_by_all_contracts(problem_with(observed_result(status), wrong_status, wrong_title), False)


@pytest.mark.parametrize("status", ["invalid_input", "target_missing", "stale_view", "save_failed"])
def test_about_blank_title_is_the_status_title(status):
    value = project_result(observed_result(status), request_id=REQUEST).body
    value["title"] = "Unrelated HTTP status"
    accepted_by_all_contracts(value, False)


@pytest.mark.parametrize("status", ["invalid_input", "save_failed"])
def test_unbound_rejections_remain_valid_problems(status):
    value = project_result(observed_result(status, "unbound"), request_id=REQUEST).body
    accepted_by_all_contracts(value, True)
