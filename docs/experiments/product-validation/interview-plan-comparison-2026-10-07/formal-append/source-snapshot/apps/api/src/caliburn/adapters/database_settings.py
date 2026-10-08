"""Where the application keeps its data: a PostgreSQL target and one namespace.

Owned by the database adapter so adapters never import the top-level settings; `Settings`
only aggregates this value with the other sections.
"""

import re
from dataclasses import dataclass, field

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True, slots=True)
class DatabaseSettings:
    url: str = field(repr=False)
    schema: str = "caliburn"

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", self.schema):
            raise ValueError("Database schema must be a lowercase PostgreSQL identifier")
        if make_url(self.url).drivername not in {"postgresql", "postgresql+psycopg"}:
            raise ValueError("The target database must use PostgreSQL with psycopg")

    @property
    def sqlalchemy_url(self) -> URL:
        return make_url(self.url).set(drivername="postgresql+psycopg")
