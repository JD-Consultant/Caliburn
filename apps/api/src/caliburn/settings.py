"""Explicit target settings; never load a legacy dotenv or infer its database."""

import os
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


@dataclass(frozen=True, slots=True)
class Settings:
    database: DatabaseSettings | None = None

    @classmethod
    def from_environment(cls) -> Settings:
        database_url = os.environ.get("CALIBURN_DATABASE_URL")
        if not database_url:
            return cls()
        return cls(
            database=DatabaseSettings(
                url=database_url,
                schema=os.environ.get("CALIBURN_DATABASE_SCHEMA", "caliburn"),
            )
        )
