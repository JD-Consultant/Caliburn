"""Document catalog application boundary, distinct from JD content revisions.

Creation binds the caller's original key and payload. Metadata uses a strong
ETag precondition over this dataset's catalog representation and a database CAS.
No automatic retry, synthetic receipt, replay, or second catalog is introduced.
"""
from dataclasses import asdict
import hashlib
import json
from uuid import UUID

from .generated.catalog_http import (CatalogDocument, CatalogPage, CatalogCreateInput,
    CatalogCreationResult, CatalogCreationLookup, CatalogRenameInput, CatalogArchiveInput)
from .manual_runtime import ManualRuntime
from .transport import REQUEST_LIMIT


class CatalogError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _uuid(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
        return UUID(value)
    except (TypeError, ValueError, AttributeError):
        raise CatalogError("invalid_input") from None


def parse_catalog(value, model):
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError()
            result[key] = item
        return result
    def constant(_):
        raise ValueError()
    try:
        raw = value if type(value) is str else json.dumps(value, ensure_ascii=False, allow_nan=False)
        if len(raw.encode("utf-8")) > REQUEST_LIMIT:
            raise ValueError()
        parsed = json.loads(raw, object_pairs_hook=unique, parse_constant=constant)
        return model.model_validate(parsed, strict=True).model_dump(mode="json")
    except Exception:
        raise CatalogError("invalid_input") from None


def _failure(error):
    code = getattr(error, "code", None)
    codes = {"invalid_input": "invalid_input", "invalid_title": "invalid_input",
        "invalid_create_key": "invalid_input", "document_missing": "document_missing",
        "operation_conflict": "creation_conflict", "metadata_changed": "metadata_changed",
        "document_busy": "busy", "create_unconfirmed": "write_unconfirmed",
        "catalog_unconfirmed": "write_unconfirmed"}
    return CatalogError(codes.get(code, "service_unavailable") if type(code) is str else "service_unavailable")


class CatalogService:
    def __init__(self, runtime: ManualRuntime, dataset_id: str):
        if not isinstance(runtime, ManualRuntime):
            raise ValueError("invalid_catalog_runtime")
        _uuid(dataset_id)
        self.runtime, self.dataset_id = runtime, dataset_id

    def _record(self, record):
        value = asdict(record)
        value["created_at"] = record.created_at.isoformat()
        value["updated_at"] = record.updated_at.isoformat()
        return CatalogDocument.model_validate(value, strict=True).model_dump(mode="json")

    def etag(self, document):
        data = json.dumps([self.dataset_id, document], ensure_ascii=False,
                          sort_keys=True, separators=(",", ":")).encode("utf-8")
        # Entity tag is a representation validator, not an access credential.
        return '"' + hashlib.sha256(data).hexdigest() + '"'

    def get(self, document_id):
        _uuid(document_id)
        try:
            return self._record(self.runtime.storage.catalog_document(document_id))
        except Exception as error:
            raise _failure(error) from None

    def list(self, *, archived=False, after=None, limit=50):
        if (type(limit) is not int or not 1 <= limit <= 100
                or archived is not None and type(archived) is not bool):
            raise CatalogError("invalid_input")
        if after is not None:
            _uuid(after)
        try:
            rows = self.runtime.storage.list_catalog(archived=archived, after=after, limit=limit + 1)
            page = {"dataset_id": self.dataset_id,
                "documents": [self._record(row) for row in rows[:limit]],
                "next_after": rows[limit - 1].document_id if len(rows) > limit else None}
            return CatalogPage.model_validate(page, strict=True).model_dump(mode="json")
        except Exception as error:
            raise _failure(error) from None

    def _creation(self, envelope):
        value = parse_catalog(envelope, CatalogCreateInput)
        if value["dataset_id"] != self.dataset_id:
            raise CatalogError("dataset_changed")
        return value

    def create(self, envelope):
        value = self._creation(envelope)
        try:
            doc = self.runtime.create_document(UUID(value["request_key"]), value["title"])
            return CatalogCreationResult(dataset_id=self.dataset_id,
                request_key=value["request_key"], document_id=doc).model_dump(mode="json")
        except Exception as error:
            raise _failure(error) from None

    def lookup(self, envelope):
        value = self._creation(envelope)
        try:
            doc = self.runtime.storage.lookup_creation(UUID(value["request_key"]), value["title"])
            # A missing row is only a read observation. Original request may run.
            return CatalogCreationLookup.model_validate({"dataset_id": self.dataset_id,
                "request_key": value["request_key"], "document_id": doc,
                "state": "found" if doc is not None else "not_found"}, strict=True).model_dump(mode="json")
        except Exception as error:
            raise _failure(error) from None

    def update(self, document_id, if_match, envelope, *, kind):
        model = {"title": CatalogRenameInput, "archive": CatalogArchiveInput}.get(kind)
        if model is None:
            raise CatalogError("invalid_input")
        value = parse_catalog(envelope, model)
        _uuid(document_id)
        if if_match is None:
            raise CatalogError("precondition_required")
        if type(if_match) is not str or len(if_match) > 256:
            raise CatalogError("invalid_input")
        current = self.get(document_id)
        if if_match != self.etag(current):
            raise CatalogError("metadata_changed")
        try:
            # A newer metadata version between GET and locks fails the SQL CAS.
            record = self.runtime.update_catalog(document_id, current["metadata_version"], **value)
            return self._record(record)
        except Exception as error:
            raise _failure(error) from None
