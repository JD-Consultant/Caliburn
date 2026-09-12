"""Freeze an edit after trusted admission materials are supplied, without a gate.

This consumes App-verified Ref/Source/Selection materials; it does not authenticate
tokens, prove current database existence, allocate IDs, or acquire writer ownership.
The caller retains the trusted new_id callable; binding never invokes it. Domain
validation and the persistent operation owner remain separate responsibilities.
"""

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
import hashlib
import json
from types import MappingProxyType
from typing import Literal
from uuid import UUID

from .domain import COLLECTIONS, CONDITION_KINDS, FIELDS, CommandContext, Ref, Source
from .selection import Selection, replace_utf16
from .transport import TransportError, manual_command


_REF_ROLES = {
    "target_field_ref": "field", "container_ref": "container",
    "destination_container_ref": "container", "after_ref": "item",
    "target_ref": "item", "task_ref": "task", "detail_ref": "detail",
    "capability_ref": "capability", "condition_ref": "condition",
}
_TEXT_KEYS = frozenset({"name", "description", "scope_text", "text", "replacement_text"})


class IntentValidationError(ValueError):
    """Safe rejection before producing a bound intent; contains no caller values."""

    def __init__(self):
        self.code = "invalid_input"
        super().__init__(self.code)


@dataclass(frozen=True, slots=True)
class BoundEdit:
    document_id: str
    operation_id: UUID
    base_revision_id: UUID
    origin: Literal["manual", "ai"]
    ai_run_id: str | None
    request_digest: str
    _command_json: str = field(repr=False)
    context: CommandContext = field(repr=False)

    @property
    def command(self) -> dict:
        """Each consumer gets its own command; nested mutations cannot change intent."""
        return json.loads(self._command_json)


def _require(condition: bool) -> None:
    if not condition:
        raise IntentValidationError()


def _identity(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _freeze_context(context: CommandContext) -> CommandContext:
    _require(isinstance(context, CommandContext))
    _require(_identity(context.document_id) and isinstance(context.base_revision, str))
    _require(callable(context.new_id))
    copied = []
    for mapping, expected in ((context.refs, Ref), (context.sources, Source), (context.selections, Selection)):
        _require(isinstance(mapping, Mapping))
        values = {}
        for token, value in mapping.items():
            _require(_identity(token) and isinstance(value, expected))
            if expected is Ref:
                _require(all(isinstance(item, str) for item in (value.document_id, value.revision, value.kind)))
                _require(all(item is None or isinstance(item, str)
                             for item in (value.entity_id, value.field, value.child_kind)))
            elif expected is Source:
                _require(isinstance(value.document_id, str) and type(value.readable) is bool)
            else:
                _require(all(isinstance(item, str) for item in (value.field_ref, value.field_text, value.selected_text)))
                _require(type(value.start_utf16) is int and type(value.end_utf16) is int)
            # Copy frozen dataclass values too: no object owned by the caller is retained.
            values[token] = expected(**asdict(value))
        copied.append(MappingProxyType(values))
    return CommandContext(context.document_id, context.base_revision, copied[0], copied[1],
                          context.new_id, copied[2])


def _issued_ref(token: str, role: str, context: CommandContext) -> dict:
    ref = context.refs.get(token)
    _require(ref is not None and ref.document_id == context.document_id and ref.revision == context.base_revision)
    if role == "field":
        _require(ref.field in FIELDS.get(ref.kind, ()) and ref.child_kind is None)
        _require(ref.entity_id is None if ref.kind == "profile" else _identity(ref.entity_id))
    elif role == "container":
        _require(ref.kind == "container" and ref.field is None)
        if ref.child_kind == "task":
            _require(ref.entity_id is None or _identity(ref.entity_id))
        elif ref.child_kind in {"outcome", "requirement"}:
            _require(_identity(ref.entity_id))
        else:
            _require(ref.child_kind in CONDITION_KINDS | {"duty", "collaborator", "knowledge", "skill"}
                     and ref.entity_id is None)
    else:
        _require(ref.kind in COLLECTIONS and ref.field is None and ref.child_kind is None and _identity(ref.entity_id))
        _require(role == "item" or ref.kind == role)
    return asdict(ref)


def _selection_identity(token: str, context: CommandContext) -> dict:
    selected = context.selections.get(token)
    _require(selected is not None)
    field_ref = _issued_ref(selected.field_ref, "field", context)
    # Validate only the captured range. The latest saved field is checked by domain.
    replace_utf16(selected.field_text, selected.start_utf16, selected.end_utf16,
                  selected.selected_text, selected.selected_text)
    return {
        "field_ref": field_ref,
        "start_utf16": selected.start_utf16, "end_utf16": selected.end_utf16,
        "field_text_digest": hashlib.sha256(selected.field_text.encode("utf-8")).hexdigest(),
        "selected_text_digest": hashlib.sha256(selected.selected_text.encode("utf-8")).hexdigest(),
    }


def _semantic_command(value: object, context: CommandContext) -> object:
    """Walk the eight validated tool shapes using their fixed, known reference keys."""
    if isinstance(value, list):
        return [_semantic_command(item, context) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key in _REF_ROLES:
            result[key] = None if item is None else _issued_ref(item, _REF_ROLES[key], context)
        elif key == "selection_ref":
            result[key] = _selection_identity(item, context)
        elif key == "basis_refs":
            for token in item:
                source = context.sources.get(token)
                _require(source is not None and source.document_id == context.document_id and source.readable)
            # These are the source owner's opaque identities, never JD issued aliases.
            result[key] = list(item)
        elif key in _TEXT_KEYS and isinstance(item, str):
            # Preserve meaningful whitespace and code points; canonical writes use LF.
            result[key] = item.replace("\r\n", "\n").replace("\r", "\n")
        else:
            result[key] = _semantic_command(item, context)
    return result


def bind_edit(operation_id: UUID, origin: Literal["manual", "ai"], ai_run_id: str | None,
              command: dict, context: CommandContext) -> BoundEdit:
    """Freeze App-trusted inputs; this function does not perform admission or saving.

    Operation identity is an idempotency key, not part of the request digest. Issued
    JD aliases are replaced only in digest material; the frozen command keeps its
    aliases and its matching frozen context for domain execution. Unused refs and
    ID-generator state cannot change the digest.
    """
    try:
        _require(isinstance(operation_id, UUID))
        _require(origin in {"manual", "ai"})
        _require((origin == "ai") == (ai_run_id is not None))
        _require(ai_run_id is None or _identity(ai_run_id))
        validated = manual_command(command)  # Exactly one standard generated input validation.
        frozen_context = _freeze_context(context)
        base = UUID(frozen_context.base_revision)
        material = {
            "document_id": frozen_context.document_id,
            "origin": origin, "ai_run_id": ai_run_id,
            "base_revision_id": str(base),
            "command": _semantic_command(validated, frozen_context),
        }
        canonical = json.dumps(material, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        serialized = json.dumps(validated, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        return BoundEdit(frozen_context.document_id, operation_id, base, origin, ai_run_id,
                         digest, serialized, frozen_context)
    except (TransportError, ValueError, TypeError, AttributeError, KeyError, RecursionError):
        raise IntentValidationError() from None
