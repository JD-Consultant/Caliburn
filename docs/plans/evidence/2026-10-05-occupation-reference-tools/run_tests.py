"""Run isolated tests against the identified local test PostgreSQL; never print credentials."""

import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import quote


def main():
    root = Path(__file__).resolve().parents[4]
    info = json.loads(subprocess.check_output(
        ["docker", "inspect", "caliburn-jd-docker-test-postgres-1"], text=True
    ))[0]
    ports = info["NetworkSettings"]["Ports"]["5432/tcp"]
    if ports != [{"HostIp": "127.0.0.1", "HostPort": "55441"}]:
        raise RuntimeError("Unexpected test database binding")
    values = dict(item.split("=", 1) for item in info["Config"]["Env"] if "=" in item)
    # This named test database is provisioned separately from POSTGRES_DB.
    database = "caliburn_docker_test"
    user = quote(values["POSTGRES_USER"], safe="")
    password = quote(values["POSTGRES_PASSWORD"], safe="")
    env = os.environ.copy()
    env["CALIBURN_TEST_DATABASE_URL"] = (
        f"postgresql://{user}:{password}@127.0.0.1:55441/{database}"
    )
    result = subprocess.run(
        [str(root / "apps/api/.venv/Scripts/python.exe"), "-m", "pytest",
         "-p", "no:cacheprovider", *sys.argv[1:]], cwd=root, env=env,
    )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
