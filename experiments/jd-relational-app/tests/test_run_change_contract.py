"""Public captured-run changes reuse the authoritative historical records."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
from referencing import Registry, Resource
import pytest

from jd_relational.generated import chat_http


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
SCHEMA = json.loads((CONTRACTS / "jd-chat-http.schema.json").read_text(encoding="utf-8"))
REGISTRY = Registry().with_resources((path.name, Resource.from_contents(json.loads(path.read_text(encoding="utf-8"))))
                                     for path in CONTRACTS.glob("*.schema.json"))
NAME = "ChatRunChangePage"
DATASET = "12345678-90ab-cdef-1234-567890abcdef"
DOCUMENT = "22345678-90ab-cdef-1234-567890abcdef"
RUN = "32345678-90ab-cdef-1234-567890abcdef"


def page(continuity="continuous", **overrides):
    return dict(format_version=1, view="run_change", access="history", dataset_id=DATASET,
        document_id=DOCUMENT, run_id=RUN, capture_ref="signed-captured-ids-offset-zero",
        effects_state="settled", continuity=continuity,
        captured_operation_count=0 if continuity == "none" else 2,
        base_revision_ref="S" if continuity == "continuous" else None,
        result_revision_ref="E" if continuity == "continuous" else None,
        records=[], start_index=0, total_records=0, total_changes=0,
        has_more=False, next_cursor=None, oversized_unit=False) | overrides


def oracle():
    assert NAME in SCHEMA["$defs"]
    return Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{NAME}"}, registry=REGISTRY)


def structural_accepts(payload, expected):
    assert oracle().is_valid(payload) is expected
    model = getattr(chat_http, NAME)
    assert Draft202012Validator(model.model_json_schema(mode="validation")).is_valid(payload) is expected
    try:
        result = model.model_validate(payload, strict=True).model_dump(mode="json")
    except ValidationError:
        assert not expected
    else:
        assert expected and result == payload


def test_named_generated_root_is_closed_and_reuses_external_read_records():
    assert SCHEMA["properties"].get(NAME) == {"$ref": f"#/$defs/{NAME}"}
    assert NAME in SCHEMA["required"]
    definition = SCHEMA["$defs"][NAME]
    assert definition["additionalProperties"] is False
    assert set(definition["required"]) == set(definition["properties"]) == set(page())
    assert definition["properties"]["records"]["items"] == {"$ref": "jd-read.schema.json#/$defs/ChangeReadRecord"}
    Draft202012Validator.check_schema(SCHEMA)


@pytest.mark.parametrize("continuity", ["none", "continuous", "discontinuous"])
@pytest.mark.parametrize("state", ["settled", "unconfirmed"])
def test_valid_states_include_no_net_change_and_active_captured_ranges(continuity, state):
    structural_accepts(page(continuity, effects_state=state), True)


@pytest.mark.parametrize("field", list(page()))
def test_every_published_field_is_required(field):
    payload = page()
    del payload[field]
    structural_accepts(payload, False)


@pytest.mark.parametrize("field,value", [
    ("format_version", 2), ("format_version", True), ("view", "change"), ("access", "current"),
    ("dataset_id", "other"), ("document_id", DOCUMENT.upper()), ("run_id", RUN + "\n"),
    ("capture_ref", ""), ("capture_ref", "x" * 4097), ("effects_state", "confirmed"),
    ("continuity", "complete"), ("captured_operation_count", True), ("captured_operation_count", 97),
    ("captured_operation_count", -1), ("start_index", -1), ("total_records", True),
    ("total_changes", -1), ("has_more", 1), ("oversized_unit", 0), ("next_cursor", ""),
])
def test_invalid_scalar_shapes_do_not_coerce(field, value):
    structural_accepts(page(**{field: value}), False)


def test_unknown_fields_and_fake_operation_identity_are_not_published():
    for name in ("operation_ref", "change_ref", "snapshot", "writer", "commands", "accepted"):
        structural_accepts(page(**{name: "unexpected"}), False)


@pytest.mark.parametrize("overrides", [
    {"continuity": "none"}, {"captured_operation_count": 0},
    {"base_revision_ref": None}, {"result_revision_ref": None},
])
def test_authoritative_schema_rejects_invalid_continuous_combinations(overrides):
    assert not oracle().is_valid(page() | overrides)


@pytest.mark.parametrize("continuity", ["none", "discontinuous"])
@pytest.mark.parametrize("overrides", [
    {"base_revision_ref": "fake-S"}, {"result_revision_ref": "fake-E"},
    {"total_records": 1}, {"total_changes": 1},
    {"records": [{"type": "change", "change_index": 0, "kind": "update", "entity_kind": "profile",
                  "before_exists": True, "after_exists": True, "changed_fields": ["purpose"]}]},
])
def test_noncontinuous_has_no_net_comparison(overrides, continuity):
    assert not oracle().is_valid(page(continuity, **overrides))


def test_empty_and_discontinuous_counts_cannot_be_swapped():
    assert not oracle().is_valid(page("none", captured_operation_count=1))
    assert not oracle().is_valid(page("discontinuous", captured_operation_count=0))


def test_generated_dto_does_not_replace_authoritative_conditional_validation():
    # The pinned standard generator preserves the flat data shape but does not
    # generate if/then validators. The service must also use the source schema,
    # as the Web Ajv decoder does; this is a limit, not successful validation.
    invalid = page(captured_operation_count=0)
    assert not oracle().is_valid(invalid)
    model = getattr(chat_http, NAME)
    assert model.model_validate(invalid, strict=True).model_dump(mode="json") == invalid
    assert Draft202012Validator(model.model_json_schema(mode="validation")).is_valid(invalid)


def test_full_multiline_field_and_history_only_record_reuse():
    header = dict(type="change", change_index=0, kind="update", entity_kind="profile",
                  before_exists=True, after_exists=True, changed_fields=["purpose"])
    field = dict(type="value", change_index=0, side="after", record=dict(type="field", item_ref=None,
        section_ref="history-section", field_ref="history-field", name="purpose", value="繁中\n完整原文😀"))
    payload = page(records=[header, field], total_records=2, total_changes=1)
    structural_accepts(payload, True)
    invalid = deepcopy(payload)
    invalid["records"][1]["record"]["invented_field"] = "not silently dropped"
    structural_accepts(invalid, False)
