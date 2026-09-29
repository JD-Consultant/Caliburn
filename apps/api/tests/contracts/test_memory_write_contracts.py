"""Write wire/DTO boundaries; semantic validation and persistence belong to their owners."""

import json
from importlib import import_module
from importlib.resources import files
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError

SCHEMAS = Path(__file__).parents[2] / "contracts/tools"
CONTENT = {
    "title": " 月末庫存盤點 ",
    "description": "核對帳實差異，異常交主管確認。",
    "body": "## 處理頻率\r\n每週一次。\r\n",
}
DIFF = "@@\n ## 處理頻率\n-每週一次。\n+每月一次。"
LAYERS = [
    ("work-situation", "interview_references", [12, 28], [6]),
    ("work-understanding", "work_situation_references", [" 月末庫存盤點 "], ["例行盤點"]),
]
ARGUMENT_NAMES = [
    "create-work-situation-arguments",
    "create-work-understanding-arguments",
    "delete-memory-object-arguments",
    "update-work-situation-arguments",
    "update-work-understanding-arguments",
]


def load_contract(name: str) -> tuple[Draft202012Validator, type[BaseModel]]:
    path = SCHEMAS / f"{name}.schema.json"
    assert path.is_file(), f"Missing model-visible write contract: {name}"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    module = import_module(f"caliburn.contracts.generated.tools.{name.replace('-', '_')}")
    return Draft202012Validator(schema), getattr(module, schema["title"])


def assert_round_trip(name: str, payload: dict[str, object]) -> None:
    validator, model = load_contract(name)
    validator.validate(payload)
    assert model.model_validate(payload).model_dump(mode="json") == payload
    assert model.model_validate_json(json.dumps(payload)).model_dump(mode="json") == payload


def assert_rejected(name: str, payload: object) -> None:
    validator, model = load_contract(name)
    assert not validator.is_valid(payload)
    with pytest.raises(ValidationError):
        model.model_validate(payload)
    with pytest.raises(ValidationError):
        model.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize(("layer", "references", "added", "removed"), LAYERS)
def test_create_requires_full_content_but_allows_empty_sources(
    layer: str, references: str, added: list[object], removed: list[object]
) -> None:
    name = f"create-{layer}-arguments"
    for sources in ([], added):
        payload = {**CONTENT, references: sources}
        assert_round_trip(name, payload)
        for field in payload:
            assert_rejected(name, {key: value for key, value in payload.items() if key != field})
            assert_rejected(name, {**payload, field: None})
    for field in CONTENT:
        for value in (12, True, ""):
            assert_rejected(name, {**CONTENT, references: [], field: value})
    assert_rejected(name, {**CONTENT, references: [], "changes": []})


@pytest.mark.parametrize(("layer", "references", "added", "removed"), LAYERS)
def test_update_selects_only_requested_fields_and_reference_sides(
    layer: str, references: str, added: list[object], removed: list[object]
) -> None:
    name = f"update-{layer}-arguments"
    text_changes = [
        {"field": "title", "value": "月末盤點"},
        {"field": "description", "value": "核對實際差異。"},
        {"field": "body", "diff": DIFF},
    ]
    reference_changes = [
        {"field": references, "add": added},
        {"field": references, "remove": removed},
        {"field": references, "add": added, "remove": removed},
    ]
    for change in [*text_changes, *reference_changes]:
        assert_round_trip(name, {"target_title": CONTENT["title"], "changes": [change]})
    for change in reference_changes:
        assert_round_trip(
            name, {"target_title": CONTENT["title"], "changes": [*text_changes, change]}
        )


@pytest.mark.parametrize(("layer", "references", "added", "removed"), LAYERS)
def test_update_rejects_missing_empty_null_and_mixed_mutations(
    layer: str, references: str, added: list[object], removed: list[object]
) -> None:
    name = f"update-{layer}-arguments"
    valid_change = {"field": "title", "value": "月末盤點"}
    invalid_changes = [
        {},
        {"field": "title"},
        {"field": "title", "value": None},
        {"field": "title", "value": 12},
        {"field": "title", "value": ""},
        {"field": "description", "value": True},
        {"field": "description", "value": None},
        {"field": "body", "diff": None},
        {"field": "body", "diff": 12},
        {"field": "body", "diff": ""},
        {"field": "body", "value": DIFF},
        {"field": "body", "diff": DIFF, "value": "replacement"},
        {"field": "title", "value": "月末盤點", "diff": DIFF},
        {"field": "sources", "add": added},
        {"field": "unknown", "value": "content"},
        {"field": references},
        {"field": references, "add": []},
        {"field": references, "remove": []},
        {"field": references, "add": None},
        {"field": references, "remove": None},
        {"field": references, "add": added, "remove": []},
        {"field": references, "add": [], "remove": removed},
        {"field": references, "add": added, "remove": None},
        {"field": references, "add": None, "remove": removed},
        {"field": references, "add": added, "value": "replacement"},
    ]
    for change in invalid_changes:
        assert_rejected(name, {"target_title": CONTENT["title"], "changes": [change]})
    for changes in ([], None, {}, [valid_change] * 5):
        assert_rejected(name, {"target_title": CONTENT["title"], "changes": changes})
    assert_rejected(name, {"target_title": CONTENT["title"]})
    assert_rejected(name, {"changes": [valid_change]})
    for title in (None, 12, True, ""):
        assert_rejected(name, {"target_title": title, "changes": [valid_change]})


def test_write_arguments_keep_layer_reference_branches_separate() -> None:
    for layer, references, added, _ in LAYERS:
        for other_layer, other_references, other_added, _ in LAYERS:
            if layer == other_layer:
                continue
            assert_rejected(f"create-{layer}-arguments", {**CONTENT, other_references: other_added})
            assert_rejected(
                f"create-{layer}-arguments",
                {**CONTENT, references: added, other_references: other_added},
            )
            assert_rejected(
                f"update-{layer}-arguments",
                {
                    "target_title": CONTENT["title"],
                    "changes": [
                        {"field": references, "add": added},
                        {"field": other_references, "remove": other_added},
                    ],
                },
            )


@pytest.mark.parametrize(
    ("layer", "references", "source"),
    [
        ("work-situation", "interview_references", source)
        for source in (0, -1, 1.5, "12", True, None, {"interview_sequence": 12})
    ]
    + [
        ("work-understanding", "work_situation_references", source)
        for source in (12, True, None, "", {"target_title": "盤點"})
    ],
)
def test_reference_selection_rejects_wrong_types_without_coercion(
    layer: str, references: str, source: object
) -> None:
    assert_rejected(f"create-{layer}-arguments", {**CONTENT, references: [source]})
    for side in ("add", "remove"):
        assert_rejected(
            f"update-{layer}-arguments",
            {"target_title": CONTENT["title"], "changes": [{"field": references, side: [source]}]},
        )
    for side in ("added", "removed"):
        assert_rejected(
            "memory-write-result",
            {
                "status": "updated",
                "title": CONTENT["title"],
                "description": CONTENT["description"],
                "applied_changes": [{"field": references, side: [source]}],
            },
        )


def test_delete_selects_exact_title_without_cascade_or_read_claims() -> None:
    name = "delete-memory-object-arguments"
    assert_round_trip(name, {"target_title": CONTENT["title"]})
    for payload in ({}, [], {"title": "盤點"}, {"target_title": "盤點", "cascade": True}):
        assert_rejected(name, payload)
    for title in (None, 12, True, ""):
        assert_rejected(name, {"target_title": title})


@pytest.mark.parametrize(
    "field",
    [
        "scope",
        "layer",
        "job_file_id",
        "memory_snapshot_id",
        "revision_id",
        "source_id",
        "batch_id",
        "operation_id",
        "candidate_position_id",
        "stage",
        "version",
        "unexpected",
    ],
)
def test_model_cannot_supply_execution_scope_or_other_undeclared_fields(field: str) -> None:
    for layer, references, added, _ in LAYERS:
        assert_rejected(f"create-{layer}-arguments", {**CONTENT, references: [], field: "internal"})
        update = {"target_title": CONTENT["title"], "changes": [{"field": "body", "diff": DIFF}]}
        assert_rejected(f"update-{layer}-arguments", {**update, field: "internal"})
        for change in (
            {"field": "title", "value": "盤點"},
            {"field": "body", "diff": DIFF},
            {"field": references, "add": added},
        ):
            assert_rejected(
                f"update-{layer}-arguments", {**update, "changes": [{**change, field: "internal"}]}
            )
    assert_rejected("delete-memory-object-arguments", {"target_title": "盤點", field: "internal"})


@pytest.mark.parametrize(("layer", "references", "added", "removed"), LAYERS)
def test_semantic_checks_and_identity_deduplication_are_left_to_runtime_and_domain(
    layer: str, references: str, added: list[object], removed: list[object]
) -> None:
    # Shape acceptance is not authorization, valid content, or an applied update.
    assert_round_trip(f"create-{layer}-arguments", {**CONTENT, references: [*added, *added]})
    assert_round_trip(f"create-{layer}-arguments", {**CONTENT, "title": " \t", references: []})
    for changes in (
        [{"field": "title", "value": "one"}, {"field": "title", "value": "two"}],
        [{"field": "description", "value": " \t"}],
        [{"field": "body", "diff": "not a V4A hunk"}],
        [{"field": references, "add": [*added, *added]}],
        [{"field": references, "add": added, "remove": added}],
    ):
        assert_round_trip(
            f"update-{layer}-arguments", {"target_title": CONTENT["title"], "changes": changes}
        )


@pytest.mark.parametrize("status", ["created", "deleted", "unchanged"])
def test_status_only_results_do_not_echo_arguments_or_expose_scope(status: str) -> None:
    assert_round_trip("memory-write-result", {"status": status})
    for field, value in {**CONTENT, "stage": "candidate", "applied_changes": []}.items():
        assert_rejected("memory-write-result", {"status": status, field: value})


@pytest.mark.parametrize(
    "change",
    [{"field": "title"}, {"field": "description"}, {"field": "body", "diff": DIFF}],
)
def test_updated_result_needs_no_unmodified_body_or_sources(change: dict[str, object]) -> None:
    payload = {
        "status": "updated",
        "title": CONTENT["title"],
        "description": CONTENT["description"],
        "applied_changes": [change],
    }
    assert_round_trip("memory-write-result", payload)
    assert_rejected("memory-write-result", {**payload, "body": CONTENT["body"]})
    assert_rejected(
        "memory-write-result", {**payload, "applied_changes": [{**change, "source_id": "internal"}]}
    )


@pytest.mark.parametrize(("layer", "references", "added", "removed"), LAYERS)
def test_updated_result_reports_actual_changes_with_only_changed_reference_sides(
    layer: str, references: str, added: list[object], removed: list[object]
) -> None:
    result = {"status": "updated", "title": "月末盤點", "description": CONTENT["description"]}
    for reference_change in (
        {"field": references, "added": added},
        {"field": references, "removed": removed},
        {"field": references, "added": added, "removed": removed},
    ):
        assert_round_trip("memory-write-result", {**result, "applied_changes": [reference_change]})
        assert_round_trip(
            "memory-write-result",
            {
                **result,
                "applied_changes": [
                    {"field": "title"},
                    {"field": "description"},
                    {"field": "body", "diff": DIFF},
                    reference_change,
                ],
            },
        )
    invalid_changes = [
        {"field": "title", "value": "月末盤點"},
        {"field": "body"},
        {"field": "body", "diff": None},
        {"field": "body", "diff": 12},
        {"field": references},
        {"field": references, "add": added},
        {"field": references, "added": []},
        {"field": references, "removed": []},
        {"field": references, "added": added, "removed": None},
        {"field": references, "added": None, "removed": removed},
        {"field": references, "added": added, "removed": []},
        {"field": references, "added": [], "removed": removed},
    ]
    for change in invalid_changes:
        assert_rejected("memory-write-result", {**result, "applied_changes": [change]})
    for changes in ([], None):
        assert_rejected("memory-write-result", {**result, "applied_changes": changes})
    valid = {**result, "applied_changes": [{"field": "title"}]}
    for field in valid:
        assert_rejected(
            "memory-write-result", {key: value for key, value in valid.items() if key != field}
        )
        assert_rejected("memory-write-result", {**valid, field: None})
    for field in ("title", "description"):
        assert_rejected("memory-write-result", {**valid, field: 12})
    assert_rejected("memory-write-result", {**valid, "stage": "candidate"})


def test_result_cannot_mix_layer_effects_or_claim_unknown_outcome_as_success() -> None:
    assert_rejected(
        "memory-write-result",
        {
            "status": "updated",
            "title": "盤點",
            "description": CONTENT["description"],
            "applied_changes": [
                {"field": "interview_references", "added": [12]},
                {"field": "work_situation_references", "added": ["盤點"]},
            ],
        },
    )
    for status in ("unknown", "published", "rejected", None, 1):
        assert_rejected("memory-write-result", {"status": status})


@pytest.mark.parametrize("name", ARGUMENT_NAMES)
def test_argument_wire_uses_required_closed_objects_and_nested_anyof(name: str) -> None:
    validator, _ = load_contract(name)
    schema = validator.schema
    assert schema["type"] == "object"
    assert "anyOf" not in schema

    def check_node(node: object) -> None:
        if isinstance(node, list):
            for item in node:
                check_node(item)
        elif isinstance(node, dict):
            assert "oneOf" not in node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            if "$ref" in node:
                assert node["$ref"].startswith("#/$defs/")
            for value in node.values():
                check_node(value)

    check_node(schema)
    if name.startswith("update-"):
        changes = schema["properties"]["changes"]
        assert changes["minItems"] == 1 and changes["maxItems"] == 4
        assert len(changes["items"]["anyOf"]) == 5


@pytest.mark.parametrize("name", [*ARGUMENT_NAMES, "memory-write-result"])
def test_packaged_write_wire_matches_authoritative_schema(name: str) -> None:
    filename = f"{name}.schema.json"
    resource = files("caliburn.contracts.generated.tools").joinpath(filename)
    assert resource.is_file(), f"Missing packaged write schema: {filename}"
    assert resource.read_bytes() == (SCHEMAS / filename).read_bytes()
