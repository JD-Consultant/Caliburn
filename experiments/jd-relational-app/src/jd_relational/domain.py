"""Bounded JD candidate construction. No DTO, provider, persistence or receipt code.

The App supplies already shape-validated command arguments and trusted fixture refs.
Ref.kind names an entity; a non-null field denotes a field ref, never an item ref.
Containers use child_kind=task with entity_id=duty_id (None means unassigned),
outcome/requirement with entity_id=task_id, or duty/collaborator/knowledge/skill
and each condition kind with entity_id=None. This is not production ref issuance.

Snapshots hold ID-keyed duties/tasks/details/capabilities/conditions/collaborators,
a profile object, and task_capabilities/source_links lists. Rows use the relational
contract's column names. Existing rows may omit the enclosing document_id; newly
constructed rows include it. The enclosing revision is preserved, never advanced.
"""

from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass, field as dataclass_field
import hashlib
import json

from jd_relational.selection import Selection, SelectionError, replace_utf16


MAX_CHANGES = 64
MAX_FIELD_BYTES = 64 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MAX_TASK_CHILDREN = 128

CONDITION_KINDS = frozenset({"work_environment", "schedule_travel", "shared_authority",
                             "shared_collaboration", "qualification"})
PROFILE_FIELDS = frozenset({"job_title", "organization_unit", "employee_name", "reports_to", "purpose"})
COLLECTIONS = {"duty": "duties", "task": "tasks", "detail": "details",
               "capability": "capabilities", "condition": "conditions", "collaborator": "collaborators"}
FIELDS = {"profile": PROFILE_FIELDS, "duty": frozenset({"name", "scope_text"}),
          "task": frozenset({"name", "description"}), "detail": frozenset({"text"}),
          "capability": frozenset({"name", "description"}), "condition": frozenset({"text"}),
          "collaborator": frozenset({"name", "scope_text"})}
SOURCE_COLUMNS = ("profile_field", "collaborator_id", "duty_id", "task_id", "detail_id",
                  "capability_id", "condition_id", "linked_task_id", "linked_capability_id")


@dataclass(frozen=True)
class Ref:
    document_id: str
    revision: str
    kind: str
    entity_id: str | None = None
    field: str | None = None
    child_kind: str | None = None


@dataclass(frozen=True)
class Source:
    document_id: str
    readable: bool = True


@dataclass(frozen=True)
class CommandContext:
    document_id: str
    base_revision: str
    refs: Mapping[str, Ref]
    sources: Mapping[str, Source]
    new_id: Callable[[], str]
    selections: Mapping[str, Selection] = dataclass_field(default_factory=dict)


class DomainError(ValueError):
    def __init__(self, code: str, message: str, refs: Iterable[str] = ()):
        super().__init__(message)
        self.code = code
        self.message = message
        self.refs = tuple(refs)


def _invalid(message: str, *refs: str) -> None:
    raise DomainError("invalid_input", message, refs)


def _json_bytes(value: object) -> bytes:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, UnicodeError) as exc:
        raise DomainError("invalid_input", "Payload must contain valid JSON and Unicode text.") from exc


def _text(value: str | None, *, required: bool = False) -> str | None:
    if value is None:
        if required:
            _invalid("This content item requires meaningful text.")
        return None
    if not isinstance(value, str):
        _invalid("Text must be a string or an allowed null.")
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError as exc:
        raise DomainError("invalid_input", "Text contains an invalid Unicode surrogate.") from exc
    if size > MAX_FIELD_BYTES or "\x00" in value:
        _invalid("Text exceeds 64 KiB UTF-8 or contains a NUL character.")
    if not value.strip():
        if required:
            _invalid("This content item requires meaningful text.")
        return None
    return value


def _target_from_link(link: dict) -> tuple:
    targets = []
    for kind in ("profile", "collaborator", "duty", "task", "detail", "capability", "condition"):
        column = "profile_field" if kind == "profile" else f"{kind}_id"
        if link.get(column) is not None:
            targets.append((kind, link[column]))
    task, capability = link.get("linked_task_id"), link.get("linked_capability_id")
    if (task is None) != (capability is None):
        _invalid("A relation source must identify both endpoints.")
    if task is not None:
        targets.append(("relation", task, capability))
    if len(targets) != 1:
        _invalid("Each source link must have exactly one typed target.")
    return targets[0]


def _source_columns(target: tuple) -> dict:
    result = dict.fromkeys(SOURCE_COLUMNS)
    if target[0] == "relation":
        result.update(linked_task_id=target[1], linked_capability_id=target[2])
    else:
        result["profile_field" if target[0] == "profile" else f"{target[0]}_id"] = target[1]
    return result


def _basis_content(snapshot: dict, target: tuple) -> dict:
    """Exact non-recursive source context; excludes IDs, order and descendants."""
    kind, identity = target[:2]
    if kind == "profile":
        if identity not in PROFILE_FIELDS:
            _invalid("Unknown profile source target.")
        return {"field": identity, "value": snapshot["profile"].get(identity)}
    if kind == "relation":
        if not any(row["task_id"] == identity and row["capability_id"] == target[2]
                   for row in snapshot["task_capabilities"]):
            _invalid("A source cannot remain on a removed task capability relation.")
        return {"task": _basis_content(snapshot, ("task", identity)),
                "capability": _basis_content(snapshot, ("capability", target[2]))}
    row = snapshot[COLLECTIONS[kind]].get(identity)
    if row is None:
        _invalid("A source cannot remain on a removed content target.")
    keys = {"duty": ("name", "scope_text"), "collaborator": ("name", "scope_text"),
            "task": ("name", "description"), "capability": ("kind", "name", "description"),
            "detail": ("kind", "text"), "condition": ("kind", "text")}[kind]
    return {key: row.get(key) for key in keys}


class _Candidate:
    """One command's private work. There is no mutable session across calls."""

    def __init__(self, snapshot: dict, context: CommandContext):
        self.base = snapshot
        self.context = context
        self.value = deepcopy(snapshot)
        self.pending_basis: dict[tuple, list[str]] = {}
        self.anchor_tails: dict[tuple, str] = {}
        self.used_ids = {identity for name in COLLECTIONS.values() for identity in snapshot[name]}
        self.used_ids.update(link["source_link_id"] for link in snapshot["source_links"])

    def ref(self, token: str, kinds: set[str] | None = None, *, field: bool = False) -> Ref:
        ref = self.context.refs.get(token)
        if ref is None:
            _invalid("Use an App-issued reference from the current read.", token)
        if ref.document_id != self.context.document_id:
            _invalid("The reference belongs to another document.", token)
        if ref.revision != self.context.base_revision:
            raise DomainError("stale_view", "The reference belongs to another revision.", (token,))
        if kinds is not None and ref.kind not in kinds:
            _invalid("The reference has the wrong target kind.", token)
        if (ref.field is not None) != field:
            _invalid("Field references and item/container references are distinct.", token)
        if ref.kind == "container":
            if ref.child_kind == "task":
                if ref.entity_id is not None and ref.entity_id not in self.base["duties"]:
                    raise DomainError("target_missing", "The duty container no longer exists.", (token,))
            elif ref.child_kind in {"outcome", "requirement"}:
                if ref.entity_id not in self.base["tasks"]:
                    raise DomainError("target_missing", "The task container no longer exists.", (token,))
            elif ref.child_kind not in CONDITION_KINDS | {"duty", "collaborator", "knowledge", "skill"} or ref.entity_id is not None:
                _invalid("Unsupported container type.", token)
        elif ref.kind == "profile":
            if ref.entity_id is not None:
                _invalid("Profile fields do not accept an item ID.", token)
        elif ref.kind not in COLLECTIONS:
            _invalid("Unsupported reference type.", token)
        elif ref.entity_id not in self.base[COLLECTIONS[ref.kind]]:
            raise DomainError("target_missing", "The referenced item no longer exists.", (token,))
        if field and ref.field not in FIELDS.get(ref.kind, ()):
            _invalid("This field cannot be edited by the content operation.", token)
        return ref

    def basis(self, refs: list[str]) -> list[str]:
        result = []
        for token in refs:
            source = self.context.sources.get(token)
            if source is None or source.document_id != self.context.document_id or not source.readable:
                _invalid("A basis must be an issued, readable source in this document.", token)
            if token not in result:
                result.append(token)
        return result

    def stage_basis(self, target: tuple, refs: list[str]) -> None:
        if refs:
            pending = self.pending_basis.setdefault(target, [])
            pending.extend(ref for ref in refs if ref not in pending)

    def new_id(self) -> str:
        identity = self.context.new_id()
        if not isinstance(identity, str) or not identity or identity in self.used_ids:
            _invalid("The App ID allocator returned an invalid or duplicate identity.")
        self.used_ids.add(identity)
        return identity

    def row(self, entity_kind: str, identity: str, **values) -> dict:
        return {"document_id": self.context.document_id, f"{entity_kind}_id": identity, **values}

    def insert(self, rows: list[dict], new_row: dict, id_column: str, group: tuple,
               anchor: str | None) -> None:
        rows.sort(key=lambda row: (row["position"], row[id_column]))
        effective_anchor = self.anchor_tails.get((*group, anchor), anchor)
        index = 0 if effective_anchor is None else next(
            i + 1 for i, row in enumerate(rows) if row[id_column] == effective_anchor)
        rows.insert(index, new_row)
        for position, row in enumerate(rows):
            row["position"] = position
        self.anchor_tails[(*group, anchor)] = new_row[id_column]

    def remove_sources(self, target: tuple) -> None:
        self.value["source_links"] = [link for link in self.value["source_links"]
                                      if _target_from_link(link) != target]

    def finish_sources(self) -> None:
        for target, refs in self.pending_basis.items():
            digest = hashlib.sha256(_json_bytes(_basis_content(self.value, target))).hexdigest()
            existing = [link for link in self.value["source_links"] if _target_from_link(link) == target]
            existing.sort(key=lambda link: (link["position"], link["source_link_id"]))
            by_source = {link["source_ref"]: link for link in existing}
            if any(source_ref not in by_source for source_ref in refs):
                for position, link in enumerate(existing):
                    link["position"] = position
            for source_ref in refs:
                if source_ref in by_source:
                    by_source[source_ref]["basis_digest"] = digest
                else:
                    link = {"document_id": self.context.document_id, "source_link_id": self.new_id(),
                            "source_ref": source_ref, "basis_digest": digest, "position": len(existing),
                            **_source_columns(target)}
                    existing.append(link)
                    by_source[source_ref] = link
                    self.value["source_links"].append(link)


def _create_task(work: _Candidate, args: dict) -> None:
    if sum(len(args[key]) for key in ("outcomes", "requirements", "capabilities")) > MAX_TASK_CHILDREN:
        _invalid("A task can contain at most 128 details and capability references in this probe.")
    container = work.ref(args["container_ref"], {"container"})
    if container.child_kind != "task":
        _invalid("Creating a task requires a task container.")
    anchor = None
    if args["after_ref"] is not None:
        anchor = work.ref(args["after_ref"], {"task"}).entity_id
        if work.base["tasks"][anchor]["duty_id"] != container.entity_id:
            _invalid("The ordering anchor must be in the same task container.", args["after_ref"])
    name, description = _text(args["name"]), _text(args["description"])
    if name is None and description is None:
        _invalid("A task requires a meaningful name or description.")
    basis = work.basis(args["basis_refs"])
    details = [(kind, _text(item["text"], required=True), work.basis(item["basis_refs"]))
               for key, kind in (("outcomes", "outcome"), ("requirements", "requirement"))
               for item in args[key]]
    capabilities = []
    for item in args["capabilities"]:
        identity = work.ref(item["capability_ref"], {"capability"}).entity_id
        if identity in [value[0] for value in capabilities]:
            _invalid("The same capability may be referenced only once.", item["capability_ref"])
        capabilities.append((identity, work.basis(item["basis_refs"])))
    identity = work.new_id()
    row = work.row("task", identity, duty_id=container.entity_id, name=name, description=description, position=0)
    siblings = [task for task in work.value["tasks"].values() if task["duty_id"] == container.entity_id]
    work.insert(siblings, row, "task_id", ("tasks", container.entity_id), anchor)
    work.value["tasks"][identity] = row
    work.stage_basis(("task", identity), basis)
    positions = {"outcome": 0, "requirement": 0}
    for kind, text, refs in details:
        detail_id = work.new_id()
        work.value["details"][detail_id] = work.row("detail", detail_id, task_id=identity,
            kind=kind, text=text, position=positions[kind])
        positions[kind] += 1
        work.stage_basis(("detail", detail_id), refs)
    for position, (capability_id, refs) in enumerate(capabilities):
        work.value["task_capabilities"].append({"document_id": work.context.document_id,
            "task_id": identity, "capability_id": capability_id, "position": position})
        work.stage_basis(("relation", identity, capability_id), refs)


def _plan_revision(work: _Candidate, changes: list[dict]) -> list[tuple]:
    if not 1 <= len(changes) <= MAX_CHANGES:
        _invalid("A revision requires between 1 and 64 content changes.")
    plans, anchors = [], []
    fields, edited, removed, relations = set(), set(), set(), set()
    for change in changes:
        kind = change["kind"]
        if kind == "set_field":
            ref = work.ref(change["target_field_ref"], field=True)
            key = (ref.kind, ref.entity_id, ref.field)
            if key in fields:
                _invalid("The same field cannot be changed twice.", change["target_field_ref"])
            fields.add(key)
            edited.add((ref.kind, ref.entity_id))
            plans.append((kind, ref, _text(change["text"], required=ref.kind in {"detail", "condition"}),
                          work.basis(change["basis_refs"])))
        elif kind in {"remove_task_detail", "remove_condition"}:
            entity_kind = "detail" if kind == "remove_task_detail" else "condition"
            token = change["detail_ref" if entity_kind == "detail" else "condition_ref"]
            ref = work.ref(token, {entity_kind})
            key = (entity_kind, ref.entity_id)
            if key in removed:
                _invalid("The same item cannot be removed twice.", token)
            removed.add(key)
            plans.append((kind, ref))
        elif kind == "set_task_capability":
            task = work.ref(change["task_ref"], {"task"})
            capability = work.ref(change["capability_ref"], {"capability"})
            key = (task.entity_id, capability.entity_id)
            if key in relations:
                _invalid("The same relation cannot be set twice in one correction.")
            relations.add(key)
            if change["mode"] not in {"link", "unlink"} or (change["mode"] == "unlink" and change["basis_refs"]):
                _invalid("Use link or unlink; unlink cannot attach sources.")
            plans.append((kind, *key, change["mode"], work.basis(change["basis_refs"])))
        elif kind in {"add_task_detail", "add_condition"}:
            if kind == "add_task_detail":
                parent = work.ref(change["task_ref"], {"task"}).entity_id
                item_kind = change["detail_kind"]
                if item_kind not in {"outcome", "requirement"}:
                    _invalid("Task details must be outcomes or requirements.")
                ref_kind = "detail"
            else:
                container = work.ref(change["container_ref"], {"container"})
                if container.child_kind not in CONDITION_KINDS:
                    _invalid("A condition requires a supported condition container.")
                parent, item_kind, ref_kind = None, container.child_kind, "condition"
            anchor = None
            if change["after_ref"] is not None:
                anchor = work.ref(change["after_ref"], {ref_kind}).entity_id
                row = work.base[COLLECTIONS[ref_kind]][anchor]
                if row["kind"] != item_kind or (ref_kind == "detail" and row["task_id"] != parent):
                    _invalid("The anchor must be a sibling of the same content kind.", change["after_ref"])
                anchors.append((ref_kind, anchor))
            plans.append((kind, parent, item_kind, anchor, _text(change["text"], required=True),
                          work.basis(change["basis_refs"])))
        else:
            _invalid("This operation supports only the six named content changes.")
    if edited & removed or any(anchor in removed for anchor in anchors):
        _invalid("An item cannot be edited and removed, or be an anchor and removed, in one correction.")
    return plans


def _apply_revision(work: _Candidate, plans: list[tuple]) -> None:
    for kind, *values in plans:
        if kind == "set_field":
            ref, text, basis = values
            row = work.value["profile"] if ref.kind == "profile" else work.value[COLLECTIONS[ref.kind]][ref.entity_id]
            row[ref.field] = text
            work.stage_basis((ref.kind, ref.field if ref.kind == "profile" else ref.entity_id), basis)
        elif kind in {"remove_task_detail", "remove_condition"}:
            ref, = values
            row = work.value[COLLECTIONS[ref.kind]].pop(ref.entity_id)
            siblings = [item for item in work.value[COLLECTIONS[ref.kind]].values()
                        if item["kind"] == row["kind"] and (ref.kind != "detail" or item["task_id"] == row["task_id"])]
            for position, item in enumerate(sorted(siblings, key=lambda item: (item["position"], item[f"{ref.kind}_id"]))):
                item["position"] = position
            work.remove_sources((ref.kind, ref.entity_id))
        elif kind == "set_task_capability":
            task, capability, mode, basis = values
            rows = work.value["task_capabilities"]
            existing = next((row for row in rows if row["task_id"] == task and row["capability_id"] == capability), None)
            if mode == "link":
                if existing is None:
                    siblings = sorted((row for row in rows if row["task_id"] == task),
                                      key=lambda row: (row["position"], row["capability_id"]))
                    for position, row in enumerate(siblings):
                        row["position"] = position
                    rows.append({"document_id": work.context.document_id, "task_id": task,
                                 "capability_id": capability, "position": len(siblings)})
                work.stage_basis(("relation", task, capability), basis)
            elif existing is not None:
                rows.remove(existing)
                siblings = sorted((row for row in rows if row["task_id"] == task),
                                  key=lambda row: (row["position"], row["capability_id"]))
                for position, row in enumerate(siblings):
                    row["position"] = position
                work.remove_sources(("relation", task, capability))
        else:
            parent, item_kind, anchor, text, basis = values
            entity_kind = "detail" if kind == "add_task_detail" else "condition"
            identity = work.new_id()
            row = work.row(entity_kind, identity, kind=item_kind, text=text, position=0)
            if entity_kind == "detail":
                row["task_id"] = parent
            collection = work.value[COLLECTIONS[entity_kind]]
            siblings = [item for item in collection.values() if item["kind"] == item_kind
                        and (entity_kind != "detail" or item["task_id"] == parent)]
            work.insert(siblings, row, f"{entity_kind}_id", (entity_kind, parent, item_kind), anchor)
            collection[identity] = row
            work.stage_basis((entity_kind, identity), basis)


def _row_group(kind: str, row: dict) -> tuple:
    if kind == "task":
        return kind, row["duty_id"], None
    if kind == "detail":
        return kind, row["task_id"], row["kind"]
    if kind in {"capability", "condition"}:
        return kind, None, row["kind"]
    return kind, None, None


def _container_group(ref: Ref) -> tuple:
    child = ref.child_kind
    if child == "task":
        return "task", ref.entity_id, None
    if child in {"outcome", "requirement"}:
        return "detail", ref.entity_id, child
    if child in {"knowledge", "skill"}:
        return "capability", None, child
    if child in CONDITION_KINDS:
        return "condition", None, child
    return child, None, None


def _group_rows(snapshot: dict, group: tuple) -> list[dict]:
    kind = group[0]
    return sorted((row for row in snapshot[COLLECTIONS[kind]].values() if _row_group(kind, row) == group),
                  key=lambda row: (row["position"], row[f"{kind}_id"]))


def _normalize_group(snapshot: dict, group: tuple) -> None:
    for position, row in enumerate(_group_rows(snapshot, group)):
        row["position"] = position


def _anchor(work: _Candidate, token: str | None, group: tuple, *, moving_id: str | None = None) -> str | None:
    if token is None:
        return None
    ref = work.ref(token, {group[0]})
    if ref.entity_id == moving_id:
        _invalid("An item cannot be its own ordering anchor.", token)
    if _row_group(ref.kind, work.base[COLLECTIONS[ref.kind]][ref.entity_id]) != group:
        _invalid("The ordering anchor must be a sibling in the same container and kind.", token)
    return ref.entity_id


def _insert_item(work: _Candidate, item: dict) -> None:
    item_kind = item["kind"]
    kind = {"duty": "duty", "collaborator": "collaborator", "knowledge": "capability", "skill": "capability",
            "outcome": "detail", "requirement": "detail", "condition": "condition"}.get(item_kind)
    if kind is None:
        _invalid("Use the complete create-task operation for tasks, or one of the seven insert kinds.")
    container = work.ref(item["container_ref"], {"container"})
    group = _container_group(container)
    if group[0] != kind or (item_kind != "condition" and container.child_kind != item_kind):
        _invalid("The inserted item kind does not match its container.", item["container_ref"])
    anchor = _anchor(work, item["after_ref"], group)
    values = {key: _text(item[key], required=kind in {"detail", "condition"}) for key in FIELDS[kind]}
    if kind not in {"detail", "condition"} and not any(value is not None for value in values.values()):
        _invalid("An inserted item requires a meaningful name or description/scope.")
    basis = work.basis(item["basis_refs"])
    identity = work.new_id()
    row = work.row(kind, identity, **values, position=0)
    if kind in {"detail", "capability", "condition"}:
        row["kind"] = group[2]
    if kind == "detail":
        row["task_id"] = group[1]
    work.insert(_group_rows(work.value, group), row, f"{kind}_id", group, anchor)
    work.value[COLLECTIONS[kind]][identity] = row
    work.stage_basis((kind, identity), basis)


def _replace_selection(work: _Candidate, args: dict) -> None:
    token = args["selection_ref"]
    selection = work.context.selections.get(token)
    if selection is None:
        _invalid("Use an App-issued selection reference, not a field reference.", token)
    ref = work.ref(selection.field_ref, field=True)
    row = work.base["profile"] if ref.kind == "profile" else work.base[COLLECTIONS[ref.kind]][ref.entity_id]
    if row.get(ref.field) != selection.field_text:
        raise DomainError("stale_view", "The captured field text no longer matches the current field.", (token,))
    try:
        text = replace_utf16(selection.field_text, selection.start_utf16, selection.end_utf16,
                             selection.selected_text, args["replacement_text"])
    except SelectionError as exc:
        raise DomainError("invalid_input", str(exc), (token,)) from exc
    _apply_revision(work, _plan_revision(work, [{"kind": "set_field", "target_field_ref": selection.field_ref,
                                               "text": text, "basis_refs": args["basis_refs"]}]))


def _structural_changes(work: _Candidate, changes: list[dict], task_ids: set[str],
                        duty_ids: set[str] | None = None) -> list[tuple]:
    if not changes:
        return []
    if any(change["kind"] not in {"set_field", "add_task_detail"} for change in changes):
        _invalid("A structural operation permits only related field changes and new task details.")
    plans = _plan_revision(work, changes)
    for kind, *values in plans:
        if kind == "add_task_detail":
            allowed = values[0] in task_ids
        else:
            ref = values[0]
            allowed = ((ref.kind == "task" and ref.entity_id in task_ids)
                or (ref.kind == "detail" and work.base["details"][ref.entity_id]["task_id"] in task_ids)
                or (ref.kind == "duty" and ref.field == "scope_text" and ref.entity_id in (duty_ids or set())))
        if not allowed:
            _invalid("The content change is outside this structural operation's surviving work.")
    return plans


def _delete_item(work: _Candidate, args: dict) -> None:
    ref = work.ref(args["target_ref"], set(COLLECTIONS))
    kind, identity = ref.kind, ref.entity_id
    row = work.base[COLLECTIONS[kind]][identity]
    group = _row_group(kind, row)
    if kind != "duty" and args["content_changes"]:
        _invalid("Only duty deletion can include related surviving task content changes.")
    if kind == "capability" and any(link["capability_id"] == identity for link in work.base["task_capabilities"]):
        raise DomainError("dependent_items", "This capability is still used by tasks; inspect its references before removal.",
                          (args["target_ref"],))
    if kind == "duty":
        moved = _group_rows(work.value, ("task", identity, None))
        plans = _structural_changes(work, args["content_changes"], {task["task_id"] for task in moved})
        _apply_revision(work, plans)
        unassigned = _group_rows(work.value, ("task", None, None))
        # D01 appends preserved tasks in their prior display order; there is no implicit scope inheritance.
        for position, task in enumerate(unassigned + moved):
            task["duty_id"] = None
            task["position"] = position
    elif kind == "task":
        detail_ids = {key for key, detail in work.value["details"].items() if detail["task_id"] == identity}
        for detail_id in detail_ids:
            del work.value["details"][detail_id]
            work.remove_sources(("detail", detail_id))
        relations = [link for link in work.value["task_capabilities"] if link["task_id"] == identity]
        for link in relations:
            work.remove_sources(("relation", identity, link["capability_id"]))
        work.value["task_capabilities"] = [link for link in work.value["task_capabilities"] if link["task_id"] != identity]
    del work.value[COLLECTIONS[kind]][identity]
    work.remove_sources((kind, identity))
    _normalize_group(work.value, group)


def _move_item(work: _Candidate, args: dict) -> None:
    ref = work.ref(args["target_ref"], set(COLLECTIONS))
    destination = work.ref(args["destination_container_ref"], {"container"})
    original = work.base[COLLECTIONS[ref.kind]][ref.entity_id]
    source_group, destination_group = _row_group(ref.kind, original), _container_group(destination)
    if destination_group[0] != ref.kind or (ref.kind != "task" and source_group != destination_group):
        _invalid("Only tasks may change containers; other items can only reorder within their current kind and container.")
    anchor = _anchor(work, args["after_ref"], destination_group, moving_id=ref.entity_id)
    cross_duty = ref.kind == "task" and source_group != destination_group
    if args["content_changes"] and not cross_duty:
        _invalid("A reorder cannot include unrelated content changes.")
    plans = _structural_changes(work, args["content_changes"], {ref.entity_id} if cross_duty else set(),
                                {identity for identity in (source_group[1], destination_group[1]) if identity is not None})
    _apply_revision(work, plans)
    row = work.value[COLLECTIONS[ref.kind]].pop(ref.entity_id)
    _normalize_group(work.value, source_group)
    if ref.kind == "task":
        row["duty_id"] = destination_group[1]
    work.insert(_group_rows(work.value, destination_group), row, f"{ref.kind}_id", destination_group, anchor)
    work.value[COLLECTIONS[ref.kind]][ref.entity_id] = row


def validate_content(snapshot: dict, document_id: str) -> None:
    """Validate final rows, without applying intermediate per-column constraints."""
    for kind, collection in COLLECTIONS.items():
        for identity, row in snapshot[collection].items():
            if row.get(f"{kind}_id") != identity or row.get("document_id", document_id) != document_id:
                _invalid("A content row has inconsistent document or identity.")
            if type(row.get("position")) is not int or row["position"] < 0:
                _invalid("Content ordering positions must be non-negative integers.")
            for name in FIELDS[kind]:
                value = row.get(name)
                if _text(value, required=kind in {"detail", "condition"}) != value:
                    _invalid("Current content must use normalized text.")
            if kind in {"duty", "collaborator", "task", "capability"} and not any(row.get(name) is not None for name in FIELDS[kind]):
                _invalid("An item must retain a meaningful name or description/scope.")
            if kind == "task" and row.get("duty_id") is not None and row["duty_id"] not in snapshot["duties"]:
                _invalid("A task's duty must exist in the same document.")
            if kind == "detail" and (row["task_id"] not in snapshot["tasks"] or row["kind"] not in {"outcome", "requirement"}):
                _invalid("A task detail needs a valid owner and content kind.")
            if kind == "capability" and row["kind"] not in {"knowledge", "skill"}:
                _invalid("A capability must be knowledge or skill.")
            if kind == "condition" and row["kind"] not in CONDITION_KINDS:
                _invalid("Unsupported position-wide condition kind.")
    for name in PROFILE_FIELDS:
        value = snapshot["profile"].get(name)
        if _text(value) != value:
            _invalid("Profile fields must use normalized text.")
    pairs = set()
    for row in snapshot["task_capabilities"]:
        pair = (row["task_id"], row["capability_id"])
        if (pair in pairs or pair[0] not in snapshot["tasks"] or pair[1] not in snapshot["capabilities"]
                or row.get("document_id", document_id) != document_id
                or type(row.get("position")) is not int or row["position"] < 0):
            _invalid("Task capability relations must be unique, ordered and within this document.")
        pairs.add(pair)
    sources, identities = set(), set()
    for link in snapshot["source_links"]:
        target = _target_from_link(link)
        _basis_content(snapshot, target)
        key = (target, link["source_ref"])
        digest = link["basis_digest"]
        if (key in sources or link["source_link_id"] in identities
                or link.get("document_id", document_id) != document_id
                or not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)
                or type(link.get("position")) is not int or link["position"] < 0):
            _invalid("Source links must have unique identities and targets with valid basis digests.")
        sources.add(key)
        identities.add(link["source_link_id"])


def build_candidate(snapshot: dict, command: dict, context: CommandContext) -> dict:
    """Return a separate complete candidate, or raise DomainError without changing input.

    The caller owns persistence and any new revision. A returned value is not saved.
    Sources are append/upsert only when explicitly listed; omitted sources retain
    their previous basis digest. All listed sources bind final target content.
    """
    if snapshot["document_id"] != context.document_id:
        _invalid("The App command context belongs to another document.")
    if snapshot["revision"] != context.base_revision:
        raise DomainError("stale_view", "The App command context has an outdated base revision.")
    if len(_json_bytes(command)) > MAX_REQUEST_BYTES:
        _invalid("The complete request exceeds 1 MiB and cannot be silently split.")
    work = _Candidate(snapshot, context)
    if command["tool"] == "jd_create_task":
        _create_task(work, command["arguments"])
    elif command["tool"] == "jd_revise_work":
        plans = _plan_revision(work, command["arguments"]["changes"])
        _apply_revision(work, plans)
    elif command["tool"] in {"jd_set_text", "jd_set_task_capability"}:
        kind = "set_field" if command["tool"] == "jd_set_text" else "set_task_capability"
        _apply_revision(work, _plan_revision(work, [{"kind": kind, **command["arguments"]}]))
    elif command["tool"] == "jd_insert_item":
        _insert_item(work, command["arguments"]["item"])
    elif command["tool"] == "jd_replace_selection":
        _replace_selection(work, command["arguments"])
    elif command["tool"] == "jd_delete_item":
        _delete_item(work, command["arguments"])
    elif command["tool"] == "jd_move_item":
        _move_item(work, command["arguments"])
    else:
        _invalid("Use one of the eight named JD editing operations.")
    validate_content(work.value, context.document_id)
    work.finish_sources()
    validate_content(work.value, context.document_id)
    return work.value
