"""Fixed JD read projection over materialized content and original history.

No SQL transaction survives projection. Issued references are locators, not
writer permission. External source availability is deliberately not inferred.
"""

import json
from uuid import UUID

from pydantic import ValidationError

from .domain import (
    COLLECTIONS,
    CONDITION_KINDS,
    FIELDS,
    CommandContext,
    Ref,
    Source,
    source_target,
    source_basis_digest,
)
from .generated.reads import ReadInput, ReadPage
from .references import (
    ReferenceCodec,
    SignedReference,
    ReadCursor,
    ReferenceValidationError,
    field_value_digest,
)
from .snapshots import domain_from_snapshot, snapshot_from_domain, SnapshotValidationError
from .storage.history import HistoryError
from .storage.service import StorageError
from .transport import manual_command, TransportError

SECTIONS = {
    "profile": "基本資料",
    "purpose": "職務目的",
    "duties_tasks": "職責與任務",
    "knowledge": "所需知識",
    "skills": "所需技能",
    "conditions": "適用條件與責任邊界",
}


class ReadError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def read_json(value):
    """The exact inner tool-result encoding used by both paging and transport."""
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _section(kind, row=None, field=None):
    if kind == "profile":
        return "purpose" if field == "purpose" else "profile"
    if kind == "collaborator":
        return "profile"
    if kind == "condition":
        return "conditions"
    if kind == "capability":
        return "knowledge" if row["kind"] == "knowledge" else "skills"
    return "duties_tasks"


def _exists(value, ref):
    """Check a typed locator against this material, never query a newer head."""
    if ref.role == "container":
        if (
            ref.child_kind == "task"
            and ref.entity_id is not None
            and ref.entity_id not in value["duties"]
        ):
            raise ReadError("target_missing")
        if ref.child_kind in {"outcome", "requirement"} and ref.entity_id not in value["tasks"]:
            raise ReadError("target_missing")
    elif ref.role in {"item", "field"}:
        if ref.kind != "profile" and ref.entity_id not in value[COLLECTIONS[ref.kind]]:
            raise ReadError("target_missing")
        if ref.role == "field":
            row = (
                value["profile"]
                if ref.kind == "profile"
                else value[COLLECTIONS[ref.kind]][ref.entity_id]
            )
            if field_value_digest(row[ref.field]) != ref.value_digest:
                raise ReadError("stale_view")


class _Projection:
    def __init__(self, value, codec, purpose):
        self.value = value
        self.codec = codec
        self.purpose = purpose

    def token(self, role, kind, entity_id=None, field=None, child_kind=None):
        digest = None
        if role == "field":
            row = (
                self.value["profile"]
                if kind == "profile"
                else self.value[COLLECTIONS[kind]][entity_id]
            )
            digest = field_value_digest(row[field])
        return self.codec.issue(
            SignedReference(
                document_id=self.value["document_id"],
                revision_id=self.value["revision"],
                purpose=self.purpose,
                role=role,
                kind=kind,
                entity_id=entity_id,
                field=field,
                child_kind=child_kind,
                value_digest=digest,
            )
        )

    def _included(self, target):
        value = self.value
        if target is None:
            return None
        if target.role == "section":
            keep = {
                ("profile", name)
                for name in value["profile"]
                if _section("profile", field=name) == target.entity_id
            }
            keep |= {
                (kind, identity)
                for kind, collection in COLLECTIONS.items()
                for identity, row in value[collection].items()
                if _section(kind, row) == target.entity_id
            }
        else:
            _exists(value, target)
            keep = {(target.kind, target.entity_id)}
        tasks = {identity for kind, identity in keep if kind == "task"}
        if target.role == "item" and target.kind == "duty":
            tasks |= {
                identity
                for identity, row in value["tasks"].items()
                if row["duty_id"] == target.entity_id
            }
        if target.role == "item" and target.kind == "capability":
            tasks |= {
                row["task_id"]
                for row in value["task_capabilities"]
                if row["capability_id"] == target.entity_id
            }
        if target.role == "item" and target.kind == "detail":
            tasks.add(value["details"][target.entity_id]["task_id"])
        keep |= {("task", identity) for identity in tasks}
        keep |= {
            ("duty", value["tasks"][identity]["duty_id"])
            for identity in tasks
            if value["tasks"][identity]["duty_id"]
        }
        keep |= {
            ("detail", identity)
            for identity, row in value["details"].items()
            if row["task_id"] in tasks
        }
        keep |= {
            ("capability", row["capability_id"])
            for row in value["task_capabilities"]
            if row["task_id"] in tasks
        }
        return keep

    def records(self, target=None):
        value, token = self.value, self.token
        keep = self._included(target)

        def included(kind, identity):
            return keep is None or (kind, identity) in keep

        section_ids = (
            set(SECTIONS)
            if keep is None
            else {
                _section(
                    kind,
                    None if kind == "profile" else value[COLLECTIONS[kind]][identity],
                    identity if kind == "profile" else None,
                )
                for kind, identity in keep
            }
        )
        if target and target.role == "section":
            section_ids.add(target.entity_id)
        result = []
        section_refs = {name: token("section", "section", name) for name in SECTIONS}
        for name, title in SECTIONS.items():
            if name in section_ids:
                result.append(dict(type="section", section_ref=section_refs[name], title=title))
        containers = [
            ("collaborator", None, "profile", None),
            ("duty", None, "duties_tasks", None),
            ("task", None, "duties_tasks", None),
            ("knowledge", None, "knowledge", None),
            ("skill", None, "skills", None),
        ]
        containers += [(kind, None, "conditions", None) for kind in sorted(CONDITION_KINDS)]
        containers += [
            ("task", identity, "duties_tasks", ("duty", identity))
            for identity in value["duties"]
            if included("duty", identity)
        ]
        containers += [
            (kind, identity, "duties_tasks", ("task", identity))
            for identity in value["tasks"]
            if included("task", identity)
            for kind in ("outcome", "requirement")
        ]
        for kind, identity, section, owner in containers:
            if section in section_ids:
                result.append(
                    dict(
                        type="container",
                        container_ref=token("container", "container", identity, child_kind=kind),
                        section_ref=section_refs[section],
                        owner_ref=token("item", *owner) if owner else None,
                        child_kind=kind,
                    )
                )
        for field in ("job_title", "organization_unit", "employee_name", "reports_to", "purpose"):
            if included("profile", field):
                result.append(
                    dict(
                        type="field",
                        item_ref=None,
                        section_ref=section_refs[_section("profile", field=field)],
                        field_ref=token("field", "profile", field=field),
                        name=field,
                        value=value["profile"][field],
                    )
                )
        for kind, collection in COLLECTIONS.items():
            for identity, row in value[collection].items():
                if not included(kind, identity):
                    continue
                section = _section(kind, row)
                item_type = row["kind"] if kind in {"detail", "capability", "condition"} else kind
                parent = (
                    row["duty_id"]
                    if kind == "task"
                    else row["task_id"] if kind == "detail" else None
                )
                item_ref = token("item", kind, identity)
                result.append(
                    dict(
                        type="item",
                        item_ref=item_ref,
                        section_ref=section_refs[section],
                        kind=item_type,
                        container_ref=token("container", "container", parent, child_kind=item_type),
                        position=row["position"],
                    )
                )
                for field in sorted(FIELDS[kind]):
                    result.append(
                        dict(
                            type="field",
                            item_ref=item_ref,
                            section_ref=section_refs[section],
                            field_ref=token("field", kind, identity, field=field),
                            name=field,
                            value=row[field],
                        )
                    )
        for relation in value["task_capabilities"]:
            if included("task", relation["task_id"]) and included(
                "capability", relation["capability_id"]
            ):
                result.append(
                    dict(
                        type="task_capability",
                        section_ref=section_refs["duties_tasks"],
                        task_ref=token("item", "task", relation["task_id"]),
                        capability_ref=token("item", "capability", relation["capability_id"]),
                        capability_kind=value["capabilities"][relation["capability_id"]]["kind"],
                        position=relation["position"],
                    )
                )
        for link in value["source_links"]:
            target_key = source_target(link)
            kind, identity = target_key[:2]
            if kind == "relation":
                if not included("task", identity) or not included("capability", target_key[2]):
                    continue
                section, target_ref = "duties_tasks", token("item", "task", identity)
                related = token("item", "capability", target_key[2])
            else:
                if not included(kind, identity):
                    continue
                section = _section(
                    kind,
                    None if kind == "profile" else value[COLLECTIONS[kind]][identity],
                    identity if kind == "profile" else None,
                )
                target_ref = (
                    token("field", "profile", field=identity)
                    if kind == "profile"
                    else token("item", kind, identity)
                )
                related = None
            result.append(
                dict(
                    type="source",
                    section_ref=section_refs[section],
                    target_ref=target_ref,
                    related_capability_ref=related,
                    source_ref=link["source_ref"],
                    basis_status=(
                        "current"
                        if source_basis_digest(value, target_key) == link["basis_digest"]
                        else "needs_recheck"
                    ),
                    readability="not_checked",
                )
            )
        return result


class ReadService:
    def __init__(self, current_reader, history_reader, codec: ReferenceCodec, *, page_bytes=32768):
        if type(page_bytes) is not int or not 4096 <= page_bytes <= 1024 * 1024:
            raise ValueError("invalid_page_budget")
        self.current, self.history, self.codec, self.page_bytes = (
            current_reader,
            history_reader,
            codec,
            page_bytes,
        )

    def _revision_ref(self, document, revision):
        return self.codec.issue(
            SignedReference(
                document_id=document,
                revision_id=str(revision),
                purpose="history",
                role="revision",
                kind="revision",
            )
        )

    def _page(
        self,
        records,
        *,
        document,
        revision,
        view,
        access,
        start,
        total,
        target=None,
        tail=False,
        index=False
    ):
        def page_at(end, oversized=False):
            more = end < len(records) or tail
            offset = records[end - 1]["revision_number"] if index and end else start + end
            cursor = (
                self.codec.issue_cursor(
                    ReadCursor(
                        document_id=document,
                        view=view,
                        revision_id=str(revision),
                        offset=offset,
                        target=target,
                    )
                )
                if more
                else None
            )
            return dict(
                format_version=1,
                view=view,
                access=access,
                revision_ref=self._revision_ref(document, revision),
                records=records[:end],
                start_index=start,
                total_records=total,
                has_more=more,
                next_cursor=cursor,
                oversized_unit=oversized,
            )

        count = 0
        for end in range(1, len(records) + 1):
            if len(read_json(page_at(end)).encode("utf-8")) > self.page_bytes:
                break
            count = end
        if records and count == 0:
            result = page_at(1, True)
        else:
            result = page_at(count)
        return ReadPage.model_validate(result, strict=True).model_dump(mode="json")

    def _index(self, document, cursor):
        # HistoryReader fixes this index's upper revision; new heads stay out.
        page = self.history.list_revisions(
            document,
            UUID(cursor.revision_id) if cursor else None,
            cursor.offset if cursor else None,
            limit=100,
        )
        records = []
        for revision in page.revisions:
            operation = revision.producer_operation_id
            common = dict(document_id=document, purpose="observation", entity_id=str(operation))
            records.append(
                dict(
                    type="revision",
                    revision_ref=self._revision_ref(document, revision.revision_id),
                    revision_number=revision.revision_number,
                    origin=revision.origin,
                    created_at=revision.created_at.isoformat(),
                    operation_ref=(
                        self.codec.issue(
                            SignedReference(
                                **common, revision_id=None, role="operation", kind="operation"
                            )
                        )
                        if operation
                        else None
                    ),
                    change_ref=(
                        self.codec.issue(
                            SignedReference(
                                **common,
                                revision_id=str(revision.revision_id),
                                role="change",
                                kind="change"
                            )
                        )
                        if operation
                        else None
                    ),
                )
            )
        start = page.anchor_revision_number - (records[0]["revision_number"] if records else 0)
        return self._page(
            records,
            document=document,
            revision=page.anchor_revision_id,
            view="history",
            access="history",
            start=start,
            total=page.anchor_revision_number,
            tail=page.has_more,
            index=True,
        )

    def _request(self, document_id, arguments):
        """Only caller input/ref validation can ask the caller to correct it."""
        try:
            request = ReadInput.model_validate(arguments, strict=True)
            view, target = request.view, None
            if request.target_ref is not None:
                roles = (
                    {"item"}
                    if view == "item"
                    else (
                        {"section"}
                        if view == "section"
                        else {"revision"} if view == "history" else set()
                    )
                )
                target = self.codec.resolve(
                    request.target_ref,
                    document_id=document_id,
                    roles=roles,
                    purposes={"current", "history", "observation"},
                )
            elif view in {"item", "section"}:
                raise ReadError("invalid_input")
            cursor = (
                self.codec.resolve_cursor(
                    request.cursor, document_id=document_id, view=view, target=target
                )
                if request.cursor
                else None
            )
            return view, target, cursor
        except ReadError:
            raise
        except ReferenceValidationError as exc:
            raise ReadError(exc.code) from None
        except ValidationError:
            raise ReadError("invalid_input") from None
        except Exception:
            raise ReadError("read_failed") from None

    def read(self, document_id, arguments):
        view, target, cursor = self._request(document_id, arguments)
        try:
            if view == "history" and target is None:
                return self._index(document_id, cursor)
            access = (
                "history"
                if view == "history" or target and target.purpose == "history"
                else "current"
            )
            if access == "history":
                material = self.history.read_revision(document_id, UUID(target.revision_id))
            else:
                material = self.current.read_current(document_id)
            revision = str(material.revision_id)
            if (target and target.revision_id != revision) or (
                cursor and cursor.revision_id != revision
            ):
                raise ReadError("stale_view")
            value = domain_from_snapshot(material.snapshot, revision)
            if value["document_id"] != document_id:
                raise ReadError("read_failed")
            records = _Projection(value, self.codec, access).records(
                target if view in {"item", "section"} else None
            )
            start = cursor.offset if cursor else 0
            if start > len(records) or cursor and start == len(records):
                raise ReadError("invalid_ref")
            return self._page(
                records[start:],
                document=document_id,
                revision=revision,
                view=view,
                access=access,
                start=start,
                total=len(records),
                target=target,
            )
        except ReadError:
            raise
        except (StorageError, HistoryError) as exc:
            code = (
                "target_missing"
                if exc.code in {"document_missing", "revision_missing", "operation_missing"}
                else "read_failed"
            )
            raise ReadError(code) from None
        except Exception:
            raise ReadError("read_failed") from None


def command_context(value, command, codec, source_resolver, new_id):
    """Resolve caller tokens to trusted material; caller still owns admission.

    Selection issuance is a separate pending browser integration. It is rejected
    here explicitly instead of treating an item/field token as a selection.
    """
    try:
        command = manual_command(command)
        value = domain_from_snapshot(snapshot_from_domain(value), value["revision"])
        refs, sources = {}, {}

        def visit(node):
            if isinstance(node, list):
                for child in node:
                    visit(child)
            elif isinstance(node, dict):
                for key, child in node.items():
                    if key == "selection_ref":
                        raise ReadError("selection_not_available")
                    if key == "basis_refs":
                        for token in child:
                            if token not in sources:
                                source = source_resolver(token, value["document_id"])
                                if (
                                    not isinstance(source, Source)
                                    or source.document_id != value["document_id"]
                                    or not source.readable
                                ):
                                    raise ReadError("invalid_ref")
                                sources[token] = source
                    elif key.endswith("_ref") and child is not None:
                        ref = codec.resolve(
                            child,
                            document_id=value["document_id"],
                            roles={"item", "field", "container"},
                            purposes={"current"},
                            revision_id=value["revision"],
                        )
                        _exists(value, ref)
                        refs[child] = Ref(
                            value["document_id"],
                            value["revision"],
                            ref.kind,
                            ref.entity_id,
                            ref.field,
                            ref.child_kind,
                        )
                    else:
                        visit(child)

        visit(command["arguments"])
        return CommandContext(value["document_id"], value["revision"], refs, sources, new_id)
    except ReadError:
        raise
    except ReferenceValidationError as exc:
        raise ReadError(exc.code) from None
    except (TransportError, SnapshotValidationError):
        raise ReadError("invalid_input") from None
    except Exception:
        raise ReadError("read_failed") from None
