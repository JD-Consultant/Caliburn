"""JD 寫入入口共用的 UTF-8 Text 可表示性檢查，不改寫文字。"""

from typing import Annotated

from pydantic import AfterValidator

from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)


def require_storable_text(value: str) -> str:
    """可供 DTO 與具名文字參數共用；Domain 內容語意仍由 Domain 驗證。"""
    if "\x00" in value:
        raise InvalidJobDescriptionInputError("JD 文字不可含 NUL")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeEncodeError as error:
        raise InvalidJobDescriptionInputError("JD 文字必須可編碼為 UTF-8") from error
    return value


StorableText = Annotated[str, AfterValidator(require_storable_text)]
