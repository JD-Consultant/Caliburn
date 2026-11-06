"""共用 HTTP 值格式及 Schema 投影；業務文字規則留在各模組。"""

import json
import re
import sys
from typing import Annotated
from uuid import UUID

from pydantic import BeforeValidator, Field

_UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}"
    r"-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
# 投影 Python str.strip／str.isspace 的集合，不使用語意不同的 JS \s。
PYTHON_WHITESPACE_ESCAPES = "".join(
    json.dumps(chr(codepoint), ensure_ascii=True)[1:-1]
    for codepoint in range(sys.maxunicode + 1)
    if chr(codepoint).isspace()
)


def _uuid_text(value: object) -> UUID:
    """HTTP 只接受連字號字串；裸 UUID 另接受 compact、URN 和大括號。"""
    if not isinstance(value, str) or re.fullmatch(_UUID_PATTERN, value) is None:
        raise ValueError("UUID 必須使用含連字號的標準格式")
    return UUID(value)


HttpId = Annotated[
    UUID,
    BeforeValidator(_uuid_text),
    Field(
        json_schema_extra={"pattern": _UUID_PATTERN, "minLength": 36, "maxLength": 36}
    ),
]
