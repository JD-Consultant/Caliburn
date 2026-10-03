"""Configure the official checkpoint serializer; payload allowlists belong to callers."""

from collections.abc import Iterable

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer


def create_graph_serializer(*, allowed_types: Iterable[type[object]] = ()) -> JsonPlusSerializer:
    """Allow only the supplied custom types in addition to framework-safe types.

    Callers must enumerate nested dataclasses and enums as well as the outer
    payload. UUID and frozenset already belong to the framework's safe set.
    Checkpoint 4.2.0 returns raw dicts/values for blocked constructors, and may
    return None when reconstruction fails; it does not always raise. Validate
    the restored payload's nested types before executing a prepared command.

    Native tuples decode as lists even when tuple is allowlisted. Use a State
    shape that accepts this framework behavior; this factory adds no codec,
    implicit domain registry, or pickle fallback. Legacy JSON custom
    constructors remain disabled independently of the msgpack allowlist.
    """
    return JsonPlusSerializer(
        pickle_fallback=False,
        allowed_json_modules=None,
        allowed_msgpack_modules=tuple(allowed_types),
    )
