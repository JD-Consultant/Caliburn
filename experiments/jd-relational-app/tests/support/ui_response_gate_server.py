"""Explicit synthetic Windows/PG/browser helper; never a production entry point.

prepare/initialize/serve run separately. Only prepare creates a NEW test database;
ordinary serve uses the existing real DPAPI file and real Windows host ownership.
arm/release are local file controls, not HTTP routes. No provider is configured.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import socket
import sys
from threading import Event, Lock, Thread
from time import monotonic

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parents[1]
sys.path.insert(0, str(APP / "src"))
if __package__:
    from .ui_response_gate import ResponseGate, canonical_uuid, write_report
else:
    from ui_response_gate import ResponseGate, canonical_uuid, write_report

ORIGIN = "http://127.0.0.1:3002"
FIXTURE = dict(host="127.0.0.1", port=55436, dbname="caliburn_jd_relational_test",
    user="jd_test", password="jd-local-test-only", connect_timeout=5)


def directory(value):
    target = Path(value).resolve()
    if target.parent != ROOT / ".research-tmp" or not re.fullmatch(r"jd-ui-gate-[0-9a-f]{32}", target.name):
        raise ValueError("invalid_probe_directory")
    return target


def valid_port(port):
    return type(port) is int and 1024 <= port <= 65535 and port not in {3001, 3002, 55436}


def bound_socket(port):
    bound = socket.socket()
    try:
        bound.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        bound.bind(("127.0.0.1", port))
        return bound
    except BaseException:
        bound.close()
        raise


def prepare(target, port):
    from psycopg import Connection, sql
    if not valid_port(port):
        raise ValueError("invalid_probe_port")
    with bound_socket(port):
        pass
    target.mkdir(exist_ok=False)
    database = "caliburn_jd_setup_test_" + target.name.removeprefix("jd-ui-gate-")
    write_report(target / "fixture.json", {"database": database, "port": 55436, "api_port": port, "ui_origin": ORIGIN})
    with Connection.connect(**FIXTURE, autocommit=True) as connection:
        actual = connection.execute("SELECT current_database(),current_user,current_setting('server_version_num')::integer").fetchone()
        if actual != ("caliburn_jd_relational_test", "jd_test", 180006):
            raise ValueError("invalid_fixture_database")
        connection.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(sql.Identifier(database), sql.Identifier("jd_test")))
    write_report(target / "prepare.finished.json", {"pid": os.getpid(), "database": database, "created": True})


def manifest(target):
    value = json.loads((target / "fixture.json").read_text(encoding="utf-8"))
    expected = "caliburn_jd_setup_test_" + target.name.removeprefix("jd-ui-gate-")
    if (type(value) is not dict or set(value) != {"database", "port", "api_port", "ui_origin"}
        or value["database"] != expected or value["port"] != 55436 or value["ui_origin"] != ORIGIN
        or not valid_port(value["api_port"])):
        raise ValueError("invalid_probe_manifest")
    return value


def initialize(target):
    from jd_relational.configured_host import initialize_configuration
    value = manifest(target)
    settings = initialize_configuration(fixture_file(target, value), connection=dict(
        host="127.0.0.1", port=55436, database=value["database"], username="jd_test", password="jd-local-test-only",
        checkpoint_schema="jd_runtime", api_port=value["api_port"],
        allowed_origins=(ORIGIN, f"http://127.0.0.1:{value['api_port']}")))
    write_report(target / "initialize.finished.json", {"pid": os.getpid(), "phase": settings.phase,
        "installation_id": settings.installation_id, "dataset_id": settings.dataset_id,
        "api_port": settings.api_port, "database": settings.database})


def arm(target, document):
    manifest(target)
    if not canonical_uuid(document) or any((target / name).exists() for name in
            ("gate.claimed.json", "gate.release.request", "stop.request")):
        raise ValueError("invalid_gate_arm")
    with (target / "gate.arm.json").open("x", encoding="utf-8") as stream:
        json.dump({"format": 1, "document_id": document}, stream)


def release(target):
    manifest(target)
    armed = json.loads((target / "gate.arm.json").read_text(encoding="utf-8"))
    committed = json.loads((target / "gate.committed.json").read_text(encoding="utf-8"))
    held = json.loads((target / "gate.held.json").read_text(encoding="utf-8"))
    if (committed.get("committed") is not True or committed.get("document_id") != armed.get("document_id")
        or not canonical_uuid(committed.get("operation_id")) or not canonical_uuid(committed.get("result_revision_id"))
        or held.get("document_id") != armed.get("document_id") or held.get("response_start_forwarded") is not False
        or (target / "gate.finished.json").exists()):
        raise ValueError("gate_not_committed_and_held")
    with (target / "gate.release.request").open("x", encoding="utf-8"):
        pass


def check_settings(settings, value):
    if (settings.host != "127.0.0.1" or settings.port != 55436 or settings.database != value["database"]
        or settings.username != "jd_test" or settings.password != "jd-local-test-only"
        or settings.checkpoint_schema != "jd_runtime" or settings.api_port != value["api_port"]
        or settings.allowed_origins != (ORIGIN, f"http://127.0.0.1:{value['api_port']}")):
        raise ValueError("invalid_probe_configuration")


def fixture_file(target, value):
    from jd_relational.config_file import ConfigFile
    from jd_relational.local_configuration import parse_configuration

    class FixtureConfigFile(ConfigFile):
        # Both initialization and ordinary host open may reread existing config.
        # Check EVERY native read before bytes can select a DB; preserve the
        # real file's generation/change checks rather than freeze its contents.
        def read(self):
            raw = super().read()
            check_settings(parse_configuration(raw), value)
            return raw

    return FixtureConfigFile(target / "host.v1.dpapi")


def serve(target, timeout):
    import uvicorn
    from jd_relational.managed_app import open_managed_app, unavailable_consultant
    value = manifest(target)
    if (target / "stop.request").exists():
        raise ValueError("probe_already_stopped")
    gate = ResponseGate(None, target, timeout=timeout)  # Validate before acquiring OS/DB resources.
    file = fixture_file(target, value)
    file.read()  # Scope check BEFORE host can connect; subsequent reads check too.
    managed = open_managed_app(file, consultant=unavailable_consultant())
    settings = managed.opened.settings
    try:
        check_settings(settings, value)
    except ValueError:
        managed.close()
        raise
    gate.app = managed.app
    original_execute = managed.opened.host.runtime.storage.execute
    operations, observations, evidence_lock = [], [], Lock()

    def execute(intent):
        # Count real entries without delaying, replacing or retrying the writer.
        with evidence_lock:
            operations.append(str(intent.operation_id))
        result = original_execute(intent)
        gate.record_execution(intent.document_id, intent.operation_id, result)
        with evidence_lock:
            observations.append({"operation_id": str(intent.operation_id), "confirmed": result.confirmed,
                "result_revision_id": str(result.receipt.result_revision_id) if result.receipt and result.receipt.result_revision_id else None})
            try:
                write_report(target / "writer.observations.json", {"operations": operations.copy(), "observations": observations.copy()})
            except Exception:
                # Evidence failure must not change the original mutation result.
                gate._evidence_failed = True
        return result

    managed.opened.host.runtime.storage.execute = execute
    done = Event(); control = {"reason": "server_exit"}; started = monotonic()
    try:
        with bound_socket(managed.port) as bound:
            server = uvicorn.Server(uvicorn.Config(gate, host="127.0.0.1", port=managed.port,
                workers=1, reload=False, access_log=False, log_level="critical", log_config=None,
                timeout_graceful_shutdown=timeout + 5))

            def control_loop():
                deadline = monotonic() + 45
                while not server.started:
                    if done.wait(0.05): return
                    if monotonic() >= deadline:
                        control["reason"] = "startup_timeout"; server.should_exit = True; return
                write_report(target / "serve.ready.json", {"pid": os.getpid(), "parent_pid": os.getppid(),
                    "status": "ready", "api_origin": f"http://127.0.0.1:{managed.port}", "ui_origin": ORIGIN,
                    "dataset_id": settings.dataset_id, "installation_id": settings.installation_id,
                    "database": settings.database, "provider_enabled": False, "gate_timeout": timeout})
                while not done.wait(0.1):
                    if (target / "stop.request").exists() or monotonic() - started >= 3600:
                        control["reason"] = "requested" if (target / "stop.request").exists() else "probe_deadline"
                        server.should_exit = True; return

            def controls():
                try:
                    control_loop()
                except Exception:
                    control["reason"] = "control_failed"
                    server.should_exit = True

            Thread(target=controls, daemon=True, name="synthetic-ui-gate-controls").start()
            server.run(sockets=[bound])
    finally:
        done.set(); closed = managed.close()
        write_report(target / "serve.finished.json", {"pid": os.getpid(), "closed": closed,
            "saver_connection_closed": managed.opened.host.saver_connection.closed, "reason": control["reason"],
            "operations": operations, "observations": observations})
    if not server.started or not closed:
        raise ValueError("probe_shutdown_unconfirmed")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "initialize", "serve", "arm", "release"))
    parser.add_argument("directory", type=directory)
    parser.add_argument("--api-port", type=int, default=8767)
    parser.add_argument("--gate-timeout", type=float, default=60)
    parser.add_argument("--document-id")
    args = parser.parse_args()
    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise ValueError("explicit_test_scope_required")
    if args.mode == "prepare": prepare(args.directory, args.api_port)
    elif args.mode == "arm": arm(args.directory, args.document_id)
    elif args.mode == "release": release(args.directory)
    else:
        write_report(args.directory / f"{args.mode}.boot.json", {"pid": os.getpid(), "parent_pid": os.getppid(),
            "started_at": datetime.now(timezone.utc).isoformat()})
        if args.mode == "initialize": initialize(args.directory)
        else: serve(args.directory, args.gate_timeout)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        print("ui_gate_probe_failed", file=sys.stderr, flush=True)
        sys.exit(1)
