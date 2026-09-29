"""Memory read schemas and generated DTOs expose choices, not execution scope."""

import json
from importlib import import_module
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError
from referencing import Registry, Resource

SCHEMAS = Path(__file__).parents[2] / "contracts/tools"
TARGET = {"target_title": " 月末庫存盤點 ", "description": "盤點帳實差異。"}
CONTENT = {
    "title": " 月末庫存盤點 ",
    "description": "盤點帳實差異。",
    "body": "# 盤點\n逐項核對。\n",
}
MESSAGE = {"interview_sequence": 1, "speaker": "app", "text": " 請說明主要工作。\r\n"}
VALID_PAYLOADS = [
    ("memory-map-arguments", {}),
    ("read-memory-object-arguments", {"target_title": TARGET["target_title"]}),
    ("read-interview-arguments", {"query": {"kind": "messages", "sequences": [1]}}),
    ("read-interview-arguments", {"query": {"kind": "messages", "sequences": [7, 1, 7]}}),
    (
        "read-interview-arguments",
        {"query": {"kind": "range", "start_sequence": 2, "end_sequence": 7}},
    ),
    ("memory-map", {"items": []}),
    ("memory-map", {"items": [TARGET]}),
    ("work-situation-view", {**CONTENT, "interview_references": []}),
    ("work-situation-view", {**CONTENT, "interview_references": [1, 2, 7]}),
    ("work-understanding-view", {**CONTENT, "work_situation_references": []}),
    ("work-understanding-view", {**CONTENT, "work_situation_references": [TARGET]}),
    (
        "historical-interview",
        {
            "data_kind": "historical_interview",
            "messages": [
                MESSAGE,
                {"interview_sequence": 2, "speaker": "employee", "text": " 每月一次。\n"},
                {"interview_sequence": 3, "speaker": "consultant", "text": "遇到差異如何處理？"},
            ],
        },
    ),
]


def load_contract(name: str) -> tuple[Draft202012Validator, type[BaseModel]]:
    schema_path = SCHEMAS / f"{name}.schema.json"
    assert schema_path.is_file(), f"Missing model-visible read contract: {name}"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    map_schema = json.loads((SCHEMAS / "memory-map.schema.json").read_text(encoding="utf-8"))
    registry = Registry().with_resource(
        "memory-map.schema.json", Resource.from_contents(map_schema)
    )
    module = import_module(f"caliburn.contracts.generated.tools.{name.replace('-', '_')}")
    return Draft202012Validator(schema, registry=registry), getattr(module, schema["title"])


@pytest.mark.parametrize(("name", "payload"), VALID_PAYLOADS)
def test_read_contract_preserves_complete_content_and_empty_collections(
    name: str, payload: dict[str, object]
) -> None:
    validator, model = load_contract(name)
    validator.validate(payload)
    assert model.model_validate(payload).model_dump(mode="json") == payload
    assert model.model_validate_json(json.dumps(payload)).model_dump(mode="json") == payload
    invalid = {**payload, "unexpected_field": "not allowed"}
    assert not validator.is_valid(invalid)
    with pytest.raises(ValidationError):
        model.model_validate(invalid)


@pytest.mark.parametrize(
    ("name", "payload"),
    [
        ("memory-map-arguments", []),
        ("read-memory-object-arguments", {}),
        ("read-memory-object-arguments", {"target_title": 12}),
        ("read-interview-arguments", {}),
        ("read-interview-arguments", {"query": {"sequences": [1]}}),
        ("read-interview-arguments", {"query": {"kind": "messages", "sequences": []}}),
        ("read-interview-arguments", {"query": {"kind": "range", "start_sequence": 1}}),
        ("read-interview-arguments", {"query": {"kind": "search", "sequences": [1]}}),
        (
            "read-interview-arguments",
            {
                "query": {
                    "kind": "messages",
                    "sequences": [1],
                    "start_sequence": 1,
                    "end_sequence": 2,
                }
            },
        ),
        (
            "read-interview-arguments",
            {"query": {"kind": "range", "start_sequence": 1, "end_sequence": 2, "sequences": [1]}},
        ),
        ("memory-map", {}),
        ("memory-map", {"items": [{"target_title": "盤點"}]}),
        ("memory-map", {"items": [{**TARGET, "can_read": True}]}),
        ("work-situation-view", CONTENT),
        ("work-situation-view", {**CONTENT, "interview_references": None}),
        ("work-understanding-view", CONTENT),
        ("work-understanding-view", {**CONTENT, "work_situation_references": None}),
        (
            "work-understanding-view",
            {**CONTENT, "work_situation_references": [{**TARGET, "source_id": "internal"}]},
        ),
        ("historical-interview", {"messages": [MESSAGE]}),
        ("historical-interview", {"data_kind": "current_input", "messages": [MESSAGE]}),
        ("historical-interview", {"data_kind": "historical_interview", "messages": []}),
        (
            "historical-interview",
            {"data_kind": "historical_interview", "messages": [{**MESSAGE, "speaker": "system"}]},
        ),
        (
            "historical-interview",
            {
                "data_kind": "historical_interview",
                "messages": [{**MESSAGE, "source_id": "internal"}],
            },
        ),
    ],
)
def test_read_contract_rejects_missing_fields_mixed_queries_and_internal_metadata(
    name: str, payload: object
) -> None:
    validator, model = load_contract(name)
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        model.model_validate(payload)


@pytest.mark.parametrize("sequence", [0, -1, 1.5, "1", True, None])
def test_sequences_are_positive_integers_without_coercion(sequence: object) -> None:
    payloads = [
        ("read-interview-arguments", {"query": {"kind": "messages", "sequences": [sequence]}}),
        (
            "read-interview-arguments",
            {"query": {"kind": "range", "start_sequence": sequence, "end_sequence": 7}},
        ),
        (
            "read-interview-arguments",
            {"query": {"kind": "range", "start_sequence": 1, "end_sequence": sequence}},
        ),
        ("work-situation-view", {**CONTENT, "interview_references": [sequence]}),
        (
            "historical-interview",
            {
                "data_kind": "historical_interview",
                "messages": [{**MESSAGE, "interview_sequence": sequence}],
            },
        ),
    ]
    for name, payload in payloads:
        validator, model = load_contract(name)
        assert not validator.is_valid(payload)
        with pytest.raises(ValidationError):
            model.model_validate(payload)


@pytest.mark.parametrize(
    "field",
    ["scope", "job_file_id", "memory_snapshot_id", "revision_id", "source_id", "cursor", "stage"],
)
def test_model_cannot_supply_app_bound_scope(field: str) -> None:
    for name, payload in VALID_PAYLOADS[:5]:
        validator, model = load_contract(name)
        invalid = {**payload, field: "app-owned"}
        assert not validator.is_valid(invalid)
        with pytest.raises(ValidationError):
            model.model_validate(invalid)
    validator, model = load_contract("read-interview-arguments")
    invalid_query = {"query": {"kind": "messages", "sequences": [1], field: "app-owned"}}
    assert not validator.is_valid(invalid_query)
    with pytest.raises(ValidationError):
        model.model_validate(invalid_query)


def test_range_order_is_left_to_domain_validation() -> None:
    validator, model = load_contract("read-interview-arguments")
    payload = {"query": {"kind": "range", "start_sequence": 7, "end_sequence": 2}}
    validator.validate(payload)
    assert model.model_validate(payload).model_dump(mode="json") == payload


@pytest.mark.parametrize("name", sorted({name for name, _ in VALID_PAYLOADS}))
def test_tool_wire_objects_are_closed_and_required(name: str) -> None:
    validator, _ = load_contract(name)
    schema = validator.schema
    assert schema["type"] == "object"
    assert "anyOf" not in schema and "oneOf" not in schema
    objects = [schema, *schema.get("$defs", {}).values()]
    for node in objects:
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
    if name == "read-interview-arguments":
        assert len(schema["properties"]["query"]["anyOf"]) == 2


@pytest.mark.parametrize("name", sorted({name for name, _ in VALID_PAYLOADS}))
def test_packaged_tool_schema_matches_source_bytes(name: str) -> None:
    filename = f"{name}.schema.json"
    resource = files("caliburn.contracts.generated.tools").joinpath(filename)
    assert resource.is_file(), f"Missing packaged tool schema: {filename}"
    assert resource.read_bytes() == (SCHEMAS / filename).read_bytes()
