"""直接核對路由發布的 OpenAPI，避免測試保有另一份 HTTP shape。"""

from functools import cache
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from pydantic import BaseModel

from caliburn.bootstrap import create_app
from caliburn.settings import Settings


@cache
def _components() -> dict[str, Any]:
    return create_app(Settings()).openapi()["components"]


def http_schema(model: type[BaseModel]) -> dict[str, Any]:
    components = _components()
    assert model.__name__ in components["schemas"]
    return {"$ref": f"#/components/schemas/{model.__name__}", "components": components}


def http_validator(model: type[BaseModel]) -> Draft202012Validator:
    return Draft202012Validator(http_schema(model), format_checker=FormatChecker())
