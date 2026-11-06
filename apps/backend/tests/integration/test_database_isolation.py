"""測試 schema 不得沿 search_path 讀寫 public 的同名物件。"""

from uuid import uuid4

import pytest
from sqlalchemy import Engine, text


def test_pg_engine_does_not_resolve_public_tables(
    test_database_engine: Engine, request: pytest.FixtureRequest
) -> None:
    """public 既有物件只在明確指定 schema 時可見，不混入本例資料庫。"""
    sentinel = f"workspace_isolation_{uuid4().hex}"
    with test_database_engine.begin() as connection:
        connection.execute(text(f'CREATE TABLE public."{sentinel}" (id integer)'))
    try:
        pg_engine: Engine = request.getfixturevalue("pg_engine")
        with pg_engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT to_regclass(:name)"), {"name": f"public.{sentinel}"}
                )
                is not None
            )
            assert (
                connection.scalar(text("SELECT to_regclass(:name)"), {"name": sentinel})
                is None
            )
    finally:
        with test_database_engine.begin() as connection:
            connection.execute(text(f'DROP TABLE public."{sentinel}"'))
