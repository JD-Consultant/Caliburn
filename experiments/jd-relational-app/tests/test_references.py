"""Real OSS signer, synthetic scopes and new-process validation; no DB/LLM."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback
from uuid import UUID, uuid4

from itsdangerous import URLSafeSerializer
from pydantic import ValidationError
import pytest

from jd_relational.domain import CommandContext, Ref, FIELDS
from jd_relational.intents import bind_edit
from jd_relational.references import (
    MAX_TOKEN_BYTES, ReadCursor, ReferenceCodec, ReferenceValidationError,
    SECTION_IDS, SignedReference, field_value_digest,
)


KEY = b"synthetic-test-key-not-a-secret!!1"
DATASET = "synthetic-dataset:restore-1"
DOC = "synthetic-document"
REV = "10000000-0000-4000-8000-000000000001"
ENTITY = "20000000-0000-4000-8000-000000000001"


@pytest.fixture
def codec():
    return ReferenceCodec(KEY, DATASET)


def reference(**overrides):
    values = dict(document_id=DOC, revision_id=REV, purpose="current", role="item", kind="task", entity_id=ENTITY)
    values.update(overrides)
    return SignedReference(**values)


def resolve(codec, token, **overrides):
    args = dict(document_id=DOC, roles={"item"}, purposes={"current"}, revision_id=REV)
    args.update(overrides)
    return codec.resolve(token, **args)


def test_real_signer_roundtrip_is_opaque_not_encrypted(codec):
    value = reference()
    token = codec.issue(value)
    assert token != ENTITY and token.isascii() and len(token.encode("ascii")) <= MAX_TOKEN_BYTES
    assert resolve(codec, token) == value
    # Decode with the official serializer to demonstrate that the payload is JSON.
    raw = URLSafeSerializer(KEY, salt="caliburn.jd.reference.v1",
                           signer_kwargs={"digest_method": hashlib.sha256}).loads(token)
    assert raw["reference"]["entity_id"] == ENTITY
    assert raw["dataset_id"] == DATASET and raw["format_version"] == 1


@pytest.mark.parametrize("kind,field", [(kind, field) for kind, fields in FIELDS.items() for field in fields])
def test_all_fixed_business_fields_can_receive_a_ref(codec, kind, field):
    value = reference(role="field", kind=kind, entity_id=None if kind == "profile" else ENTITY,
                      field=field, value_digest=field_value_digest(None))
    assert resolve(codec, codec.issue(value), roles={"field"}) == value


@pytest.mark.parametrize("child,parent", [
    ("duty", None), ("collaborator", None), ("task", None), ("task", ENTITY),
    ("outcome", ENTITY), ("requirement", ENTITY), ("knowledge", None), ("skill", None),
    ("work_environment", None), ("schedule_travel", None), ("shared_authority", None),
    ("shared_collaboration", None), ("qualification", None),
])
def test_empty_containers_do_not_need_a_preexisting_child(codec, child, parent):
    value = reference(role="container", kind="container", entity_id=parent, child_kind=child)
    assert resolve(codec, codec.issue(value), roles={"container"}) == value


@pytest.mark.parametrize("section", sorted(SECTION_IDS))
def test_six_section_refs_are_fixed_read_locators(codec, section):
    value = reference(role="section", kind="section", entity_id=section)
    assert resolve(codec, codec.issue(value), roles={"section"}) == value


@pytest.mark.parametrize("role", ["item", "field", "container", "section"])
def test_history_ref_at_current_head_is_still_never_a_current_write_ref(codec, role):
    updates = {"purpose": "history", "role": role}
    if role == "field":
        updates.update(field="description", value_digest=field_value_digest("內容"))
    elif role == "container":
        updates.update(kind="container", child_kind="task")
    elif role == "section":
        updates.update(kind="section", entity_id="duties_tasks")
    value = reference(**updates)
    token = codec.issue(value)
    assert resolve(codec, token, roles={role}, purposes={"history"}) == value
    with pytest.raises(ReferenceValidationError) as error:
        resolve(codec, token, roles={role})
    assert error.value.code == "invalid_ref"


@pytest.mark.parametrize("patch", [
    {"document_id": "other"}, {"roles": {"container"}}, {"purposes": {"history"}},
])
def test_valid_signature_does_not_relax_expected_scope(codec, patch):
    with pytest.raises(ReferenceValidationError, match="invalid_ref"):
        resolve(codec, codec.issue(reference()), **patch)


def test_stale_revision_is_distinct_only_after_scope_was_validated(codec):
    token = codec.issue(reference())
    with pytest.raises(ReferenceValidationError, match="stale_view"):
        resolve(codec, token, revision_id=str(uuid4()))
    history = codec.issue(reference(purpose="history"))
    with pytest.raises(ReferenceValidationError, match="invalid_ref"):
        resolve(codec, history, revision_id=str(uuid4()))


@pytest.mark.parametrize("bad", ["", "x" * 4097, "工作", "a/b", "qa:source-owner", None, 23])
def test_malformed_or_foreign_owner_tokens_never_become_jd_refs(codec, bad):
    with pytest.raises(ReferenceValidationError, match="invalid_ref"):
        resolve(codec, bad)


def test_payload_and_signature_tampering_are_rejected_without_echo(codec):
    token = codec.issue(reference())
    for bad in ("x" + token[1:], token[:-2] + ("AA" if not token.endswith("AA") else "BB")):
        with pytest.raises(ReferenceValidationError) as error:
            resolve(codec, bad)
        assert error.value.code == "invalid_ref"
        assert bad not in "".join(traceback.format_exception(error.value))
        assert error.value.__cause__ is None


@pytest.mark.parametrize("patch", [
    {"format_version": 2}, {"format_version": True}, {"unexpected": "never accepted"},
    {"dataset_id": "a new incarnation"},
])
def test_authenticated_envelope_still_requires_closed_supported_shape(codec, patch):
    raw = {"format_version": 1, "dataset_id": DATASET, "reference": reference().model_dump()}
    raw.update(patch)
    token = URLSafeSerializer(KEY, salt="caliburn.jd.reference.v1",
                              signer_kwargs={"digest_method": hashlib.sha256}).dumps(raw)
    with pytest.raises(ReferenceValidationError, match="invalid_ref"):
        resolve(codec, token)


@pytest.mark.parametrize("patch", [
    {"role": "source"}, {"kind": "sql"}, {"revision_id": None}, {"entity_id": "task-a"},
    {"field": "description"}, {"child_kind": "task"}, {"value_digest": "a" * 64},
    {"role": "field", "field": "description", "value_digest": None},
    {"role": "field", "field": "sql", "value_digest": "a" * 64},
    {"role": "container", "kind": "container", "child_kind": "skill"},
    {"role": "section", "kind": "section", "entity_id": "arbitrary"},
    {"role": "revision", "kind": "revision", "entity_id": None},
    {"role": "operation", "kind": "operation", "purpose": "current", "revision_id": None},
])
def test_locator_combinations_cannot_be_coerced_into_other_capabilities(patch):
    with pytest.raises(ValidationError):
        reference(**patch)


@pytest.mark.parametrize("role", ["revision", "operation", "change"])
def test_observation_refs_are_not_writable_targets(codec, role):
    value = reference(role=role, kind=role, purpose="observation",
                      entity_id=None if role == "revision" else ENTITY,
                      revision_id=None if role == "operation" else REV)
    token = codec.issue(value)
    assert resolve(codec, token, roles={role}, purposes={"observation"}, revision_id=None) == value
    with pytest.raises(ReferenceValidationError):
        resolve(codec, token)


def test_issuer_revalidates_constructed_or_copied_models_and_rejects_dicts(codec):
    for invalid in (reference().model_dump(), reference().model_copy(update={"kind": "sql"}),
                    SignedReference.model_construct(document_id=DOC, revision_id=REV,
                        purpose="current", role="item", kind="task", entity_id="unvalidated")):
        with pytest.raises(ReferenceValidationError):
            codec.issue(invalid)


def test_dataset_rebuild_or_restore_invalidates_old_refs_without_registry(codec):
    token = codec.issue(reference())
    assert resolve(ReferenceCodec(KEY, DATASET), token) == reference()
    for different in (ReferenceCodec(KEY, "synthetic-dataset:restore-2"),
                      ReferenceCodec(b"another-synthetic-key-long-enough", DATASET)):
        with pytest.raises(ReferenceValidationError):
            resolve(different, token)


def test_new_python_process_can_validate_same_key_dataset_token(codec):
    token = codec.issue(reference())
    code = """import json,sys
sys.path.insert(0, 'src')
from jd_relational.references import ReferenceCodec
x=json.load(sys.stdin)
r=ReferenceCodec(bytes.fromhex(x['key']),x['dataset']).resolve(x['token'],document_id=x['doc'],roles={'item'},purposes={'current'},revision_id=x['rev'])
print(json.dumps(r.model_dump()))
"""
    result = subprocess.run([sys.executable, "-c", code],
        input=json.dumps({"key": KEY.hex(), "dataset": DATASET, "doc": DOC, "rev": REV, "token": token}),
        text=True, capture_output=True, check=True, timeout=10,
        cwd=Path(__file__).resolve().parents[1])
    assert json.loads(result.stdout) == reference().model_dump()


def test_ordinary_refs_have_no_clock_expiry(codec, monkeypatch):
    monkeypatch.setattr(time, "time", lambda: (_ for _ in ()).throw(AssertionError("clock must not be consulted")))
    assert resolve(codec, codec.issue(reference())) == reference()


def test_scalar_digest_keeps_null_and_meaningful_content_distinct():
    values = [None, "", " ", "甲\n甲", "甲\r\n甲", "甲😀甲"]
    assert len({field_value_digest(value) for value in values}) == len(values)
    assert field_value_digest("甲😀甲") == hashlib.sha256('"甲😀甲"'.encode("utf-8")).hexdigest()
    with pytest.raises(ReferenceValidationError):
        field_value_digest(32)


def test_refs_and_cursor_size_bound_uses_utf8_scopes_not_character_count():
    maximum_scope = "工" * 85 + "a"
    codec = ReferenceCodec(KEY, maximum_scope)
    value = reference(document_id=maximum_scope)
    cursor = ReadCursor(document_id=maximum_scope, view="item", revision_id=REV, offset=2**63-1, target=value)
    assert len(codec.issue(value)) <= MAX_TOKEN_BYTES
    assert len(codec.issue_cursor(cursor)) <= MAX_TOKEN_BYTES
    with pytest.raises(ValidationError):
        reference(document_id="工" * 86)
    with pytest.raises(ReferenceValidationError):
        ReferenceCodec(KEY, "工" * 86)


@pytest.mark.parametrize("view", ["current", "item", "section", "history", "change"])
def test_cursor_roundtrips_exact_read_scope(codec, view):
    target = None
    if view == "item":
        target = reference()
    elif view == "section":
        target = reference(role="section", kind="section", entity_id="knowledge")
    elif view == "history":
        target = reference(role="revision", kind="revision", purpose="history", entity_id=None)
    operation = ENTITY if view == "change" else None
    cursor = ReadCursor(document_id=DOC, view=view, revision_id=REV, offset=12,
                        target=target, operation_id=operation)
    token = codec.issue_cursor(cursor)
    assert codec.resolve_cursor(token, document_id=DOC, view=view, target=target,
        revision_id=REV, operation_id=operation) == cursor
    with pytest.raises(ReferenceValidationError, match="stale_view"):
        codec.resolve_cursor(token, document_id=DOC, view=view, target=target,
            revision_id=str(uuid4()), operation_id=operation)


def test_history_index_cursor_and_target_scope_validation(codec):
    index = ReadCursor(document_id=DOC, view="history", revision_id=REV, offset=0)
    assert codec.resolve_cursor(codec.issue_cursor(index), document_id=DOC, view="history") == index
    item = ReadCursor(document_id=DOC, view="item", revision_id=REV, offset=0, target=reference())
    token = codec.issue_cursor(item)
    for args in ({"document_id": "another", "view": "item", "target": reference()},
                 {"document_id": DOC, "view": "section", "target": reference()},
                 {"document_id": DOC, "view": "item", "target": reference(entity_id=str(uuid4()))},
                 {"document_id": DOC, "view": "item", "target": None}):
        with pytest.raises(ReferenceValidationError, match="invalid_ref"):
            codec.resolve_cursor(token, **args)


def test_salts_prevent_cursor_and_reference_substitution(codec):
    ref_token = codec.issue(reference())
    cursor_token = codec.issue_cursor(ReadCursor(document_id=DOC, view="current", revision_id=REV, offset=0))
    with pytest.raises(ReferenceValidationError):
        codec.resolve_cursor(ref_token, document_id=DOC, view="current")
    with pytest.raises(ReferenceValidationError):
        resolve(codec, cursor_token)


@pytest.mark.parametrize("patch", [
    {"offset": -1}, {"offset": True}, {"offset": "1"}, {"offset": 2**63},
    {"target": "not a nested token"}, {"view": "arbitrary_sql"},
    {"operation_id": ENTITY}, {"revision_id": "not-uuid"},
])
def test_cursor_rejects_invalid_shapes(patch):
    raw = dict(document_id=DOC, view="current", revision_id=REV, offset=0)
    raw.update(patch)
    with pytest.raises(ValidationError):
        ReadCursor(**raw)


def test_ref_resigning_does_not_change_existing_intent_digest(codec):
    value = reference(role="field", field="description", value_digest=field_value_digest("舊內容"))
    first = codec.issue(value)
    rotated = ReferenceCodec(b"second-synthetic-test-key-32bytes", DATASET)
    second = rotated.issue(value)
    assert first != second
    digests = []
    for signer, token in ((codec, first), (rotated, second)):
        checked = resolve(signer, token, roles={"field"})
        context = CommandContext(DOC, REV, {token: Ref(checked.document_id, checked.revision_id,
            checked.kind, checked.entity_id, field=checked.field)}, {}, lambda: str(uuid4()))
        intent = bind_edit(UUID(ENTITY), "manual", None,
            {"tool": "jd_set_text", "arguments": {"target_field_ref": token, "text": "更正內容", "basis_refs": []}}, context)
        digests.append(intent.request_digest)
    assert digests[0] == digests[1]
