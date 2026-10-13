"""共用 HTTP 值政策；保留原文及跨語言可精確表示的數字。"""

import re
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StrictStr

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
NONBLANK_PATTERN = (
    r"^[^\u0000]*[^\u0000\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680"
    r"\u2000-\u200a\u2028\u2029\u202f\u205f\u3000][^\u0000]*$"
)


def _plain_uuid(value: object) -> object:
    if isinstance(value, UUID) or isinstance(value, str) and re.fullmatch(UUID_PATTERN, value):
        return value
    raise ValueError("Expected a hyphenated UUID")


def _json_number(value: object) -> object:
    if type(value) not in (int, float):
        raise ValueError("Expected a JSON number")
    return value


type WireUuid = Annotated[
    UUID,
    BeforeValidator(_plain_uuid),
    Field(json_schema_extra={"pattern": UUID_PATTERN, "minLength": 36, "maxLength": 36}),
]
type PositiveInteger = Annotated[
    int, Field(ge=1, le=9007199254740991), BeforeValidator(_json_number)
]
type NonnegativeInteger = Annotated[
    int, Field(ge=0, le=9007199254740991), BeforeValidator(_json_number)
]
type NonemptyText = Annotated[StrictStr, Field(min_length=1)]
type NonblankText = Annotated[StrictStr, Field(min_length=1, pattern=NONBLANK_PATTERN)]
type DisplayName = Annotated[NonblankText, Field(max_length=200)]


class HttpModel(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)
