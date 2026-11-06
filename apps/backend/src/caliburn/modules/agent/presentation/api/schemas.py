"""Agent HTTP 請求格式；不改寫輸入正文。"""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from caliburn.shared.presentation.api.values import HttpId


def _utf8_text(value: str) -> str:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise ValueError("輸入必須能編碼為 UTF-8") from error
    return value


class SubmitTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_id: HttpId
    input: Annotated[str, AfterValidator(_utf8_text)] = Field(
        strict=True, json_schema_extra={"pattern": r"^[^\uD800-\uDFFF]*$"}
    )
