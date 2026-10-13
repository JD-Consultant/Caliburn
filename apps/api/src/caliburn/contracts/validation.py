"""工具先依正式 JSON Schema 驗證，再轉成生成型別。"""

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator
from pydantic import BaseModel, ValidationError
from pydantic_core import PydanticCustomError
from referencing import Registry, Resource

_BASE_URI = "https://caliburn.invalid/contracts/"


@lru_cache
def _resources() -> tuple[dict[str, str], Registry[Any]]:
    root = files("caliburn.contracts.generated")
    manifest: dict[str, str] = json.loads(
        root.joinpath("schema-manifest.json").read_text(encoding="utf-8")
    )
    resources = []
    for path in manifest.values():
        schema = json.loads(root.joinpath(path).read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        resources.append((_BASE_URI + path, Resource.from_contents(schema)))
    # 只登錄包內資源，參照不能啟動網路或檔案讀取。
    registry: Registry[Any] = Registry().with_resources(resources)
    return manifest, registry


@lru_cache
def _validator(model: type[BaseModel]) -> Draft202012Validator:
    manifest, registry = _resources()
    identity = f"{model.__module__}.{model.__name__}"
    if identity not in manifest:
        raise TypeError("Only generated canonical root DTOs admit wire input")
    return Draft202012Validator({"$ref": _BASE_URI + manifest[identity]}, registry=registry)


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
    """模型參數僅接受標準 JSON，再依工具契約准入。"""

    def reject_constant(_value: str) -> None:
        raise ValueError("Non-JSON numeric constant")

    try:
        decoded = json.loads(value, parse_constant=reject_constant)
    except ValueError, RecursionError:
        raise _invalid(model, "json") from None
    return validate_contract(model, decoded)
