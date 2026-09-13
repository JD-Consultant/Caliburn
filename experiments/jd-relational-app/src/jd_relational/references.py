"""App-issued locators, not authorization or a second persistence authority.

ItsDangerous authenticates the envelope; the App still checks the current saved
revision, target existence and field value before building a CommandContext.
The host injects one durable dataset incarnation and signing key. Normal restart
keeps them; restore/replacement must invalidate the old incarnation. No key file,
registry, source-owner alias, selection issuer or restore procedure lives here.

Payloads are readable, not encrypted. Consumers treat tokens as opaque strings.
There is deliberately no clock expiry: revision/purpose/dataset checks remain
mandatory even when an old token has a valid signature.
"""

import base64
import hashlib
import json
import re
from typing import Literal, Self
from uuid import UUID

from itsdangerous import BadData, URLSafeSerializer
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .domain import COLLECTIONS, CONDITION_KINDS, FIELDS


MAX_TOKEN_BYTES = 4096
MAX_SCOPE_BYTES = 256
SECTION_IDS = frozenset({"profile", "purpose", "duties_tasks", "knowledge", "skills", "conditions"})
Purpose = Literal["current", "history", "observation"]
Role = Literal["item", "field", "container", "section", "revision", "operation", "change"]
View = Literal["current", "item", "section", "history", "change"]
_REF_SALT = "caliburn.jd.reference.v1"
_CURSOR_SALT = "caliburn.jd.cursor.v1"
_RUN_CURSOR_SALT = "caliburn.jd.run-change-cursor.v1"
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")
_TOKEN = re.compile(r"[A-Za-z0-9_.-]+\Z")


class ReferenceValidationError(ValueError):
    """Safe public failure code; never retains a token or serializer exception."""

    def __init__(self, code: Literal["invalid_ref", "stale_view"] = "invalid_ref"):
        self.code = code
        super().__init__(code)


def _require(valid: bool) -> None:
    if not valid:
        raise ValueError("invalid_ref")


def _scope(value: str) -> bool:
    try:
        return bool(value.strip()) and "\x00" not in value and len(value.encode("utf-8")) <= MAX_SCOPE_BYTES
    except UnicodeError:
        return False


def _uuid(value: str | None) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, revalidate_instances="always")


class SignedReference(_Strict):
    document_id: str
    revision_id: str | None
    purpose: Purpose
    role: Role
    kind: str
    entity_id: str | None = None
    field: str | None = None
    child_kind: str | None = None
    value_digest: str | None = None

    @model_validator(mode="after")
    def check_locator(self) -> Self:
        _require(_scope(self.document_id))
        _require(self.revision_id is None or _uuid(self.revision_id))
        if self.role == "operation":
            _require(self.purpose == "observation" and self.kind == "operation"
                     and self.revision_id is None and _uuid(self.entity_id))
        elif self.role == "change":
            _require(self.purpose == "observation" and self.kind == "change"
                     and _uuid(self.revision_id) and _uuid(self.entity_id))
        elif self.role == "revision":
            _require(self.purpose in {"history", "observation"} and self.kind == "revision"
                     and _uuid(self.revision_id) and self.entity_id is None)
        else:
            _require(self.purpose in {"current", "history"} and _uuid(self.revision_id))
            if self.role == "item":
                _require(self.kind in COLLECTIONS and _uuid(self.entity_id))
            elif self.role == "field":
                _require(self.kind in FIELDS and self.field in FIELDS[self.kind])
                _require(self.entity_id is None if self.kind == "profile" else _uuid(self.entity_id))
                _require(isinstance(self.value_digest, str) and bool(_DIGEST.fullmatch(self.value_digest)))
            elif self.role == "section":
                _require(self.kind == "section" and self.entity_id in SECTION_IDS)
            elif self.role == "container":
                _require(self.kind == "container")
                if self.child_kind == "task":
                    _require(self.entity_id is None or _uuid(self.entity_id))
                elif self.child_kind in {"outcome", "requirement"}:
                    _require(_uuid(self.entity_id))
                else:
                    _require(self.child_kind in CONDITION_KINDS | {"duty", "collaborator", "knowledge", "skill"}
                             and self.entity_id is None)
        if self.role != "field":
            _require(self.field is None and self.value_digest is None)
        if self.role != "container":
            _require(self.child_kind is None)
        return self


class ReadCursor(_Strict):
    """Fixed continuation identity; target is a locator, never a nested token."""

    document_id: str
    view: View
    revision_id: str
    offset: int = Field(ge=0, le=2**63 - 1)
    target: SignedReference | None = None
    operation_id: str | None = None

    @model_validator(mode="after")
    def check_scope(self) -> Self:
        _require(_scope(self.document_id) and _uuid(self.revision_id))
        if self.target is not None:
            _require(self.target.document_id == self.document_id and self.target.revision_id == self.revision_id)
        if self.view == "change":
            _require(self.target is None and _uuid(self.operation_id))
        else:
            _require(self.operation_id is None)
            if self.view == "current":
                _require(self.target is None)
            elif self.view in {"item", "section"}:
                _require(self.target is not None and self.target.role == self.view)
            elif self.view == "history":
                _require(self.target is None or self.target.role == "revision")
        return self


def _run_operation_ids(value: str) -> tuple[UUID, ...]:
    # UUID.bytes and standard URL-safe base64 are only a bounded transport
    # representation. ItsDangerous still authenticates the complete envelope.
    _require(type(value) is str and len(value) <= 2048)
    packed = base64.b64decode(value, altchars=b"-_", validate=True)
    _require(len(packed) <= 96 * 16 and len(packed) % 16 == 0)
    _require(base64.urlsafe_b64encode(packed).decode("ascii") == value)
    identities = tuple(UUID(bytes=packed[index:index + 16]) for index in range(0, len(packed), 16))
    _require(len(set(identities)) == len(identities))
    return identities


class RunChangeCursor(_Strict):
    """Captured committed IDs, never a new run lookup or authority to write."""

    document_id: str
    run_id: str
    operations_b64: str = Field(max_length=2048)
    settled: bool
    offset: int = Field(ge=0, le=2**63 - 1)

    @model_validator(mode="after")
    def check_capture(self) -> Self:
        _require(_uuid(self.document_id) and _uuid(self.run_id))
        _run_operation_ids(self.operations_b64)
        return self

    @property
    def operation_ids(self) -> tuple[UUID, ...]:
        return _run_operation_ids(self.operations_b64)

    @classmethod
    def capture(cls, document_id: str, run_id: str, operation_ids: tuple[UUID, ...], settled: bool) -> Self:
        try:
            _require(type(operation_ids) is tuple and len(operation_ids) <= 96)
            _require(all(isinstance(identity, UUID) for identity in operation_ids))
            _require(len(set(operation_ids)) == len(operation_ids))
            packed = b"".join(identity.bytes for identity in sorted(operation_ids))
            return cls(document_id=document_id, run_id=run_id,
                       operations_b64=base64.urlsafe_b64encode(packed).decode("ascii"),
                       settled=settled, offset=0)
        except (ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None


class _Envelope(_Strict):
    format_version: Literal[1]
    dataset_id: str

    @field_validator("format_version", mode="before")
    @classmethod
    def check_version(cls, value):
        # Literal[1] alone accepts True because Python considers True == 1.
        _require(type(value) is int and value == 1)
        return value

    @field_validator("dataset_id")
    @classmethod
    def check_dataset(cls, value: str) -> str:
        _require(_scope(value))
        return value


class _RefEnvelope(_Envelope):
    reference: SignedReference


class _CursorEnvelope(_Envelope):
    cursor: ReadCursor


class _RunCursorEnvelope(_Envelope):
    cursor: RunChangeCursor


def field_value_digest(value: str | None) -> str:
    """Digest the saved scalar exactly; null, empty text and whitespace differ."""
    try:
        _require(value is None or isinstance(value, str))
        raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()
    except (ValueError, TypeError, UnicodeError):
        raise ReferenceValidationError() from None


class ReferenceCodec:
    __slots__ = ("_dataset_id", "_ref_serializer", "_cursor_serializer", "_run_cursor_serializer")

    @property
    def dataset_id(self) -> str:
        return self._dataset_id

    def __init__(self, secret_key: bytes, dataset_id: str):
        try:
            _require(type(secret_key) is bytes and len(secret_key) >= 32)
            _require(isinstance(dataset_id, str) and _scope(dataset_id))
        except ValueError:
            raise ReferenceValidationError() from None
        self._dataset_id = dataset_id
        options = {"signer_kwargs": {"digest_method": hashlib.sha256},
                   "serializer_kwargs": {"sort_keys": True, "ensure_ascii": False, "allow_nan": False}}
        self._ref_serializer = URLSafeSerializer(secret_key, salt=_REF_SALT, **options)
        self._cursor_serializer = URLSafeSerializer(secret_key, salt=_CURSOR_SALT, **options)
        self._run_cursor_serializer = URLSafeSerializer(secret_key, salt=_RUN_CURSOR_SALT, **options)

    @staticmethod
    def _token(token: str) -> None:
        _require(type(token) is str and 0 < len(token) <= MAX_TOKEN_BYTES and bool(_TOKEN.fullmatch(token)))

    def _dump(self, envelope: _RefEnvelope | _CursorEnvelope | _RunCursorEnvelope,
              serializer: URLSafeSerializer) -> str:
        # Admission size is independent of zlib's compression ratio. Worst-case
        # SHA-256 URLSafeSerializer output is ceil(4*n/3)+44 ASCII bytes.
        payload = envelope.model_dump(mode="json")
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
                         allow_nan=False).encode("utf-8")
        _require((4 * len(raw) + 2) // 3 + 44 <= MAX_TOKEN_BYTES)
        token = serializer.dumps(payload)
        self._token(token)
        return token

    def issue(self, reference: SignedReference) -> str:
        try:
            _require(isinstance(reference, SignedReference))
            envelope = _RefEnvelope(format_version=1, dataset_id=self._dataset_id, reference=reference)
            return self._dump(envelope, self._ref_serializer)
        except (ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None

    def resolve(self, token: str, *, document_id: str, roles: set[str], purposes: set[str],
                revision_id: str | None = None) -> SignedReference:
        try:
            self._token(token)
            envelope = _RefEnvelope.model_validate(self._ref_serializer.loads(token), strict=True)
            reference = envelope.reference
            _require(envelope.dataset_id == self._dataset_id and reference.document_id == document_id)
            _require(reference.role in roles and reference.purpose in purposes)
        except (BadData, ValidationError, ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None
        if revision_id is not None and reference.revision_id != revision_id:
            raise ReferenceValidationError("stale_view")
        return reference

    def issue_cursor(self, cursor: ReadCursor) -> str:
        try:
            _require(isinstance(cursor, ReadCursor))
            envelope = _CursorEnvelope(format_version=1, dataset_id=self._dataset_id, cursor=cursor)
            return self._dump(envelope, self._cursor_serializer)
        except (ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None

    def resolve_cursor(self, token: str, *, document_id: str, view: View,
                       target: SignedReference | None = None, revision_id: str | None = None,
                       operation_id: str | None = None) -> ReadCursor:
        try:
            self._token(token)
            envelope = _CursorEnvelope.model_validate(self._cursor_serializer.loads(token), strict=True)
            cursor = envelope.cursor
            _require(envelope.dataset_id == self._dataset_id and cursor.document_id == document_id)
            _require(cursor.view == view and cursor.target == target and cursor.operation_id == operation_id)
        except (BadData, ValidationError, ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None
        if revision_id is not None and cursor.revision_id != revision_id:
            raise ReferenceValidationError("stale_view")
        return cursor

    def issue_run_cursor(self, cursor: RunChangeCursor) -> str:
        try:
            _require(isinstance(cursor, RunChangeCursor))
            envelope = _RunCursorEnvelope(format_version=1, dataset_id=self._dataset_id, cursor=cursor)
            return self._dump(envelope, self._run_cursor_serializer)
        except (ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None

    def resolve_run_cursor(self, token: str, *, document_id: str, run_id: str) -> RunChangeCursor:
        try:
            self._token(token)
            envelope = _RunCursorEnvelope.model_validate(self._run_cursor_serializer.loads(token), strict=True)
            cursor = envelope.cursor
            _require(envelope.dataset_id == self._dataset_id and cursor.document_id == document_id
                     and cursor.run_id == run_id)
            return cursor
        except (BadData, ValidationError, ValueError, TypeError, UnicodeError):
            raise ReferenceValidationError() from None
