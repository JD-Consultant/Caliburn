"""Versioned native run metadata, without rewriting older saved requests.

Pydantic's native tagged union selects the exact persisted format. A narrow
before-model check preserves strict integer version tags: Literal[1]/[2] alone
accept bool/float equivalents in Pydantic 2.13.5, even with strict validation.
Only the V2 builder creates new requests; V1 is parsed for history and recovery.
"""

from hashlib import sha256
import json
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator


class AiRecordError(ValueError):
    def __init__(self):
        self.code = "invalid_run_record"
        super().__init__(self.code)


def _uuid(value):
    if type(value) is not str or str(UUID(value)) != value:
        raise ValueError()
    return value


def _digest(payload):
    value = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return sha256(value.encode("utf-8")).hexdigest()


class _RunRecord(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)
    dataset_id: str
    document_id: str
    run_id: str
    request_digest: str = Field(pattern="^[0-9a-f]{64}$")
    status: Literal["running", "completed", "cancelled", "failed"]

    @model_validator(mode="before")
    @classmethod
    def strict_version(cls, value):
        if type(value) is not dict or type(value.get("format_version")) is not int:
            raise ValueError("invalid_format_version")
        return value

    @field_validator("dataset_id", "document_id", "run_id")
    @classmethod
    def canonical_uuid(cls, value):
        return _uuid(value)


class AiRunRecordV1(_RunRecord):
    format_version: Literal[1]


class AiRunRecordV2(_RunRecord):
    format_version: Literal[2]
    start_revision_id: str

    @field_validator("start_revision_id")
    @classmethod
    def canonical_revision(cls, value):
        return _uuid(value)


AiRunRecord = Annotated[AiRunRecordV1 | AiRunRecordV2, Field(discriminator="format_version")]
_RECORD = TypeAdapter(AiRunRecord)


def parse_run_record(value: dict) -> AiRunRecordV1 | AiRunRecordV2:
    try:
        if type(value) is not dict:
            raise ValueError()
        return _RECORD.validate_python(value, strict=True)
    except Exception:
        raise AiRecordError() from None


def parse_run_record_json(value: str) -> AiRunRecordV1 | AiRunRecordV2:
    try:
        if type(value) is not str:
            raise ValueError()
        return parse_run_record(json.loads(value))
    except Exception:
        raise AiRecordError() from None


def request_digest_for_record(record: AiRunRecordV1 | AiRunRecordV2, text: str) -> str:
    """Verify this actual saved version; never infer a missing V1 revision."""
    payload = {"dataset_id": record.dataset_id, "document_id": record.document_id, "text": text}
    if type(record) is AiRunRecordV2:
        payload.update(format_version=2, start_revision_id=record.start_revision_id)
    elif type(record) is not AiRunRecordV1:
        raise AiRecordError()
    return _digest(payload)


def build_run_record(dataset_id: str, document_id: str, run_id: str, text: str, *,
                     start_revision_id: str) -> AiRunRecordV2:
    """Typed V2 metadata only; original Human validation belongs to its caller."""
    try:
        return AiRunRecordV2(format_version=2, dataset_id=dataset_id, document_id=document_id,
            run_id=run_id, start_revision_id=start_revision_id, status="running",
            request_digest=_digest({"format_version": 2, "dataset_id": dataset_id,
                "document_id": document_id, "start_revision_id": start_revision_id, "text": text}))
    except Exception:
        raise AiRecordError() from None
