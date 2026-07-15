"""Reusable scalar contracts and naming rules."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated

from pydantic import AfterValidator, AwareDatetime, Field


def _not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("value cannot be blank")
    return value


def _utc_only(value: datetime) -> datetime:
    if value.utcoffset() != timedelta(0):
        raise ValueError("timestamp must use UTC offset +00:00")
    return value


NonEmptyText = Annotated[str, Field(min_length=1), AfterValidator(_not_blank)]
ShortText = Annotated[
    str,
    Field(min_length=1, max_length=512),
    AfterValidator(_not_blank),
]
StableName = Annotated[
    str,
    Field(pattern=r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$", min_length=1, max_length=128),
]
SemVer = Annotated[
    str,
    Field(
        pattern=(
            r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
            r"(?:-[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?"
            r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
        )
    ),
]
Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
Locale = Annotated[str, Field(pattern=r"^[A-Za-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")]
ReferenceUrn = Annotated[
    str,
    Field(min_length=3, max_length=512),
    AfterValidator(_not_blank),
]
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_utc_only)]
