"""Transform only named locator fields, never user text, titles or native history."""

import json
from collections.abc import Callable

from pydantic import JsonValue, TypeAdapter

from caliburn.workflows.jd_model_references import JdModelReferences

_REF_FIELDS = frozenset(
    {
        "read_ref",
        "parent_read_ref",
        "neighbor_read_ref",
        "detail_read_ref",
        "capability_read_ref",
        "citation_ref",
        "area_read_ref",
        "task_read_ref",
    }
)


def map_jd_reference_fields(value: JsonValue, transform: Callable[[str], str]) -> JsonValue:
    if isinstance(value, list):
        return [map_jd_reference_fields(item, transform) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, JsonValue] = {}
    for key, item in value.items():
        if key in _REF_FIELDS and isinstance(item, str) and item != "未歸屬":
            result[key] = transform(item)
        elif key == "task_read_refs" and isinstance(item, list):
            result[key] = [transform(ref) if isinstance(ref, str) else ref for ref in item]
        else:
            result[key] = map_jd_reference_fields(item, transform)
    return result


def _references(value: JsonValue) -> set[str]:
    references: set[str] = set()

    def collect(ref: str) -> str:
        references.add(ref)
        return ref

    map_jd_reference_fields(value, collect)
    return references


async def resolve_jd_arguments(references: JdModelReferences, arguments: str) -> str:
    payload: JsonValue = TypeAdapter(JsonValue).validate_json(arguments)
    resolved = await references.resolve(_references(payload))
    return json.dumps(map_jd_reference_fields(payload, resolved.__getitem__), ensure_ascii=False)


async def encode_jd_payload(references: JdModelReferences, payload: JsonValue) -> str:
    assigned = await references.assign(_references(payload))
    return json.dumps(
        map_jd_reference_fields(payload, assigned.__getitem__),
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
