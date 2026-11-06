"""Value Object 的嚴格驗證、值比較與不可變設定。"""

from pydantic import BaseModel, ConfigDict


class BaseValueObject(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        strict=True,
        extra="forbid",
        validate_default=True,
    )
