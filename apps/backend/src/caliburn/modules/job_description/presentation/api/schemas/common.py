"""JD HTTP 值規則；輸入接受集合與 OpenAPI 同步投影。"""

import re
from typing import Annotated, Any, ClassVar, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    WithJsonSchema,
    model_validator,
)

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.input_text import (
    require_storable_text,
)
from caliburn.shared.presentation.api.values import PYTHON_WHITESPACE_ESCAPES, HttpId

_MAX_SAFE_INTEGER = 9007199254740991
_UNSTORABLE_ESCAPES = r"\u0000\uD800-\uDFFF"
_STORABLE_PATTERN = f"^[^{_UNSTORABLE_ESCAPES}]*$"
_NONBLANK_PATTERN = (
    f"^[{PYTHON_WHITESPACE_ESCAPES}]*"
    f"[^{_UNSTORABLE_ESCAPES}{PYTHON_WHITESPACE_ESCAPES}]"
    f"[^{_UNSTORABLE_ESCAPES}]*$"
)
# JSON Schema 不清洗字串；只限制去除外圍空白後的1–255個碼點。
_NAME_PATTERN = (
    f"^[{PYTHON_WHITESPACE_ESCAPES}]*"
    f"[^{_UNSTORABLE_ESCAPES}{PYTHON_WHITESPACE_ESCAPES}]"
    f"(?:[^{_UNSTORABLE_ESCAPES}]{{0,253}}"
    f"[^{_UNSTORABLE_ESCAPES}{PYTHON_WHITESPACE_ESCAPES}])?"
    f"[{PYTHON_WHITESPACE_ESCAPES}]*(?![\\s\\S])"
)


def _bounded_decimal_pattern(maximum: int, *, allow_zero: bool = False) -> str:
    """將整數上限完整投影至 ECMAScript pattern，避免 JS 先轉 Number。"""
    digits = str(maximum)
    alternatives = [rf"[1-9][0-9]{{0,{len(digits) - 2}}}"]
    for index, digit in enumerate(digits):
        lower = 1 if index == 0 else 0
        upper = int(digit) - 1
        if upper >= lower:
            choice = str(lower) if lower == upper else f"[{lower}-{upper}]"
            alternatives.append(
                digits[:index] + choice + rf"[0-9]{{{len(digits) - index - 1}}}"
            )
    alternatives.append(digits)
    if allow_zero:
        alternatives.append("0")
    # 明定字串結尾，避免 ECMAScript $ 接受最後一個換行前。
    return "^(?:" + "|".join(alternatives) + r")(?![\s\S])"


_VERSION_QUERY_PATTERN = _bounded_decimal_pattern(_MAX_SAFE_INTEGER)
_PAGE_SIZE_PATTERN = _bounded_decimal_pattern(_MAX_SAFE_INTEGER, allow_zero=True)


def _mathematical_integer(value: object) -> int:
    if type(value) is int:
        return value
    if type(value) is float and value.is_integer():
        return int(value)
    raise ValueError("必須提供 JSON 數學整數")


def _version_query(value: object) -> int:
    if (
        not isinstance(value, str)
        or re.fullmatch(_VERSION_QUERY_PATTERN, value) is None
    ):
        raise ValueError("版本必須是安全正整數十進位字串")
    return int(value)


def _page_size_query(value: object) -> int:
    if not isinstance(value, str) or re.fullmatch(_PAGE_SIZE_PATTERN, value) is None:
        raise ValueError("分頁大小必須是安全非負整數十進位字串")
    return int(value)


def _storable_text(value: str) -> str:
    try:
        return require_storable_text(value)
    except InvalidJobDescriptionInputError as error:
        raise ValueError("文字必須可保存為 UTF-8 Text") from error


def _nonblank_text(value: str) -> str:
    if not value.strip():
        raise ValueError("文字不可全為空白")
    return value


ExpectedVersion = Annotated[
    int,
    Field(strict=True, ge=1, le=_MAX_SAFE_INTEGER),
    BeforeValidator(_mathematical_integer),
]
CompetencyLevelInput = Annotated[
    int, Field(strict=True, ge=1, le=6), BeforeValidator(_mathematical_integer)
]
ExpectedVersionQuery = Annotated[
    int,
    BeforeValidator(_version_query),
    WithJsonSchema({"type": "string", "pattern": _VERSION_QUERY_PATTERN}),
]
HistoryPageSizeQuery = Annotated[
    int,
    BeforeValidator(_page_size_query),
    WithJsonSchema({"type": "string", "pattern": _PAGE_SIZE_PATTERN}),
]
StorableText = Annotated[
    str,
    AfterValidator(_storable_text),
    Field(strict=True, json_schema_extra={"pattern": _STORABLE_PATTERN}),
]
NonBlankText = Annotated[
    StorableText,
    AfterValidator(_nonblank_text),
    Field(min_length=1, json_schema_extra={"pattern": _NONBLANK_PATTERN}),
]
NameInput = Annotated[
    NonBlankText,
    AfterValidator(str.strip),
    Field(max_length=255, json_schema_extra={"pattern": _NAME_PATTERN}),
    WithJsonSchema({"type": "string", "pattern": _NAME_PATTERN}),
]
CorrelationIdInput = Annotated[NonBlankText, Field(max_length=200)]


class RequestModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ResponseModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", from_attributes=True)


class WriteRequest(RequestModel):
    expected_version: ExpectedVersion
    correlation_id: CorrelationIdInput | None = None


class PlacementRequest(RequestModel):
    """在自身集合排序；省略 before_id 或 null 表示移至集合末尾。"""

    before_id: HttpId | None = None


def _patch_json_schema(schema: dict[str, Any], model: type[PatchRequest]) -> None:
    schema["anyOf"] = [{"required": [field]} for field in model.patch_fields]
    for field in model.nonnullable_patch_fields:
        schema["properties"][field].pop("default", None)


class PatchRequest(WriteRequest):
    """同時投影空 patch 與省略但不可為 null 的欄位規則。"""

    model_config = ConfigDict(json_schema_extra=_patch_json_schema)
    patch_fields: ClassVar[tuple[str, ...]] = ()
    nonnullable_patch_fields: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _require_patch(self) -> Self:
        if not self.model_fields_set.intersection(self.patch_fields):
            raise ValueError("至少須提供一個可修改欄位")
        for field in self.nonnullable_patch_fields:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError("必要欄位不可清空")
        return self
