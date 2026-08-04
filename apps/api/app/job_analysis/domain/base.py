"""Shared Pydantic policy and scalar contracts for job-analysis domain values."""

from __future__ import annotations

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value cannot be blank")
    return value


NonEmptyText = Annotated[str, Field(min_length=1), AfterValidator(_not_blank)]

# 所有 ID 由 application 配發(§9.1、§12.1);domain 只要求非空字串,不綁 UUID 形狀
# ——§12.3 明令不得做 UUID 形狀掃描,綁死格式等於把同一個誤判搬進 domain。
Identifier = NonEmptyText
TaskId = Identifier


class DomainModel(BaseModel):
    """Strict immutable value object.

    Frozen models block attribute assignment; collection fields use tuples so a
    retained reference cannot mutate nested state.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
