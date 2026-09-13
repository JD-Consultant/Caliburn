"""New Windows processes use one configured Memory dataset; synthetic only."""
import os
import sys

from psycopg import Connection
import pytest

from test_configured_host_native import fresh_database, worker, schema_identity, CONNECTION
from test_storage_postgres import engine


pytestmark = pytest.mark.skipif(sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit synthetic PostgreSQL and Windows opt-in required")


def test_real_configured_memory_is_corrected_drained_and_read_by_a_new_host(fresh_database):
    database, directory = fresh_database
    with worker("initialize", database, directory) as (process, setup, _):
        process.communicate(timeout=15)
        assert process.returncode == 0 and setup["phase"] == "ready"
    objects = schema_identity(database)
    with worker("memory-write", database, directory) as (process, first, _):
        process.communicate(timeout=15)
        assert process.returncode == 0 and first["synthetic_calls"] == 2
        assert first["closed"] and first["drain_kept_resources"] and first["setup_calls"] == 0
    with worker("memory-read", database, directory) as (process, second, _):
        process.communicate(timeout=15)
        assert process.returncode == 0 and second["synthetic_calls"] == 0
        assert second["closed"] and second["drain_kept_resources"] and second["setup_calls"] == 0
        assert second["dataset_id"] == first["dataset_id"] == setup["dataset_id"]
        assert second["document"] == first["document"]
        assert second["memory_revision"] == first["memory_revision"] == 2
        assert second["jd_revision"] == first["jd_revision"] == 1
        assert second["provider_calls"] == first["provider_calls"] == 0
    assert schema_identity(database) == objects, "ordinary open must not replace schema objects"
    with Connection.connect(**{**CONNECTION, "dbname": database}) as conn:
        assert conn.execute("SELECT count(*) FROM jd_runtime.q019_memory_publication_receipt").fetchone() == (2,)
        assert conn.execute("SELECT count(*) FROM jd_runtime.store").fetchone() == (6,)
        assert conn.execute("SELECT count(*) FROM public.jd_operation").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM public.jd_revision").fetchone() == (1,)
    print(f"Memory native host evidence: {directory}; DB={database}; Memory2/JD1/receipt2/artifact6")
