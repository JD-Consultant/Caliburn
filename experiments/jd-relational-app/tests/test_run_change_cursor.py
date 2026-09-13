"""Real OSS signed run-change continuations; synthetic identities, no DB/model."""

import base64
import hashlib
import json
import traceback
from uuid import UUID

from itsdangerous import URLSafeSerializer
from pydantic import ValidationError
import pytest

from jd_relational.references import (
    MAX_TOKEN_BYTES, ReadCursor, ReferenceCodec, ReferenceValidationError,
    RunChangeCursor, SignedReference,
)


KEY = b"synthetic-run-cursor-not-a-secret-32"
DOC = "aaaaaaaa-0000-4000-8000-000000000001"
RUN = "bbbbbbbb-0000-4000-8000-000000000002"
REV = "cccccccc-0000-4000-8000-000000000003"
DATASET = "synthetic-run-change-dataset"
SALT = "caliburn.jd.run-change-cursor.v1"
IDS = tuple(UUID(bytes=hashlib.sha256(str(i).encode()).digest()[:16]) for i in range(97))


@pytest.fixture
def codec():
    return ReferenceCodec(KEY, DATASET)


def serializer(salt=SALT):
    return URLSafeSerializer(KEY, salt=salt, signer_kwargs={"digest_method": hashlib.sha256},
        serializer_kwargs={"sort_keys": True, "ensure_ascii": False, "allow_nan": False})


def capture(ids=IDS[:3], settled=True):
    return RunChangeCursor.capture(DOC, RUN, ids, settled)


def envelope(cursor=None, **changes):
    return {"format_version": 1, "dataset_id": DATASET,
            "cursor": (cursor or capture()).model_dump(mode="json"), **changes}


def resolve(codec, token, **changes):
    return codec.resolve_run_cursor(token, document_id=changes.get("document_id", DOC),
                                    run_id=changes.get("run_id", RUN))


def test_capture_is_canonical_packed_uuid_set_not_serialized_uuid_strings(codec):
    first = capture(IDS[:3]); reordered = capture(tuple(reversed(IDS[:3])))
    assert first == reordered and first.offset == 0
    assert first.operation_ids == tuple(sorted(IDS[:3]))
    assert first.operations_b64 == base64.urlsafe_b64encode(b"".join(i.bytes for i in sorted(IDS[:3]))).decode("ascii")
    assert set(first.model_dump()) == {"document_id", "run_id", "operations_b64", "settled", "offset"}
    token = codec.issue_run_cursor(first)
    assert resolve(codec, token) == first
    assert serializer().loads(token) == envelope(first)
    assert token == codec.issue_run_cursor(reordered)


@pytest.mark.parametrize("count", [0, 1, 96])
@pytest.mark.parametrize("settled", [False, True])
def test_zero_through_full_capacity_roundtrip_and_max_offset(codec, count, settled):
    cursor = capture(IDS[:count], settled).model_copy(update={"offset": 2**63 - 1})
    token = codec.issue_run_cursor(cursor)
    assert token.isascii() and len(token.encode("ascii")) <= MAX_TOKEN_BYTES
    actual = resolve(ReferenceCodec(KEY, DATASET), token)
    assert actual == cursor and actual.operation_ids == tuple(sorted(IDS[:count]))
    assert type(actual.settled) is bool and actual.settled is settled


def test_full_entropy_96_ids_fit_existing_uncompressed_admission_without_relaxing_bound(codec):
    cursor = capture(IDS[:96])
    raw = json.dumps(envelope(cursor), sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    assert (4 * len(raw) + 2) // 3 + 44 <= MAX_TOKEN_BYTES
    assert len(codec.issue_run_cursor(cursor).encode()) <= MAX_TOKEN_BYTES
    long_scope = ReferenceCodec(KEY, "x" * 256)
    assert resolve(long_scope, long_scope.issue_run_cursor(cursor)) == cursor
    escaped_scope = ReferenceCodec(KEY, "\x01" * 256)
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        escaped_scope.issue_run_cursor(cursor)


def test_run_cursor_and_existing_reference_and_read_cursor_salts_are_not_interchangeable(codec):
    reference = SignedReference(document_id=DOC, revision_id=REV, purpose="current", role="item",
                                kind="task", entity_id=str(IDS[0]))
    old = ReadCursor(document_id=DOC, view="current", revision_id=REV, offset=0)
    run_token = codec.issue_run_cursor(capture())
    for foreign in (codec.issue(reference), codec.issue_cursor(old), serializer("caliburn.jd.chat-history.v1").dumps(envelope())):
        with pytest.raises(ReferenceValidationError):
            resolve(codec, foreign)
    with pytest.raises(ReferenceValidationError):
        codec.resolve(run_token, document_id=DOC, roles={"item"}, purposes={"current"})
    with pytest.raises(ReferenceValidationError):
        codec.resolve_cursor(run_token, document_id=DOC, view="current")
    # The existing token payload/salt/serializer format remains unchanged.
    assert codec.issue(reference) == serializer("caliburn.jd.reference.v1").dumps({
        "format_version": 1, "dataset_id": DATASET, "reference": reference.model_dump(mode="json")})
    assert codec.issue_cursor(old) == serializer("caliburn.jd.cursor.v1").dumps({
        "format_version": 1, "dataset_id": DATASET, "cursor": old.model_dump(mode="json")})


@pytest.mark.parametrize("change", [{"document_id": RUN}, {"run_id": DOC}])
def test_matching_signature_does_not_relax_expected_document_or_run(codec, change):
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        resolve(codec, codec.issue_run_cursor(capture()), **change)


def test_dataset_replacement_and_new_key_reject_prior_cursor_without_registry(codec):
    token = codec.issue_run_cursor(capture())
    for other in (ReferenceCodec(KEY, "other-incarnation"), ReferenceCodec(b"other-synthetic-key-at-least-32bytes", DATASET)):
        with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
            resolve(other, token)


@pytest.mark.parametrize("version", [True, False, 1.0, "1", 0, 2, None])
def test_authenticated_version_still_requires_exact_integer_one(codec, version):
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        resolve(codec, serializer().dumps(envelope(format_version=version)))


@pytest.mark.parametrize("patch", [
    {"settled": 0}, {"settled": 1}, {"settled": "true"}, {"settled": None},
    {"offset": True}, {"offset": False}, {"offset": "1"}, {"offset": 1.0},
    {"offset": -1}, {"offset": 2**63}, {"document_id": DOC.upper()},
    {"document_id": "{" + DOC + "}"}, {"run_id": "native-arbitrary-id"},
    {"operations_b64": None}, {"extra": "SyntheticPrivateCursor"},
])
def test_authenticated_cursor_requires_closed_strict_shape(codec, patch):
    raw = envelope(); raw["cursor"].update(patch)
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        resolve(codec, serializer().dumps(raw))


@pytest.mark.parametrize("packed", [
    "***", "工作", "AAAA", "AA==", base64.urlsafe_b64encode(IDS[0].bytes).decode().rstrip("="),
    base64.urlsafe_b64encode(IDS[0].bytes).decode() + "=",
    base64.urlsafe_b64encode(IDS[0].bytes * 2).decode(),
    base64.urlsafe_b64encode(b"".join(i.bytes for i in IDS)).decode(),
    base64.b64encode(b"\xff" * 16).decode(),
    # Nonzero pad bits decode to the same bytes, but are not canonical encoding.
    "AAAAAAAAAAAAAAAAAAAAAB==",
])
def test_invalid_packed_identity_encoding_is_rejected_even_with_a_valid_signature(codec, packed):
    raw = envelope(); raw["cursor"]["operations_b64"] = packed
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        resolve(codec, serializer().dumps(raw))


@pytest.mark.parametrize("ids", [list(IDS[:2]), (IDS[0], IDS[0]), IDS, (str(IDS[0]),), (None,)])
def test_capture_rejects_invalid_operation_identity_set_without_silently_deduplicating(ids):
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        capture(ids)


@pytest.mark.parametrize("settled", [0, 1, "false", None])
def test_capture_never_coerces_settled(settled):
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
        capture(settled=settled)


def test_issuer_revalidates_copied_or_constructed_internal_model_and_rejects_plain_dict(codec):
    valid = capture()
    for invalid in (valid.model_dump(), valid.model_copy(update={"offset": True}),
                    valid.model_copy(update={"operations_b64": "***"}),
                    RunChangeCursor.model_construct(**{**valid.model_dump(), "settled": 1})):
        with pytest.raises(ReferenceValidationError, match="^invalid_ref$"):
            codec.issue_run_cursor(invalid)
    with pytest.raises(ValidationError):
        RunChangeCursor(**{**valid.model_dump(), "offset": False})


@pytest.mark.parametrize("bad", [None, 1, "", "x" * 4097, "工作", "a/b", "SyntheticPrivateCursor"])
def test_malformed_tokens_return_fixed_safe_failure(codec, bad):
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$") as caught:
        resolve(codec, bad)
    assert caught.value.code == "invalid_ref" and caught.value.__cause__ is None
    assert "SyntheticPrivateCursor" not in "".join(traceback.format_exception(caught.value))


def test_tampering_does_not_echo_signed_payload_or_signature(codec):
    token = codec.issue_run_cursor(capture())
    invalid = token[:-8] + ("A" if token[-8] != "A" else "B") + token[-7:]
    with pytest.raises(ReferenceValidationError, match="^invalid_ref$") as caught:
        resolve(codec, invalid)
    assert invalid not in "".join(traceback.format_exception(caught.value))
    assert caught.value.__cause__ is None
