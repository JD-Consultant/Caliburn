"""Where the application keeps its data: a PostgreSQL target and one namespace.

Owned by the database adapter so adapters never import the top-level settings; `Settings`
only aggregates this value with the other sections.
"""

import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from psycopg import ProgrammingError
from psycopg.conninfo import conninfo_to_dict
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


def require_isolated_test_database(dsn: str, *, environment: Mapping[str, str]) -> None:
    """Validate an explicit libpq test target without opening a connection.

    Test/evaluation entry points call this before constructing any database consumer.
    The caller still owns schema isolation and cleanup. Normal App connections do not
    use this policy. Error text deliberately excludes connection strings and secrets.
    """
    try:
        info = conninfo_to_dict(dsn)
    except ProgrammingError, ValueError:
        raise ValueError("Use a valid explicit PostgreSQL test connection string") from None
    if any(key in info for key in ("hostaddr", "service", "servicefile")) or any(
        environment.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE")
    ):
        raise ValueError("Test database target cannot be redirected by hostaddr or service")
    database_name = info.get("dbname")
    if (
        info.get("host") not in {"localhost", "127.0.0.1", "::1"}
        or not isinstance(database_name, str)
        or not database_name.endswith("_test")
    ):
        raise ValueError("Use an explicit loopback database whose name ends in _test")
