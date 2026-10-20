"""Task-hint wire shapes stay self-contained, bounded, and free of occupation identity fields."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.contracts.generated.tools.search_task_hints_arguments import (
    SearchTaskHintsArguments,
)
from caliburn.contracts.generated.tools.task_hint_search_result import TaskHintSearchResult

CONTRACTS = Path(__file__).parents[2] / "contracts" / "tools"


def schema(name: str) -> dict[str, object]:
    return json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_search_arguments_round_trip_and_reject_extra_fields() -> None:
    payload = {"query": "每天整理貨架並補貨"}
    validator = Draft202012Validator(schema("search-task-hints-arguments"))
    validator.validate(payload)
    assert SearchTaskHintsArguments.model_validate(payload).model_dump() == payload
    invalid = {**payload, "unexpected_field": "not allowed"}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        SearchTaskHintsArguments.model_validate(invalid)


@pytest.mark.parametrize(
    "query",
    ["", "   ", "　", "長" * 12001, 42, None],
    ids=["empty", "spaces", "ideographic_space", "oversized", "non_string_int", "none"],
)
def test_search_arguments_reject_blank_or_oversized_query(query: object) -> None:
    payload = {"query": query}
    assert not Draft202012Validator(schema("search-task-hints-arguments")).is_valid(payload)
    with pytest.raises(ValidationError):
        SearchTaskHintsArguments.model_validate(payload)


def test_result_round_trips_and_has_no_occupation_identity_property() -> None:
    payload = {
        "hints": [
            {
                "names": [{"code": "T1", "name": "補貨上架"}],
                "competency_blocks": [
                    {
                        "competency_level": 2,
                        "outputs": [{"code": "O1", "name": "完整上架貨架"}],
                        "indicators": [{"code": "P1", "text": "依先進先出原則排放"}],
                        "knowledge": [{"code": "K1", "name": "商品分類原則"}],
                        "skills": [{"code": "S1", "name": "快速盤點"}],
                    }
                ],
            }
        ]
    }
    result_schema = schema("task-hint-search-result")
    Draft202012Validator(result_schema).validate(payload)
    assert json.loads(TaskHintSearchResult.model_validate(payload).model_dump_json()) == payload
    serialized = json.dumps(result_schema)
    for forbidden in ("ocs_code", "ocs_name", "ocu_code", "ocu_name", "reference_id", "unit_id"):
        assert forbidden not in serialized


def test_result_rejects_extra_fields_at_every_level() -> None:
    result_schema = schema("task-hint-search-result")
    validator = Draft202012Validator(result_schema)
    assert not validator.is_valid({"hints": [], "unexpected_field": "not allowed"})
    assert not validator.is_valid(
        {"hints": [{"names": [], "competency_blocks": [], "ocs_code": "X"}]}
    )
    with pytest.raises(ValidationError):
        TaskHintSearchResult.model_validate({"hints": [], "unexpected_field": "not allowed"})


def test_empty_hints_is_a_valid_result() -> None:
    payload: dict[str, object] = {"hints": []}
    Draft202012Validator(schema("task-hint-search-result")).validate(payload)
    assert TaskHintSearchResult.model_validate(payload).model_dump() == payload
