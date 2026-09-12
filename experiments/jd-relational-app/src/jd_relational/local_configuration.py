"""Private, explicit local configuration. No environment or file discovery.

Pydantic validates this internal Python boundary; it is not an HTTP contract.
Only the protected configuration-file adapter receives encoded secret content.
"""
import base64
import json
import secrets
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator
import sqlalchemy as sa


class ConfigurationError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


class LocalConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, hide_input_in_errors=True)
    format_version: int = Field(ge=1, le=1, repr=False)
    phase: Literal["initialization_pending", "initializing", "ready", "maintenance"] = Field(repr=False)
    installation_id: str = Field(repr=False)
    dataset_id: str = Field(repr=False)
    signing_key: str = Field(repr=False)
    host: Literal["127.0.0.1", "localhost"] = Field(repr=False)
    port: int = Field(ge=1, le=65535, repr=False)
    database: str = Field(min_length=1, max_length=63, repr=False)
    username: str = Field(min_length=1, max_length=63, repr=False)
    password: str = Field(min_length=1, max_length=8192, repr=False)
    checkpoint_schema: str = Field(pattern=r"^[a-z][a-z0-9_]{0,62}$", repr=False)
    api_port: int = Field(ge=1, le=65535, repr=False)
    allowed_origins: tuple[str, ...] = Field(min_length=1, max_length=8, repr=False)

    @field_validator("installation_id", "dataset_id")
    @classmethod
    def uuid_text(cls, value):
        if str(UUID(value)) != value:
            raise ValueError("invalid_identity")
        return value

    @field_validator("signing_key")
    @classmethod
    def key_bytes(cls, value):
        raw = base64.b64decode(value, validate=True)
        if len(raw) != 32 or base64.b64encode(raw).decode("ascii") != value:
            raise ValueError("invalid_key")
        return value

    @field_validator("database", "username", "password")
    @classmethod
    def connection_text(cls, value):
        if "\x00" in value:
            raise ValueError("invalid_connection_text")
        value.encode("utf-8")
        return value

    @field_validator("checkpoint_schema")
    @classmethod
    def separate_schema(cls, value):
        if value in {"public", "information_schema"} or value.startswith("pg_"):
            raise ValueError("invalid_checkpoint_schema")
        return value

    @field_validator("allowed_origins")
    @classmethod
    def local_origins(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("duplicate_origin")
        for value in values:
            url = urlsplit(value)
            port = url.port
            canonical = f"{url.scheme}://{url.hostname}" + (f":{port}" if port is not None else "")
            if (url.scheme not in {"http", "https"} or url.hostname not in {"127.0.0.1", "localhost"}
                    or value != canonical or port is not None and not 1 <= port <= 65535):
                raise ValueError("invalid_origin")
        return values

    def signing_key_bytes(self):
        return base64.b64decode(self.signing_key, validate=True)

    def database_url(self):
        return sa.URL.create("postgresql+psycopg", username=self.username, password=self.password,
            host=self.host, port=self.port, database=self.database)


def parse_configuration(raw: bytes) -> LocalConfiguration:
    def unique(pairs):
        result = {}
        for key, item in pairs:
            if key in result:
                raise ValueError()
            result[key] = item
        return result
    def constant(_):
        raise ValueError()
    try:
        if type(raw) is not bytes or not 1 <= len(raw) <= 65536:
            raise ValueError()
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=unique, parse_constant=constant)
        if type(value) is not dict or type(value.get("allowed_origins")) is not list:
            raise ValueError()
        value["allowed_origins"] = tuple(value["allowed_origins"])
        return LocalConfiguration.model_validate(value, strict=True)
    except Exception:
        raise ConfigurationError("configuration_invalid") from None


def encode_configuration(value: LocalConfiguration) -> bytes:
    try:
        if type(value) is not LocalConfiguration:
            raise ValueError()
        raw = json.dumps(value.model_dump(mode="json"), ensure_ascii=False,
            sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
        parse_configuration(raw)  # Reject unsafe model_construct/copy mutations.
        return raw
    except Exception:
        raise ConfigurationError("configuration_invalid") from None


def new_configuration(**connection) -> LocalConfiguration:
    """Only an explicit initializer calls this; ordinary open never creates IDs."""
    try:
        value = LocalConfiguration(format_version=1, phase="initialization_pending",
            installation_id=str(uuid4()), dataset_id=str(uuid4()),
            signing_key=base64.b64encode(secrets.token_bytes(32)).decode("ascii"), **connection)
        encode_configuration(value)
        return value
    except Exception:
        raise ConfigurationError("configuration_invalid") from None


def configuration_phase(value: LocalConfiguration, next_phase: str) -> LocalConfiguration:
    if (value.phase, next_phase) not in {("initialization_pending", "initializing"), ("initializing", "ready")}:
        raise ConfigurationError("configuration_phase_conflict")
    return parse_configuration(json.dumps({**value.model_dump(mode="json"),
        "phase": next_phase}, ensure_ascii=False).encode("utf-8"))
