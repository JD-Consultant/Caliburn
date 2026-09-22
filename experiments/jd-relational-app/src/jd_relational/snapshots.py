"""Fixed immutable JD content codec; no refs, revisions, SQL or provider state in its digest."""

import hashlib
import json

from pydantic import ValidationError

from .domain import COLLECTIONS, PROFILE_FIELDS, DomainError, validate_content
from .generated.snapshots import DocumentId, JdSnapshot, UuidString


FORMAT_VERSION = 3
ENGINE_PROFILE = "jd-relational-v1"

# Fixed relational projection only. Field validation comes from generated SSOT;
# meaningful content and relationships remain the shared domain's responsibility.
_KEYED = {collection: ("task_details" if kind == "detail" else collection, f"{kind}_id")
          for kind, collection in COLLECTIONS.items()}
_LISTS = {"task_capabilities": ("task_id", "capability_id"), "source_links": ("source_link_id",)}
_DOMAIN_KEYS = {"document_id", "revision", "profile", *_KEYED, *_LISTS}


class SnapshotValidationError(ValueError):
    """Malformed or unsupported content material, without exposing its contents."""


def _invalid() -> None:
    raise SnapshotValidationError("invalid_snapshot") from None


def _json_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _revision(value: str) -> str:
    try:
        return UuidString.model_validate(value, strict=True).root
    except ValidationError:
        _invalid()


def _without_scope(row: dict, document_id: str) -> dict:
    if not isinstance(row, dict):
        _invalid()
    if "document_id" in row and row["document_id"] != document_id:
        _invalid()
    # Only this explicitly redundant field is removed. Generated shape
    # validation rejects any other unknown key, including nested metadata.
    return {key: value for key, value in row.items() if key != "document_id"}


def _canonical_order(value: dict) -> dict:
    for snapshot_name, identity in _KEYED.values():
        value[snapshot_name].sort(key=lambda row: (row["position"], row[identity]))
    for name, identities in _LISTS.items():
        value[name].sort(key=lambda row: (row["position"], *(row[identity] for identity in identities)))
    return value


def _domain_rows(value: dict, revision_id: str) -> dict:
    domain = {"document_id": value["document_id"], "revision": revision_id, "profile": value["profile"]}
    for collection, (snapshot_name, identity) in _KEYED.items():
        rows = {}
        for row in value[snapshot_name]:
            key = row[identity]
            # Check before indexing; a dict comprehension would lose a duplicate
            # ID silently, even when the duplicate's text differs.
            if key in rows:
                _invalid()
            rows[key] = row
        domain[collection] = rows
    for name in _LISTS:
        domain[name] = value[name]
    return domain


def _validated_snapshot(value: dict) -> dict:
    if not isinstance(value, dict):
        _invalid()
    try:
        snapshot = JdSnapshot.model_validate(value, strict=True).model_dump(mode="json")
        # This also rejects malformed Unicode in IDs/source locators, which are
        # not employee content fields and are not normalized by the domain.
        _json_bytes(snapshot)
        domain = _domain_rows(snapshot, "")
        validate_content(domain, snapshot["document_id"])
        return _canonical_order(snapshot)
    except (ValidationError, DomainError, ValueError, TypeError, UnicodeError, RecursionError):
        _invalid()


def snapshot_from_domain(value: dict) -> dict:
    """Validate all input fields and project complete content, without mutation.

    Same-document row scope may be redundant. Revision is validated separately
    and deliberately excluded from content and its digest. No unknown keys are
    discarded, missing nullable facts defaulted, or employee text normalized.
    """
    if not isinstance(value, dict) or set(value) != _DOMAIN_KEYS:
        _invalid()
    _revision(value["revision"])
    document_id = value["document_id"]
    snapshot = {"format_version": FORMAT_VERSION, "engine_profile": ENGINE_PROFILE,
                "document_id": document_id, "profile": _without_scope(value["profile"], document_id)}
    for collection, (snapshot_name, identity) in _KEYED.items():
        if not isinstance(value[collection], dict):
            _invalid()
        rows = []
        for key, row in value[collection].items():
            item = _without_scope(row, document_id)
            if not isinstance(key, str) or item.get(identity) != key:
                _invalid()
            rows.append(item)
        snapshot[snapshot_name] = rows
    for name in _LISTS:
        if not isinstance(value[name], list):
            _invalid()
        snapshot[name] = [_without_scope(row, document_id) for row in value[name]]
    return _validated_snapshot(snapshot)


def domain_from_snapshot(value: dict, revision_id: str) -> dict:
    """Validate stored content and rebuild the existing domain's keyed rows."""
    revision_id = _revision(revision_id)
    return _domain_rows(_validated_snapshot(value), revision_id)


def snapshot_digest(value: dict) -> str:
    """SHA-256 of validated, deterministically ordered JSON UTF-8 content."""
    return hashlib.sha256(_json_bytes(_validated_snapshot(value))).hexdigest()


def empty_domain(document_id: str, revision_id: str) -> dict:
    """Initial complete shape with no invented employee facts; no persistence."""
    try:
        document_id = DocumentId.model_validate(document_id, strict=True).root
        document_id.encode("utf-8")
    except (ValidationError, UnicodeError):
        _invalid()
    return {"document_id": document_id, "revision": _revision(revision_id),
            "profile": dict.fromkeys(PROFILE_FIELDS),
            **{collection: {} for collection in _KEYED}, **{name: [] for name in _LISTS}}
