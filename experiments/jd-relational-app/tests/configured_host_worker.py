"""Synthetic-only native configured host; no provider or real user settings."""

import os
from pathlib import Path
import re
import socket
import sys
from threading import Thread

import uvicorn

from host_recovery_worker import child_graph, write
from jd_relational.config_file import ConfigFile, ConfigFileError
from jd_relational.configured_host import initialize_configuration
from jd_relational.local_configuration import parse_configuration
from jd_relational.managed_app import open_managed_app


ORIGIN = "http://127.0.0.1:3007"


def connection(database):
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
    return dict(host="127.0.0.1", port=55436, database=database, username="jd_test",
        password="jd-local-test-only", checkpoint_schema="jd_runtime", api_port=port,
        allowed_origins=(ORIGIN, f"http://127.0.0.1:{port}"))


def main(mode, path, database, report):
    assert sys.platform == "win32" and os.environ.get("JD_RELATIONAL_TEST_DB") == "1"
    assert re.fullmatch(r"caliburn_jd_setup_test_[0-9a-f]{32}", database)
    root = Path(__file__).resolve().parents[3]
    assert path.resolve().is_relative_to(root / ".research-tmp")
    assert report.resolve().is_relative_to(root / ".research-tmp")
    common = {"pid": os.getpid(), "parent_pid": os.getppid()}
    write(report.with_suffix(".boot.json"), common)
    file = ConfigFile(path)
    if mode in {"initialize", "initialize_lose_ack"}:
        lost = []
        if mode == "initialize_lose_ack":
            original = ConfigFile.replace
            def lose_ready(self, plaintext, *, expected):
                original(self, plaintext, expected=expected)
                if parse_configuration(plaintext).phase == "ready":
                    lost.append(True)
                    raise ConfigFileError("configuration_write_unconfirmed")
            ConfigFile.replace = lose_ready
        try:
            value = initialize_configuration(file, connection=connection(database))
            status = "ready"
        except ConfigFileError as error:
            if mode != "initialize_lose_ack" or error.code != "configuration_write_unconfirmed" or lost != [True]:
                raise
            value, status = parse_configuration(file.read()), "unconfirmed"
        write(report, {**common, "status": status, "phase": value.phase,
            "installation_id": value.installation_id, "dataset_id": value.dataset_id,
            "api_port": value.api_port, "database": value.database})
        return

    # These hooks are test assertions, not alternate setup or recovery paths.
    # A successful ordinary open must never reach either initialization entry.
    from jd_relational import storage_setup, configured_host
    setup_calls = []
    def forbidden_setup(*args, **kwargs):
        setup_calls.append(True)
        raise AssertionError("ordinary_open_must_not_initialize")
    storage_setup.check_empty_database = forbidden_setup
    storage_setup.setup_database = forbidden_setup
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore
    from caliburn_memory.publication import PublicationStore
    from alembic import command
    PostgresSaver.setup = forbidden_setup
    PostgresStore.setup = forbidden_setup
    PublicationStore.setup = forbidden_setup
    command.upgrade = forbidden_setup
    if mode == "reject_open":
        configured_host.open_manual_host = forbidden_setup
        try:
            open_managed_app(file, consultant=child_graph())
        except Exception as error:
            code = getattr(error, "code", None)
            assert code in {"configuration_missing", "configuration_initialization_required", "configuration_maintenance"}
            assert setup_calls == []
            write(report, {**common, "status": "rejected", "code": code, "resource_calls": 0})
            return
        raise AssertionError("incomplete_configuration_was_opened")

    if mode in {"memory-write", "memory-read"}:
        from memory_host_journey import child, run
        consultant, replies, calls, stores = child()
        managed = open_managed_app(file, consultant=consultant)
        assert managed.opened.settings.database == database and managed.opened.settings.port == 55436
        value = run(managed, mode, path.with_name("memory-fixture.json"), replies, calls, stores)
        assert setup_calls == []
        write(report, {**common, **value, "setup_calls": 0})
        return
    assert mode == "serve"
    managed = open_managed_app(file, consultant=child_graph())
    configured = managed.opened
    assert configured.settings.database == database and configured.settings.port == 55436
    host = configured.host
    operations = []
    original_execute = host.runtime.storage.execute
    def execute(intent):
        operations.append(str(intent.operation_id))
        return original_execute(intent)
    host.runtime.storage.execute = execute

    original_startup = host.runtime.finish_startup
    def startup(*args, **kwargs):
        recovered = original_startup(*args, **kwargs)
        write(report, {**common, "phase": configured.settings.phase,
            "installation_id": configured.settings.installation_id,
            "dataset_id": configured.settings.dataset_id, "port": configured.settings.api_port,
            "recovered": recovered, "setup_calls": len(setup_calls)})
        return recovered
    host.runtime.finish_startup = startup
    close_results = []
    original_close = host.runtime.close
    def close(*args, **kwargs):
        result = original_close(*args, **kwargs)
        close_results.append(result)
        return result
    host.runtime.close = close
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", configured.settings.api_port))
        server = uvicorn.Server(uvicorn.Config(managed.app, host="127.0.0.1", port=managed.port,
            reload=False, workers=1, access_log=False, log_level="warning", log_config=None))
        def controls():
            for line in sys.stdin:
                assert line.strip() == "STOP"
                break
            server.should_exit = True
        Thread(target=controls, daemon=True).start()
        server.run(sockets=[bound])
    assert setup_calls == [] and close_results == [True] and host.saver_connection.closed and host.store_connection.closed
    write(report.with_suffix(".finished.json"), {**common, "operations": operations,
        "setup_calls": 0, "closed": True})


if __name__ == "__main__":
    mode, path, database, report = sys.argv[1:]
    try:
        main(mode, Path(path), database, Path(report))
    except BaseException as error:
        # Reports and stderr never contain configuration bytes, DSNs or raw
        # driver exceptions, including assertion-rendered local variables.
        code = getattr(error, "code", None)
        safe = code if isinstance(code, str) and re.fullmatch(r"[a-z_]{1,64}", code) else "native_probe_failed"
        write(Path(report).with_suffix(".failure.json"), {"code": safe})
        print(safe, file=sys.stderr, flush=True)
        sys.exit(1)
