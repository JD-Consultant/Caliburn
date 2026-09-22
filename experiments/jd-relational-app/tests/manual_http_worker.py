"""Test-only real host + loopback HTTP; stdin controls are never API routes."""

from contextlib import asynccontextmanager
import json
import os
from pathlib import Path
import socket
import sys
from threading import Event, Thread
from uuid import uuid4

from langchain_core.messages import HumanMessage
from starlette.concurrency import run_in_threadpool
import uvicorn

from host_recovery_worker import DATABASE_URL, SCHEMA, child_graph, write
from jd_relational.change_reads import ChangeReadService
from jd_relational.host_runtime import open_manual_host
from jd_relational.catalog_api import CatalogServices, create_catalog_app
from jd_relational.catalog_service import CatalogService
from jd_relational.manual_service import ManualService
from jd_relational.reads import ReadService
from jd_relational.references import ReferenceCodec
from jd_relational.storage.history import HistoryReader


ORIGIN = "http://127.0.0.1:3007"
DATASET = "a59866fa-28fa-4d53-a6ee-002fb3a3b814"


def main(mode, installation, manifest, report):
    assert sys.platform == "win32" and os.environ.get("JD_RELATIONAL_TEST_DB") == "1"
    common = {"pid": os.getpid(), "parent_pid": os.getppid()}
    write(report.with_suffix(".boot.json"), common)
    # Assignment is deliberately inside this dedicated process's main thread.
    host = open_manual_host(installation, DATABASE_URL, checkpoint_schema=SCHEMA, consultant=child_graph())
    codec = ReferenceCodec(b"synthetic-manual-http-key-only-0000", DATASET)
    history = HistoryReader(host.engine)
    release, calls, document = Event(), [], None
    if mode == "resume":
        release.set()
    original_execute = host.runtime.storage.execute

    def execute(intent):
        calls.append(str(intent.operation_id))
        write(report.with_suffix(".entered.json"), {"operations": calls.copy()})
        assert release.wait(40), "Harness must release its own HTTP writer"
        return original_execute(intent)

    host.runtime.storage.execute = execute
    original_create = host.runtime.create_document

    def create_document(key, title):
        result = original_create(key, title)
        if mode == "catalog":
            write(report.with_suffix(".catalog-created.json"), {"document": result, "request_key": str(key)})
            assert release.wait(40), "Harness must release its own catalog response"
        return result

    host.runtime.create_document = create_document

    @asynccontextmanager
    async def resources():
        nonlocal document
        recovered = await run_in_threadpool(host.runtime.finish_startup, timeout=20)
        if mode == "resume":
            document = json.loads(manifest.read_text(encoding="utf-8"))["document"]
        else:
            assert mode in {"new", "catalog"}
            document = host.runtime.storage.create_document(uuid4(), "合成完整 HTTP 共同編輯")
            host.graph.update_state({"configurable": {"thread_id": document}},
                {"messages": [HumanMessage(content="原始員工說明\n只能追加與更正，不撤回原話", id="http-original")]},
                as_node="consultant")
            write(manifest, {"document": document})
        service = ManualService(host.runtime, history, codec, wait_timeout=2)
        write(report, {**common, "document": document, "port": bound.getsockname()[1], "recovered": recovered})
        try:
            yield CatalogServices(ReadService(host.runtime.storage, history, codec), ChangeReadService(history, codec),
                                  service, CatalogService(host.runtime, DATASET))
        finally:
            closed = await run_in_threadpool(host.close, timeout=10)
            assert closed

    app = create_catalog_app(resources, allowed_origins=(ORIGIN,))
    bound = socket.socket()
    bound.bind(("127.0.0.1", 0))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=bound.getsockname()[1],
        reload=False, workers=1, access_log=False, log_level="warning", log_config=None))

    def controls():
        for line in sys.stdin:
            command = line.strip()
            if command == "RELEASE":
                release.set()
            elif command == "STOP":
                break
            else:
                raise AssertionError("Unexpected test-only command")
        release.set()
        server.should_exit = True

    Thread(target=controls, daemon=True, name="test-http-controls").start()
    try:
        server.run(sockets=[bound])
    finally:
        bound.close()
    # Open a read-only connection after the owned host drained for immutable
    # evidence; no writes or false acknowledgement are performed by this probe.
    from sqlalchemy import create_engine
    from jd_relational.storage.service import JdReader
    engine = create_engine(DATABASE_URL, hide_parameters=True)
    try:
        current = JdReader(engine).read_current(document)
        write(report.with_suffix(".finished.json"), {**common, "operations": calls,
            "snapshot": current.snapshot, "revision_number": current.revision_number})
    finally:
        engine.dispose()


if __name__ == "__main__":
    mode, installation, manifest, report = sys.argv[1:]
    try:
        main(mode, installation, Path(manifest), Path(report))
    except BaseException as error:
        write(Path(report).with_suffix(".failure.json"), {"code": getattr(error, "code", type(error).__name__)})
        raise
