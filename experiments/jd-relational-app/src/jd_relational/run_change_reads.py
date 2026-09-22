"""Fixed captured AI changes, reusing the original saved-revision projection.

The chat owner supplies a native-verified capture on the first request. Later
pages use only that signed capture. No writer, provider, current JD or second
run authority is used, and a capture is never silently advanced to newer work.
"""
from copy import deepcopy
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from .change_reads import project_revision_changes
from .generated.chat_http import ChatRunChangePage
from .reads import ReadError, pack_read_records
from .references import ReferenceValidationError, RunChangeCursor, SignedReference
from .storage.history import HistoryError, RunChangeMaterial


@lru_cache(maxsize=1)
def _page_contract():
    # The two fixed, shipped SSOT resources are loaded once. No remote resolver.
    root = Path(__file__).resolve().parents[2] / "contracts"
    schemas = {name: json.loads((root / name).read_text(encoding="utf-8"))
               for name in ("jd-chat-http.schema.json", "jd-read.schema.json")}
    registry = Registry().with_resources((name, Resource.from_contents(schema))
                                         for name, schema in schemas.items())
    validator = Draft202012Validator({"$ref": "jd-chat-http.schema.json#/$defs/ChatRunChangePage"},
                                     registry=registry)
    return schemas["jd-chat-http.schema.json"], validator


def run_change_openapi_conditions():
    # Pinned model generation omits if/then. Copy these exact source clauses;
    # inline their sole local string definition for the OpenAPI resource root.
    schema, _ = _page_contract()
    conditions = deepcopy(schema["$defs"]["ChatRunChangePage"]["allOf"])
    for condition in conditions:
        fields = condition["then"]["properties"]
        for name in ("base_revision_ref", "result_revision_ref"):
            if fields.get(name) == {"$ref": "#/$defs/ChatOpaqueRef"}:
                fields[name] = deepcopy(schema["$defs"]["ChatOpaqueRef"])
    return conditions


class RunChangeReadService:
    def __init__(self, history, codec, *, page_bytes=32768):
        if type(page_bytes) is not int or not 4096 <= page_bytes <= 1024 * 1024:
            raise ValueError("invalid_page_budget")
        self.history, self.codec, self.page_bytes = history, codec, page_bytes

    def read(self, document_id, run_id, *, cursor=None, captured=None):
        try:
            if (cursor is None) == (captured is None):
                raise ReadError("invalid_input")
            try:
                capture = (self.codec.resolve_run_cursor(cursor, document_id=document_id, run_id=run_id)
                           if cursor is not None else captured)
            except ReferenceValidationError:
                raise ReadError("invalid_ref") from None
            if (not isinstance(capture, RunChangeCursor) or capture.document_id != document_id
                    or capture.run_id != run_id or cursor is None and capture.offset != 0):
                raise ReadError("invalid_ref")
            # Revalidation by the codec also guards caller-created model_copy instances.
            capture_ref = self.codec.issue_run_cursor(capture.model_copy(update={"offset": 0}))
            material = self.history.read_run_change(document_id, run_id, capture.operation_ids)
            if (not isinstance(material, RunChangeMaterial)
                    or {row.operation_id for row in material.receipts} != set(capture.operation_ids)
                    or len(material.receipts) != len(capture.operation_ids)
                    or any(row.document_id != document_id or row.ai_run_id != run_id
                           or row.origin != "ai" or row.status != "committed" for row in material.receipts)):
                raise ReadError("read_failed")
            base, result = material.base, material.result
            if material.continuity == "continuous":
                if (not material.receipts or base is None or result is None
                        or base.document_id != document_id or result.document_id != document_id
                        or base.revision_id != material.receipts[0].base_revision_id
                        or result.revision_id != material.receipts[-1].result_revision_id):
                    raise ReadError("read_failed")
                total_changes, records = project_revision_changes(base, result, self.codec)
            else:
                if (material.continuity not in {"none", "discontinuous"} or base is not None or result is not None
                        or (material.continuity == "none") != (len(material.receipts) == 0)):
                    raise ReadError("read_failed")
                total_changes, records = 0, []
            start = capture.offset
            if start > len(records) or cursor is not None and start == len(records):
                raise ReadError("invalid_ref")

            def revision_ref(value):
                return None if value is None else self.codec.issue(SignedReference(
                    document_id=document_id, revision_id=str(value.revision_id),
                    purpose="history", role="revision", kind="revision"))

            base_ref, result_ref = revision_ref(base), revision_ref(result)
            remaining = records[start:]
            def page_at(end, oversized=False):
                more = start + end < len(records)
                next_cursor = self.codec.issue_run_cursor(capture.model_copy(
                    update={"offset": start + end})) if more else None
                return dict(format_version=1, view="run_change", access="history",
                    dataset_id=self.codec.dataset_id, document_id=document_id, run_id=run_id,
                    capture_ref=capture_ref, effects_state="settled" if capture.settled else "unconfirmed",
                    continuity=material.continuity, captured_operation_count=len(material.receipts),
                    base_revision_ref=base_ref, result_revision_ref=result_ref,
                    records=remaining[:end], start_index=start, total_records=len(records),
                    total_changes=total_changes, has_more=more, next_cursor=next_cursor, oversized_unit=oversized)

            page = pack_read_records(remaining, page_at, self.page_bytes)
            # Validate source conditionals as well as generated strict scalars.
            _page_contract()[1].validate(page)
            return ChatRunChangePage.model_validate(page, strict=True).model_dump(mode="json")
        except ReadError:
            raise
        except HistoryError as error:
            raise ReadError("target_missing" if error.code == "document_missing" else
                            "invalid_ref" if error.code in {"operation_missing", "revision_missing"}
                            else "read_failed") from None
        except Exception:
            raise ReadError("read_failed") from None
