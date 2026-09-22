"""Explicit initialization of compose.test.yaml's synthetic database only."""

from pathlib import Path

from alembic import command
from alembic.config import Config
import sqlalchemy as sa

from jd_relational.storage.schema import JD_CONTENT_TABLE_NAMES, JD_TABLE_NAMES


def main():
    # These are public disposable-test credentials, never product configuration.
    url = sa.URL.create("postgresql+psycopg", username="jd_test",
                        password="jd-local-test-only", host="127.0.0.1", port=55436,
                        database="caliburn_jd_relational_test")
    engine = sa.create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    try:
        with engine.begin() as connection:
            identity = connection.execute(sa.text(
                "SELECT current_database(), current_user, current_setting('server_version_num')::integer"
            )).one()
            if identity != ("caliburn_jd_relational_test", "jd_test", 180006):
                raise RuntimeError("Unexpected test database identity/version; no migration applied.")
            tables = set(sa.inspect(connection).get_table_names(schema="public"))
            # Fresh, or already at a known head of this chain. Listing the
            # earlier head explicitly is what lets 0002 upgrade an existing test
            # database; anything not on this list is not this database and gets
            # no migration.
            if tables not in (set(),
                              JD_CONTENT_TABLE_NAMES | {"alembic_version"},
                              JD_TABLE_NAMES | {"alembic_version"}):
                raise RuntimeError("Unexpected existing tables; no migration applied.")
            config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            actual = set(sa.inspect(connection).get_table_names(schema="public"))
            if actual != JD_TABLE_NAMES | {"alembic_version"}:
                raise RuntimeError("Initialization did not produce the expected tables; rolling back.")
            revision = connection.execute(sa.text("SELECT version_num FROM alembic_version")).scalar_one()
        print(f"PostgreSQL 18.6: 13 JD content tables + 1 runtime admission table "
              f"+ Alembic metadata; migration {revision} committed.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
