"""Complete snapshot round trips and corruption rejection, without persistence."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator
from pydantic import ValidationError
import pytest

from jd_relational.domain import SOURCE_COLUMNS
from jd_relational.generated.snapshots import JdSnapshot
from jd_relational.snapshots import (
    SnapshotValidationError, domain_from_snapshot, empty_domain,
    snapshot_digest, snapshot_from_domain,
)


def uid(number):
    return str(UUID(int=number))


REVISION = uid(900)
SCHEMA = json.loads((Path(__file__).resolve().parents[1] / "contracts/jd-snapshot.schema.json").read_text(encoding="utf-8"))


def complete_domain():
    value = empty_domain("document-a", REVISION)
    value["profile"] = {"job_title": "維護工程師", "organization_unit": "設備組",
        "employee_name": None, "reports_to": "現場主管", "purpose": "維持可安全使用的設備狀態。"}
    value["collaborators"] = {uid(1): {"collaborator_id": uid(1), "name": "使用單位",
        "scope_text": "異常時交接停機範圍", "position": 0}}
    value["duties"] = {uid(2): {"duty_id": uid(2), "name": "設備維護", "scope_text": "僅限約定設備", "position": 0}}
    value["tasks"] = {
        uid(4): {"task_id": uid(4), "duty_id": None, "name": None,
            "description": "低頻但重要：保全故障現場；其他內容仍待釐清。", "position": 4},
        uid(3): {"task_id": uid(3), "duty_id": uid(2), "name": "功能檢查",
            "description": "  僅於已隔離設備執行😀\n保留原樣空白與 e\u0301  ", "position": 0},
    }
    value["details"] = {
        uid(5): {"detail_id": uid(5), "task_id": uid(3), "kind": "outcome", "text": "可回查的狀態紀錄", "position": 0},
        uid(6): {"detail_id": uid(6), "task_id": uid(3), "kind": "outcome", "text": "異常交接資料", "position": 3},
        uid(7): {"detail_id": uid(7), "task_id": uid(3), "kind": "requirement", "text": "先確認安全隔離", "position": 0},
        uid(8): {"detail_id": uid(8), "task_id": uid(3), "kind": "requirement", "text": "依清單作功能檢查", "position": 2},
    }
    value["capabilities"] = {
        uid(10): {"capability_id": uid(10), "kind": "skill", "name": "異常診斷", "description": "依觀察辨識問題", "position": 0},
        uid(9): {"capability_id": uid(9), "kind": "knowledge", "name": "異常診斷", "description": "了解設備狀態與限制", "position": 0},
    }
    value["task_capabilities"] = [{"task_id": uid(4), "capability_id": uid(10), "position": 0},
        {"task_id": uid(3), "capability_id": uid(10), "position": 1},
        {"task_id": uid(3), "capability_id": uid(9), "position": 0}]
    value["conditions"] = {uid(20 + i): {"condition_id": uid(20 + i), "kind": kind,
        "text": "已有依據的全職位條件", "position": 0} for i, kind in enumerate([
            "work_environment", "schedule_travel", "shared_authority", "shared_collaboration", "qualification"])}
    targets = [{"profile_field": "purpose"}, {"collaborator_id": uid(1)}, {"duty_id": uid(2)},
        {"task_id": uid(3)}, {"detail_id": uid(7)}, {"capability_id": uid(9)},
        {"condition_id": uid(20)}, {"linked_task_id": uid(3), "linked_capability_id": uid(9)}]
    value["source_links"] = [{"source_link_id": uid(30 + i), "source_ref": f"issued-source-{i}",
        "basis_digest": "a" * 64, "position": 0, **dict.fromkeys(SOURCE_COLUMNS), **target}
        for i, target in enumerate(targets)]
    return value


def schema_accepts(value, expected):
    source = Draft202012Validator(SCHEMA).is_valid(value)
    published = Draft202012Validator(JdSnapshot.model_json_schema(mode="validation")).is_valid(value)
    try:
        parsed = JdSnapshot.model_validate(value, strict=True).model_dump(mode="json")
        dto = True
        assert parsed == value
    except ValidationError:
        dto = False
    assert (source, published, dto) == (expected,) * 3


def test_complete_six_chapter_round_trip_preserves_every_value_and_relation():
    original = complete_domain()
    before = deepcopy(original)
    snapshot = snapshot_from_domain(original)
    schema_accepts(snapshot, True)
    assert set(snapshot) == {"format_version", "engine_profile", "document_id", "profile", "collaborators",
        "duties", "tasks", "task_details", "capabilities", "task_capabilities", "conditions", "source_links"}
    assert (snapshot["format_version"], snapshot["engine_profile"]) == (3, "jd-relational-v1")
    assert len(snapshot["task_details"]) == 4 and len(snapshot["source_links"]) == 8
    restored = domain_from_snapshot(snapshot, uid(901))
    assert restored["revision"] == uid(901)
    assert snapshot_from_domain(restored) == snapshot
    for collection in ("profile", "collaborators", "duties", "tasks", "details", "capabilities", "conditions"):
        assert restored[collection] == original[collection]
    for collection in ("task_capabilities", "source_links"):
        assert sorted(restored[collection], key=lambda row: json.dumps(row, sort_keys=True)) == sorted(
            original[collection], key=lambda row: json.dumps(row, sort_keys=True))
    assert original == before


def test_empty_document_is_valid_without_mandatory_employee_content():
    value = empty_domain("document-a", REVISION)
    assert set(value["profile"]) == {"job_title", "organization_unit", "employee_name", "reports_to", "purpose"}
    assert all(item is None for item in value["profile"].values())
    assert domain_from_snapshot(snapshot_from_domain(value), REVISION) == value


def test_scope_is_checked_before_redundant_row_scope_and_revision_are_removed():
    value = complete_domain()
    value["profile"]["document_id"] = value["document_id"]
    for collection in ("collaborators", "duties", "tasks", "details", "capabilities", "conditions"):
        for row in value[collection].values():
            row["document_id"] = value["document_id"]
    for collection in ("task_capabilities", "source_links"):
        for row in value[collection]:
            row["document_id"] = value["document_id"]
    assert snapshot_from_domain(value) == snapshot_from_domain(complete_domain())
    for collection, row in [("profile", value["profile"]), ("tasks", value["tasks"][uid(3)]),
                            ("source_links", value["source_links"][0])]:
        row["document_id"] = "other-document"
        with pytest.raises(SnapshotValidationError):
            snapshot_from_domain(value)
        row["document_id"] = value["document_id"]


def test_digest_is_exact_canonical_utf8_without_revision_or_array_insertion_order():
    snapshot = snapshot_from_domain(complete_domain())
    canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert snapshot_digest(snapshot) == hashlib.sha256(canonical).hexdigest()
    shuffled = deepcopy(snapshot)
    for name, rows in shuffled.items():
        if isinstance(rows, list):
            rows.reverse()
    assert snapshot_digest(shuffled) == snapshot_digest(snapshot)
    assert snapshot_digest(snapshot_from_domain(domain_from_snapshot(snapshot, uid(999)))) == snapshot_digest(snapshot)
    changed = deepcopy(snapshot)
    changed["tasks"][0]["description"] += " 新的條件"
    assert snapshot_digest(changed) != snapshot_digest(snapshot)
    changed = deepcopy(snapshot)
    changed["task_details"][0]["position"] += 1
    assert snapshot_digest(changed) != snapshot_digest(snapshot)


@pytest.mark.parametrize("patch", [
    {"format_version": 2}, {"format_version": "3"}, {"engine_profile": "plate"},
    {"revision": REVISION}, {"unknown": "must not disappear"}, {"document_id": ""},
])
def test_snapshot_shape_rejects_wrong_version_and_unknown_fields(patch):
    value = {**snapshot_from_domain(complete_domain()), **patch}
    schema_accepts(value, False)
    with pytest.raises(SnapshotValidationError):
        domain_from_snapshot(value, REVISION)


@pytest.mark.parametrize("key", ["format_version", "engine_profile", "document_id", "profile", "tasks", "source_links"])
def test_missing_snapshot_facts_are_not_defaulted(key):
    value = snapshot_from_domain(complete_domain())
    del value[key]
    schema_accepts(value, False)
    with pytest.raises(SnapshotValidationError):
        snapshot_digest(value)


@pytest.mark.parametrize("kind", ["unknown_root", "unknown_profile", "unknown_row", "missing_nullable", "key_identity", "bad_uuid", "foreign_scope"])
def test_domain_conversion_never_discards_malformed_input(kind):
    value = complete_domain()
    if kind == "unknown_root": value["extra"] = True
    elif kind == "unknown_profile": value["profile"]["extra"] = True
    elif kind == "unknown_row": value["tasks"][uid(3)]["extra"] = True
    elif kind == "missing_nullable": del value["source_links"][0]["task_id"]
    elif kind == "key_identity": value["tasks"][uid(3)]["task_id"] = uid(444)
    elif kind == "bad_uuid": value["source_links"][0]["source_link_id"] = "not-a-uuid"
    elif kind == "foreign_scope": value["task_capabilities"][0]["document_id"] = "other-document"
    before = deepcopy(value)
    with pytest.raises(SnapshotValidationError): snapshot_from_domain(value)
    assert value == before


@pytest.mark.parametrize("kind", ["duplicate_id", "duplicate_relation", "duplicate_source", "empty_task", "missing_owner", "two_source_targets", "half_relation_source", "blank_requirement", "crlf", "surrogate", "nul", "too_large"])
def test_snapshot_codec_uses_shared_content_and_relationship_rules(kind):
    value = snapshot_from_domain(complete_domain())
    if kind == "duplicate_id": value["tasks"].append({**value["tasks"][0], "description": "duplicate with different content"})
    elif kind == "duplicate_relation": value["task_capabilities"].append(deepcopy(value["task_capabilities"][0]))
    elif kind == "duplicate_source": value["source_links"].append({**value["source_links"][0], "source_link_id": uid(888)})
    elif kind == "empty_task": value["tasks"][0].update(name=None, description=None)
    elif kind == "missing_owner": value["task_details"][0]["task_id"] = uid(888)
    elif kind == "two_source_targets": value["source_links"][0]["task_id"] = uid(3)
    elif kind == "half_relation_source": value["source_links"][-1]["linked_task_id"] = None
    elif kind == "blank_requirement": value["task_details"][0]["text"] = " \t"
    elif kind == "crlf": value["tasks"][0]["description"] = "甲\r\n乙"
    elif kind == "surrogate": value["tasks"][0]["description"] = "broken\ud800"
    elif kind == "nul": value["tasks"][0]["description"] = "broken\x00"
    elif kind == "too_large": value["tasks"][0]["description"] = "甲" * 21846
    before = deepcopy(value)
    with pytest.raises(SnapshotValidationError): domain_from_snapshot(value, REVISION)
    with pytest.raises(SnapshotValidationError): snapshot_digest(value)
    assert value == before


@pytest.mark.parametrize("revision", ["r1", "", None, UUID(int=1), "00000000-0000-0000-0000-00000000000G"])
def test_revision_argument_is_a_uuid_string_without_becoming_snapshot_content(revision):
    with pytest.raises(SnapshotValidationError): empty_domain("document-a", revision)
    with pytest.raises(SnapshotValidationError): domain_from_snapshot(snapshot_from_domain(complete_domain()), revision)


@pytest.mark.parametrize("mutation", ["missing_field", "unknown_field", "scope_field", "bad_uuid", "coerced_position"])
def test_row_shape_matches_source_published_schema_and_strict_dto(mutation):
    value = snapshot_from_domain(complete_domain())
    row = value["tasks"][0]
    if mutation == "missing_field": del row["name"]
    elif mutation == "unknown_field": row["unknown"] = True
    elif mutation == "scope_field": row["document_id"] = value["document_id"]
    elif mutation == "bad_uuid": row["task_id"] = "00000000-0000-0000-0000-00000000000G"
    elif mutation == "coerced_position": row["position"] = "0"
    schema_accepts(value, False)
