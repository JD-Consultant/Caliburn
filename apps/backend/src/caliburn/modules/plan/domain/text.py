"""Plan 正文的工程容量與可保存字元；不正規化原文。"""

from caliburn.modules.plan.domain.errors import BodyEditError, InvalidPlanTextError

MAX_BODY_CHARACTERS = 16_000


def validate_body(body: str | None) -> str | None:
    """檢查完整正文並回傳原值；None、空白與換行各自保留。"""
    if body is None:
        return None
    if len(body) > MAX_BODY_CHARACTERS:
        raise BodyEditError("patch_limit_exceeded", "Plan body exceeds the edit limit")
    require_storable_text(body)
    return body


def require_storable_text(text: str) -> None:
    if "\x00" in text or any("\ud800" <= character <= "\udfff" for character in text):
        raise InvalidPlanTextError("Plan text contains an unsupported character")
