"""Canonical JSON Schema admits input; generated DTOs only convert accepted values."""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticCustomError
from referencing import Registry, Resource

_BASE_URI = "https://caliburn.invalid/contracts/"


def _plain_uuid(value: object) -> bool:
    # JSON Schema 2020-12 §7.3.5: plain RFC UUID, without URN or extra separators.
    return not isinstance(value, str) or str(UUID(value)) == value.lower()


def _formats(value: object) -> set[str]:
    if isinstance(value, list):
        return set().union(*(_formats(item) for item in value))
    if isinstance(value, dict):
        result = set().union(*(_formats(item) for item in value.values()))
        if isinstance(value.get("format"), str):
            result.add(value["format"])
        return result
    return set()


@lru_cache
def _resources() -> tuple[dict[str, str], Registry[Any], FormatChecker]:
    root = files("caliburn.contracts.generated")
    manifest: dict[str, str] = json.loads(
        root.joinpath("schema-manifest.json").read_text(encoding="utf-8")
    )
    resources = []
    required_formats: set[str] = set()
    for path in manifest.values():
        schema = json.loads(root.joinpath(path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        required_formats.update(_formats(schema))
        resources.append((_BASE_URI + path, Resource.from_contents(schema)))
    # Registry has no retriever: package references cannot initiate network or file I/O.
    registry: Registry[Any] = Registry().with_resources(resources)
    checker = FormatChecker()
    checker.checks("uuid", raises=ValueError)(_plain_uuid)
    if required_formats - checker.checkers.keys():
        raise RuntimeError("A canonical contract format checker is unavailable")
    return manifest, registry, checker


@lru_cache
def _validator(model: type[BaseModel]) -> Draft202012Validator:
    manifest, registry, checker = _resources()
    identity = f"{model.__module__}.{model.__name__}"
    if identity not in manifest:
        raise TypeError("Only generated canonical root DTOs admit wire input")
    return Draft202012Validator(
        {"$ref": _BASE_URI + manifest[identity]}, registry=registry, format_checker=checker
    )


def _invalid(
    model: type[BaseModel], kind: str, path: tuple[str | int, ...] = ()
) -> ValidationError:
    # Never retain jsonschema's instance/message/cause: they may contain employee text.
    return ValidationError.from_exception_data(
        model.__name__,
        [
            {
                "type": PydanticCustomError(
                    "canonical_schema",
                    "Input does not satisfy the canonical contract ({kind})",
                    {"kind": kind},
                ),
                "loc": path,
                "input": None,
            }
        ],
    )


def validate_contract[T: BaseModel](model: type[T], value: object) -> T:
    """Validate raw JSON first, then permit only schema-authorized DTO conversions."""
    error = next(_validator(model).iter_errors(value), None)
    if error is not None:
        # Schema path consists of authored names, unlike arbitrary input property names.
        raise _invalid(model, str(error.validator), tuple(error.absolute_schema_path)) from None
    try:
        return model.model_validate(value, strict=False)
    except ValidationError:
        # Canonical input was valid: a DTO mismatch is an internal contract defect.
        raise RuntimeError("Generated DTO could not represent canonical contract input") from None


def parse_contract[T: BaseModel](model: type[T], value: str) -> T:
    """Tool JSON and HTTP objects share the same canonical admission policy."""

    def reject_constant(_value: str) -> None:
        raise ValueError("Non-JSON numeric constant")

    try:
        decoded = json.loads(value, parse_constant=reject_constant)
    except ValueError, RecursionError:
        raise _invalid(model, "json") from None
    return validate_contract(model, decoded)
