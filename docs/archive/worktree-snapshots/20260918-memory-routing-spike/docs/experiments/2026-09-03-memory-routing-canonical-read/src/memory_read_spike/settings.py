"""Fail-closed settings for the disposable PostgreSQL experiment."""

from __future__ import annotations

import os
from urllib.parse import unquote, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, model_validator


_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


class DatabaseIdentityError(RuntimeError):
    def __init__(self, *, expected: str, actual: str) -> None:
        super().__init__("disposable database identity mismatch")
        self.expected = expected
        self.actual = actual
        self.public_message = "disposable database identity mismatch"


def _parts(database_url: str):
    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        raise ValueError("spike database URL must be PostgreSQL")
    if parsed.hostname is None:
        raise ValueError("spike database URL must include a host")
    database = unquote(parsed.path.lstrip("/"))
    if not database or "/" in database:
        raise ValueError("spike database URL must name exactly one database")
    return parsed, database


def _endpoint_identity(database_url: str) -> tuple[str, int, str]:
    parsed, database = _parts(database_url)
    return (parsed.hostname.lower(), parsed.port or 5432, database)


class SpikeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    database_url: str = Field(min_length=1)
    expected_database: str = Field(min_length=1)
    production_database_url: str | None = None

    @model_validator(mode="after")
    def validate_disposable_identity(self) -> SpikeSettings:
        parsed, database = _parts(self.database_url)
        if parsed.hostname.lower() not in _LOOPBACK_HOSTS:
            raise ValueError("spike database host must be loopback")
        if database != self.expected_database:
            raise ValueError("URL database must equal expected database")
        if "memory_routing_spike" not in database:
            raise ValueError("database name must contain memory_routing_spike")
        if self.production_database_url and (
            _endpoint_identity(self.database_url)
            == _endpoint_identity(self.production_database_url)
        ):
            raise ValueError("spike database must differ from application database")
        return self

    @property
    def connection_string(self) -> str:
        parsed, _ = _parts(self.database_url)
        scheme = "postgresql"
        return urlunsplit(
            (scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment)
        )

    @classmethod
    def from_environment(cls) -> SpikeSettings:
        return cls.model_validate(
            {
                "database_url": os.environ.get(
                    "MEMORY_ROUTING_SPIKE_DATABASE_URL"
                ),
                "expected_database": os.environ.get(
                    "MEMORY_ROUTING_SPIKE_EXPECTED_DATABASE"
                ),
                "production_database_url": os.environ.get("DATABASE_URL"),
            }
        )
