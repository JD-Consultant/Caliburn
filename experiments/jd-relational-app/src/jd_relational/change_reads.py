"""Read complete, immutable original-operation changes without write authority.

The fixed stable-ID comparison and the ordinary JD field projection are reused.
Only the change envelope, side placement and stored source basis are added here.
No current head, source owner, DB write, model or executable patch is involved.
"""

from uuid import UUID

from pydantic import ValidationError

from .changes import compare_snapshots
from .domain import COLLECTIONS, FIELDS, SOURCE_COLUMNS, source_target
from .generated.reads import ChangeReadInput, ChangeReadPage
from .reads import READ_FORMAT_VERSION, ReadError, content_projection, pack_read_records
from .references import ReadCursor, ReferenceValidationError, SignedReference
from .snapshots import domain_from_snapshot
from .storage.history import ChangeMaterial, HistoryError


def _public_fields(change):
    """Map fixed structural columns to public semantics; never publish row IDs."""
    result = set()
    for field in change.changed_fields:
        if change.entity_kind == "source_link" and field in SOURCE_COLUMNS:
            # Null columns on creation/deletion carry no target change.
            if any(row is not None and row[field] is not None for row in (change.before, change.after)):
                result.add("related_capability_ref" if field == "linked_capability_id" else "target_ref")
        elif change.entity_kind == "task_capability" and field in {"task_id", "capability_id"}:
            result.add(field.removesuffix("_id") + "_ref")
        elif (change.entity_kind == "task" and field == "duty_id") or (
            change.entity_kind == "detail" and field == "task_id"
        ):
            result.add("container_ref")
        elif not field.endswith("_id"):
            result.add(field)
    return sorted(result)


def _neighbors(rows, identity, id_field):
    ordered = sorted(rows, key=lambda row: (row["position"], row[id_field]))
    index = next(i for i, row in enumerate(ordered) if row[id_field] == identity)
    return (ordered[index - 1] if index else None,
            ordered[index + 1] if index + 1 < len(ordered) else None)


class _Side:
    """Index the shared, fixed projection once per historical side."""

    def __init__(self, value, codec):
        self.value = value
        self.projection = content_projection(value, codec, "history")
        self.token = self.projection.token
        self.sections, self.containers, self.items = {}, {}, {}
        self.fields, self.relations, self.sources = {}, {}, {}
        for row in self.projection.records():
            kind = row["type"]
            if kind == "section":
                self.sections[row["section_ref"]] = row
            elif kind == "container":
                self.containers[row["container_ref"]] = row
            elif kind == "item":
                self.items[row["item_ref"]] = row
            elif kind == "field":
                self.fields[(row["item_ref"], row["name"])] = row
            elif kind == "task_capability":
                self.relations[(row["task_ref"], row["capability_ref"])] = row
            elif kind == "source":
                self.sources[(row["target_ref"], row["related_capability_ref"], row["source_ref"])] = row

    def source_record(self, row):
        kind, identity, *related = source_target(row)
        target = (self.token("field", "profile", field=identity) if kind == "profile"
                  else self.token("item", "task" if kind == "relation" else kind, identity))
        capability = self.token("item", "capability", related[0]) if related else None
        return self.sources[(target, capability, row["source_ref"])]

    def values(self, entity_kind, row):
        if entity_kind == "profile":
            fields = [self.fields[(None, name)] for name in sorted(FIELDS["profile"])]
            sections = list(dict.fromkeys(field["section_ref"] for field in fields))
            return [self.sections[ref] for ref in sections] + fields
        if entity_kind == "task_capability":
            record = self.relations[(self.token("item", "task", row["task_id"]),
                                     self.token("item", "capability", row["capability_id"]))]
            return [self.sections[record["section_ref"]], record]
        item_ref = self.token("item", entity_kind, row[f"{entity_kind}_id"])
        item = self.items[item_ref]
        return [self.sections[item["section_ref"]], self.containers[item["container_ref"]], item,
                *[self.fields[(item_ref, name)] for name in sorted(FIELDS[entity_kind])]]

    def placement(self, entity_kind, row):
        if entity_kind == "source_link":
            record = self.source_record(row)
            siblings = [other for other in self.value["source_links"] if source_target(other) == source_target(row)]
            before, after = _neighbors(siblings, row["source_link_id"], "source_link_id")
            return dict(type="source_placement", target_ref=record["target_ref"],
                        related_capability_ref=record["related_capability_ref"],
                        previous_source_ref=before["source_ref"] if before else None,
                        next_source_ref=after["source_ref"] if after else None)
        if entity_kind == "task_capability":
            siblings = [other for other in self.value["task_capabilities"] if other["task_id"] == row["task_id"]]
            before, after = _neighbors(siblings, row["capability_id"], "capability_id")
            return dict(type="relation_placement", task_ref=self.token("item", "task", row["task_id"]),
                        previous_capability_ref=self.token("item", "capability", before["capability_id"]) if before else None,
                        next_capability_ref=self.token("item", "capability", after["capability_id"]) if after else None)
        identity = row[f"{entity_kind}_id"]
        item = self.items[self.token("item", entity_kind, identity)]
        siblings = [other for other in self.value[COLLECTIONS[entity_kind]].values()
                    if self.items[self.token("item", entity_kind, other[f"{entity_kind}_id"])]["container_ref"] == item["container_ref"]]
        before, after = _neighbors(siblings, identity, f"{entity_kind}_id")
        return dict(type="item_placement", container_ref=item["container_ref"],
                    previous_item_ref=self.token("item", entity_kind, before[f"{entity_kind}_id"]) if before else None,
                    next_item_ref=self.token("item", entity_kind, after[f"{entity_kind}_id"]) if after else None)


def _records(changes, before, after):
    result = []
    for index, change in enumerate(changes):
        result.append(dict(type="change", change_index=index, kind=change.kind,
                           entity_kind=change.entity_kind, before_exists=change.before is not None,
                           after_exists=change.after is not None, changed_fields=_public_fields(change)))
        for side_name, side, row in (("before", before, change.before), ("after", after, change.after)):
            if row is None:
                continue
            common = dict(change_index=index, side=side_name)
            if change.entity_kind == "source_link":
                result.append(dict(type="source_value", **common, record=side.source_record(row),
                                   basis_digest=row["basis_digest"], position=row["position"]))
            else:
                result.extend(dict(type="value", **common, record=record) for record in side.values(change.entity_kind, row))
            if change.kind in {"move", "reorder"}:
                result.append(dict(**side.placement(change.entity_kind, row), **common))
        for task_id in change.affected_task_ids:
            result.append(dict(type="affected_task", change_index=index,
                               before_task_ref=before.token("item", "task", task_id) if task_id in before.value["tasks"] else None,
                               after_task_ref=after.token("item", "task", task_id) if task_id in after.value["tasks"] else None))
    return result


def project_revision_changes(base, result, codec):
    """The same complete, fixed before/after projection for an operation or run."""
    left = domain_from_snapshot(base.snapshot, str(base.revision_id))
    right = domain_from_snapshot(result.snapshot, str(result.revision_id))
    if (base.document_id != result.document_id or left["document_id"] != base.document_id
            or right["document_id"] != result.document_id):
        raise ReadError("read_failed")
    changes = compare_snapshots(base.snapshot, result.snapshot)
    return len(changes), _records(changes, _Side(left, codec), _Side(right, codec))


class ChangeReadService:
    def __init__(self, history_reader, codec, *, page_bytes=32768):
        if type(page_bytes) is not int or not 4096 <= page_bytes <= 1024 * 1024:
            raise ValueError("invalid_page_budget")
        self.history, self.codec, self.page_bytes = history_reader, codec, page_bytes

    def _request(self, document_id, arguments):
        try:
            request = ChangeReadInput.model_validate(arguments, strict=True)
            target = self.codec.resolve(request.change_ref, document_id=document_id,
                                        roles={"change"}, purposes={"observation"})
            cursor = (self.codec.resolve_cursor(request.cursor, document_id=document_id, view="change",
                                                revision_id=target.revision_id, operation_id=target.entity_id)
                      if request.cursor is not None else None)
            return request, target, cursor
        except ReferenceValidationError:
            # This immutable view has no current-head staleness semantics.
            raise ReadError("invalid_ref") from None
        except ValidationError:
            raise ReadError("invalid_input") from None
        except Exception:
            raise ReadError("read_failed") from None

    def read(self, document_id, arguments):
        request, target, cursor = self._request(document_id, arguments)
        try:
            material = self.history.read_change(document_id, UUID(target.entity_id))
            if not isinstance(material, ChangeMaterial):
                raise ValueError("invalid_change_material")
            receipt, base, result = material.receipt, material.base, material.result
            if receipt.document_id != document_id or str(receipt.operation_id) != target.entity_id:
                raise ValueError("invalid_material_scope")
            if receipt.status != "committed":
                raise ReadError("invalid_ref")
            if str(receipt.result_revision_id) != target.revision_id:
                raise ReadError("invalid_ref")
            if (base is None or result is None or base.document_id != document_id or result.document_id != document_id
                or base.revision_id != receipt.base_revision_id or result.revision_id != receipt.result_revision_id
                or result.parent_revision_id != base.revision_id or result.producer_operation_id != receipt.operation_id
                or result.origin != receipt.origin):
                raise ValueError("invalid_material_pair")
            total_changes, records = project_revision_changes(base, result, self.codec)
            start = cursor.offset if cursor else 0
            if start > len(records) or cursor is not None and start == len(records):
                raise ReadError("invalid_ref")
            remaining = records[start:]
            operation_ref = self.codec.issue(SignedReference(document_id=document_id, revision_id=None,
                purpose="observation", role="operation", kind="operation", entity_id=target.entity_id))
            def revision_ref(revision):
                return self.codec.issue(SignedReference(document_id=document_id, revision_id=str(revision),
                    purpose="history", role="revision", kind="revision"))
            base_ref, result_ref = revision_ref(base.revision_id), revision_ref(result.revision_id)

            def page_at(end, oversized=False):
                more = start + end < len(records)
                next_cursor = self.codec.issue_cursor(ReadCursor(document_id=document_id, view="change",
                    revision_id=target.revision_id, operation_id=target.entity_id, offset=start + end)) if more else None
                return dict(format_version=READ_FORMAT_VERSION, view="change", access="history", change_ref=request.change_ref,
                            operation_ref=operation_ref, base_revision_ref=base_ref, result_revision_ref=result_ref,
                            origin=receipt.origin, records=remaining[:end], start_index=start, total_records=len(records),
                            total_changes=total_changes, has_more=more, next_cursor=next_cursor, oversized_unit=oversized)

            page = pack_read_records(remaining, page_at, self.page_bytes)
            return ChangeReadPage.model_validate(page, strict=True).model_dump(mode="json")
        except ReadError:
            raise
        except HistoryError as exc:
            raise ReadError("target_missing" if exc.code in {"document_missing", "operation_missing", "revision_missing"}
                            else "read_failed") from None
        except Exception:
            raise ReadError("read_failed") from None
