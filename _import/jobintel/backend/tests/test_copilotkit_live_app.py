import os
import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.skipif(not os.getenv("TEST_DATABASE_URL"),
                                reason="live app lifespan needs Postgres for AsyncPostgresSaver")


def test_live_app_lifespan_mounts_endpoint():
    # 讓 live app 的 PG checkpointer 指向測試 DB
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]
    from app.copilotkit_live_app import app
    with TestClient(app) as c:
        assert c.get("/healthz").json()["status"] == "ok"
        paths = [getattr(r, "path", "") for r in app.routes]
        assert any("/copilotkit" in p for p in paths), f"no /copilotkit route in {paths}"
