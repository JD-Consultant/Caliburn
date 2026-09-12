"""Catalog wire data stays bounded, typed and independent of JD write receipts."""

from copy import deepcopy
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from jd_relational.generated import catalog_http


CONTRACTS = Path(__file__).resolve().parents[1] / "contracts"
SCHEMA = json.loads((CONTRACTS / "jd-catalog-http.schema.json").read_text(encoding="utf-8"))
DOCUMENT = "12345678-90ab-cdef-1234-567890abcdef"
REQUEST = "22345678-90ab-cdef-1234-567890abcdef"
DATASET = "32345678-90ab-cdef-1234-567890abcdef"
STAMP = "2026-09-13T10:21:09.123456+08:00"
MAX_SAFE_INTEGER = 9007199254740991


def document():
    return {"document_id": DOCUMENT, "title": "員工的實際工作\n任務與範圍",
            "archived": False, "metadata_version": 1, "created_at": STAMP, "updated_at": STAMP}


def page():
    return {"dataset_id": DATASET, "documents": [document()], "next_after": None}


def create():
    return {"request_key": REQUEST, "dataset_id": DATASET, "title": "新的客製化職務說明書"}


def creation_result():
    return {"request_key": REQUEST, "dataset_id": DATASET, "document_id": DOCUMENT}


def creation_lookup():
    return {"state": "found", "request_key": REQUEST, "dataset_id": DATASET, "document_id": DOCUMENT}


def problem():
    return {"type": "about:blank", "title": "Precondition Required", "status": 428,
            "detail": "請先讀取文件資料。", "instance": f"urn:uuid:{REQUEST}",
            "code": "precondition_required", "next_action": "reread"}


FACTORIES = {
    "CatalogDocument": document, "CatalogPage": page, "CatalogCreateInput": create,
    "CatalogRenameInput": lambda: {"title": "更正文件名稱"},
    "CatalogArchiveInput": lambda: {"archived": True},
    "CatalogMetadataInput": lambda: {"title": "更正文件名稱"},
    "CatalogCreationResult": creation_result, "CatalogCreationLookup": creation_lookup,
    "CatalogProblem": problem,
}


def accepts(name, payload, expected):
    source = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})
    model = getattr(catalog_http, name)
    published = Draft202012Validator(model.model_json_schema(mode="validation"))
    assert source.is_valid(payload) is expected
    assert published.is_valid(payload) is expected
    try:
        parsed = model.model_validate(payload, strict=True)
    except ValidationError:
        assert expected is False
    else:
        assert expected is True
        assert parsed.model_dump(mode="json") == payload


def test_catalog_exports_only_named_endpoint_payloads():
    Draft202012Validator.check_schema(SCHEMA)
    assert SCHEMA["properties"] == {name: {"$ref": f"#/$defs/{name}"} for name in FACTORIES}
    assert SCHEMA["required"] == list(FACTORIES)
    assert SCHEMA["additionalProperties"] is False


@pytest.mark.parametrize("name", FACTORIES)
def test_all_payloads_round_trip_with_all_required_fields(name):
    payload = FACTORIES[name]()
    accepts(name, payload, True)
    for key in payload:
        changed = deepcopy(payload)
        del changed[key]
        accepts(name, changed, False)
    for key in ("etag", "operation_id", "metadata", "unexpected"):
        accepts(name, {**payload, key: "not an endpoint field"}, False)


@pytest.mark.parametrize("title", ["", " ", "\n\t", "\u3000\u00a0", "\x00",
                                  "姓名\x00", "\x00\n任務", "\x1c", "\x1d", "\x1e", "\x1f",
                                  None, True, 12, []])
def test_titles_reject_missing_content_nul_and_non_strings(title):
    for name in ("CatalogDocument", "CatalogCreateInput", "CatalogRenameInput"):
        accepts(name, {**FACTORIES[name](), "title": title}, False)


@pytest.mark.parametrize("title", ["暫定名稱", "  我的工作  ", "\n待整理任務\n", "😀",
                                  pytest.param("工" * 22000, id="long-title")])
def test_title_content_is_preserved_without_trim_or_a_hidden_character_limit(title):
    # Byte/body limits are checked by the App and storage, not duplicated as an
    # unrelated title character-count restriction in the wire schema.
    for name in ("CatalogDocument", "CatalogCreateInput", "CatalogRenameInput"):
        accepts(name, {**FACTORIES[name](), "title": title}, True)


@pytest.mark.parametrize("wrong", [DOCUMENT.upper(), DOCUMENT.replace("-", ""),
                                  "{" + DOCUMENT + "}", DOCUMENT + "\n", "", None, 1])
def test_document_and_creation_identity_are_canonical_strings(wrong):
    for name, key in (("CatalogDocument", "document_id"), ("CatalogCreateInput", "request_key"),
                      ("CatalogCreationResult", "request_key"), ("CatalogCreationResult", "document_id"),
                      ("CatalogCreationLookup", "request_key"), ("CatalogCreationLookup", "document_id")):
        accepts(name, {**FACTORIES[name](), key: wrong}, False)
    accepts("CatalogPage", {**page(), "next_after": wrong}, wrong is None)


@pytest.mark.parametrize("wrong", [0, 1, 0.0, 1.0, "true", "false", None])
def test_archive_input_and_output_are_strict_booleans(wrong):
    accepts("CatalogArchiveInput", {"archived": wrong}, False)
    accepts("CatalogMetadataInput", {"archived": wrong}, False)
    accepts("CatalogDocument", {**document(), "archived": wrong}, False)


@pytest.mark.parametrize("version", [1, MAX_SAFE_INTEGER, 0, -1, MAX_SAFE_INTEGER + 1,
                                    True, False, "1", None])
def test_metadata_version_is_a_positive_safe_integer(version):
    accepts("CatalogDocument", {**document(), "metadata_version": version},
            type(version) is int and 1 <= version <= MAX_SAFE_INTEGER)


def test_json_schema_integer_value_does_not_relax_the_python_projection_type():
    # JSON Schema's integer is a mathematical value (including JSON 1.0).
    # The App's native database version must still be a strict Python integer.
    payload = {**document(), "metadata_version": 1.0}
    source = Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": "#/$defs/CatalogDocument"})
    assert source.is_valid(payload)
    assert Draft202012Validator(catalog_http.CatalogDocument.model_json_schema()).is_valid(payload)
    with pytest.raises(ValidationError):
        catalog_http.CatalogDocument.model_validate(payload, strict=True)


@pytest.mark.parametrize("stamp", ["2026-09-13T10:21:09Z", STAMP, "2026-09-13t10:21:09z",
                                  "2026-09-13T10:21:09-05:30"])
def test_native_database_timestamps_keep_their_rfc3339_wire_string(stamp):
    accepts("CatalogDocument", {**document(), "created_at": stamp, "updated_at": stamp}, True)


@pytest.mark.parametrize("stamp", ["2026-09-13", "2026-09-13T10:21:09", "not a timestamp",
                                  "2026-13-13T10:21:09Z", "2026-09-13T24:21:09Z",
                                  "2026-09-13T10:61:09Z", "2026-09-13T10:21:61Z", None, 1])
def test_incomplete_or_malformed_timestamp_strings_are_rejected(stamp):
    accepts("CatalogDocument", {**document(), "created_at": stamp}, False)


def test_page_is_bounded_and_nullable_cursor_does_not_allow_omission():
    accepts("CatalogPage", {"dataset_id": DATASET, "documents": [], "next_after": None}, True)
    accepts("CatalogPage", {"dataset_id": DATASET, "documents": [document()] * 100, "next_after": DOCUMENT}, True)
    accepts("CatalogPage", {"dataset_id": DATASET, "documents": [document()] * 101, "next_after": DOCUMENT}, False)
    accepts("CatalogPage", {"dataset_id": DATASET, "documents": None, "next_after": None}, False)
    bad = document()
    bad["archived"] = 0
    accepts("CatalogPage", {"dataset_id": DATASET, "documents": [bad], "next_after": None}, False)


@pytest.mark.parametrize("state,document_id,expected", [
    ("found", DOCUMENT, True), ("found", None, False),
    ("not_found", None, True), ("not_found", DOCUMENT, False),
    ("pending", None, False), ("failed", None, False), (None, None, False),
])
def test_creation_lookup_does_not_invent_a_document_or_execution_state(state, document_id, expected):
    accepts("CatalogCreationLookup", {"state": state, "request_key": REQUEST,
                                      "dataset_id": DATASET, "document_id": document_id}, expected)


@pytest.mark.parametrize("status", [403, 404, 409, 412, 415, 422, 428, 500, 503, 200, 202, "428", True])
def test_problem_status_is_distinct_from_success_or_a_write_receipt(status):
    accepts("CatalogProblem", {**problem(), "status": status},
            type(status) is int and status in (403, 404, 409, 412, 415, 422, 428, 500, 503))


def test_catalog_errors_cannot_advertise_rollback_or_automatic_retry():
    for key in ("jd_result", "result", "rolled_back", "receipt_durability"):
        accepts("CatalogProblem", {**problem(), key: "not proven"}, False)
    for key, value in (("code", "archived"), ("next_action", "retry"),
                       ("type", "https://invented.invalid/problem"), ("instance", REQUEST)):
        accepts("CatalogProblem", {**problem(), key: value}, False)


@pytest.mark.parametrize("value,expected", [
    ({"title": "修正名稱"}, True), ({"archived": True}, True), ({"archived": False}, True),
    ({"title": "修正名稱", "archived": True}, False), ({"title": None}, False),
    ({"archived": None}, False), ({}, False), ({"metadata_version": 2}, False),
])
def test_conditional_metadata_patch_is_exactly_one_named_non_null_change(value, expected):
    accepts("CatalogMetadataInput", value, expected)


@pytest.mark.parametrize("wrong", [DATASET.upper(), DATASET + "\n", "", None, 1])
def test_dataset_identity_is_required_and_canonical_for_creation_and_listing(wrong):
    for name in ("CatalogPage", "CatalogCreateInput", "CatalogCreationResult", "CatalogCreationLookup"):
        accepts(name, {**FACTORIES[name](), "dataset_id": wrong}, False)


def test_creation_lookup_reuses_the_complete_original_creation_intent():
    payload = create()
    for key in ("title", "dataset_id", "request_key"):
        missing = {name: value for name, value in payload.items() if name != key}
        accepts("CatalogCreateInput", missing, False)


def test_unsupported_patch_media_type_has_an_explicit_problem():
    accepts("CatalogProblem", {**problem(), "status": 415, "title": "Unsupported Media Type",
                               "code": "unsupported_patch", "next_action": "correct_input"}, True)
