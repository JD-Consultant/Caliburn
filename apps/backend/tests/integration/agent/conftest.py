"""只管理本例 checkpoint schema，不套用業務 migrations。"""

from collections.abc import Iterator
from uuid import uuid4

import pytest
from psycopg.conninfo import make_conninfo
from sqlalchemy import Engine, text


@pytest.fixture(autouse=True)
def isolate_external_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


@pytest.fixture
def checkpoint_conninfo(test_database_engine: Engine) -> Iterator[str]:
    schema = f"agent_checkpoint_{uuid4().hex}"
    with test_database_engine.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    url = test_database_engine.url.set(drivername="postgresql")
    try:
        yield make_conninfo(
            url.render_as_string(hide_password=False),
            options=f"-csearch_path={schema}",
        )
    finally:
        with test_database_engine.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
