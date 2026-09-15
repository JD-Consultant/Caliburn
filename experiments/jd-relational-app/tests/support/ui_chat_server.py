"""Single synthetic browser journey, real managed host/SQL/Saver/Agent/SDK.

Only OpenRouter HTTP is replaced with httpx.MockTransport. No real credential,
provider network, runtime replacement, generic launcher, retry or response gate.
Reuse the established fixed fixture's prepare/initialize/scope/DPAPI checks.
The fresh jd-ui-gate-<hex> directory and database belong only to this journey.
"""

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))
if __package__:
    from .ui_response_gate_server import (ORIGIN, bound_socket, check_settings, directory,
        fixture_file, initialize, manifest, prepare, valid_port, write_report)
else:
    from ui_response_gate_server import (ORIGIN, bound_socket, check_settings, directory,
        fixture_file, initialize, manifest, prepare, valid_port, write_report)

FIRST_REPLY = "已依合成訪談建立設備檢查任務，分列檢查記錄、異常交接及先確認隔離的要求。請核對是否符合你的工作。"
SECOND_REPLY = "收到，這輪先保留訪談補充，沒有修改 JD。還有哪些低頻但重要的工作需要補充？"
KEY = "synthetic-ai-runtime-not-a-key"


class Evidence:
    """Metadata only; never write employee text, tool arguments, refs or keys."""

    def __init__(self, target):
        self.target = target
        self._lock = Lock()
        self._next_request = 0
        self._requests, self._writes, self._routes = [], [], {}
        self._http = []
        self._bodies = []
        self._failed = False

    def _snapshot(self):
        return {"format": 1, "model_request_count": len(self._requests),
            "model_requests": [dict(item) for item in self._requests],
            "closed_model_bodies": sum(body.is_closed for body in self._bodies),
            "writer_execute_count": len(self._writes), "writes": [dict(item) for item in self._writes],
            "http_counts": dict(self._routes), "http_observations": [dict(item) for item in self._http],
            "evidence_failed": self._failed,
            "provider_network": False}

    def _save(self):
        try:
            write_report(self.target / "chat.observations.json", self._snapshot())
        except Exception:
            self._failed = True

    def snapshot(self):
        with self._lock:
            return self._snapshot()

    def begin_request(self, payload_bytes):
        with self._lock:
            position = self._next_request
            self._next_request += 1
            item = {"request_number": self._next_request, "payload_bytes": payload_bytes,
                "tool": None, "response": "pending"}
            self._requests.append(item)
            self._save()
            return position, item

    def end_request(self, item, *, tool=None, failed=False):
        with self._lock:
            item["tool"] = tool
            item["response"] = "fixture_rejected" if failed else "synthetic_complete_reply"
            self._save()

    def body(self, body):
        with self._lock:
            self._bodies.append(body)
            self._save()

    def flush(self):
        with self._lock:
            self._save()

    def write(self, intent, result):
        receipt = result.receipt
        with self._lock:
            self._writes.append({"document_id": intent.document_id, "origin": intent.origin,
                "run_id": intent.ai_run_id, "operation_id": str(intent.operation_id),
                "confirmed": result.confirmed, "status": result.status,
                "result_revision_id": str(receipt.result_revision_id) if receipt and receipt.result_revision_id else None})
            self._save()

    async def routes(self, app, scope, receive, send):
        if scope["type"] != "http":
            return await app(scope, receive, send)
        started = monotonic()
        path, method = scope.get("path", ""), scope.get("method", "")
        if method not in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}:
            method = "OTHER"
        route = "other"
        match = re.fullmatch(r"/api/documents/[0-9a-f-]{36}/chat/(runs|messages)(?:/[0-9a-f-]{36})?(?:/(cancel|recover))?", path)
        read_match = re.fullmatch(r"/api/documents/[0-9a-f-]{36}/jd/(read|state)", path)
        if match:
            route = "chat_" + (match[2] or match[1])
        elif read_match:
            route = "jd_" + read_match[1]
        # Keep only a comparison bit. Header/path/query/body values never enter evidence.
        origins = [value for name, value in scope.get("headers", []) if name.lower() == b"origin"]
        with self._lock:
            key = method + " " + route
            self._routes[key] = self._routes.get(key, 0) + 1
            row = {"ordinal": len(self._http) + 1, "method": method, "route": route,
                "status": None, "response_start_forwarded": False, "response_body_end_forwarded": False,
                "cors_origin_matches": False, "elapsed_ms": None}
            self._http.append(row)
            self._save()

        async def observe_send(message):
            is_start = message["type"] == "http.response.start"
            is_end = message["type"] == "http.response.body" and not message.get("more_body", False)
            if is_start:
                cors = [value for name, value in message.get("headers", [])
                    if name.lower() == b"access-control-allow-origin"]
                with self._lock:
                    row["status"] = message["status"]
                    row["cors_origin_matches"] = len(origins) == 1 and len(cors) == 1 and origins[0] == cors[0]
                    self._save()
            # Do not hold the evidence lock over an ASGI send or change its errors.
            await send(message)
            if is_start or is_end:
                with self._lock:
                    if is_start:
                        row["response_start_forwarded"] = True
                    if is_end:
                        row["response_body_end_forwarded"] = True
                    self._save()

        try:
            await app(scope, receive, observe_send)
        finally:
            with self._lock:
                row["elapsed_ms"] = round((monotonic() - started) * 1000, 3)
                self._save()


def _cite(created, payload):
    """Quote this turn's own saved interview as the basis, as a consultant should.

    The reference is the one the App issued for this turn; nothing here invents
    or edits a token. Without it the JD carries no source links at all and the
    page's "where did this come from" markers never appear.

    Driving the model directly, without the App's consultant context, means
    there is no notice to quote. That path simply does not cite, and the
    journey checks for real source links afterwards rather than assuming.
    """
    from support.openrouter_replies import system_blocks
    from test_conversation_sources_postgres import _source_notice
    name, arguments = created
    blocks = system_blocks(payload)
    if not blocks:
        return name, arguments
    source_ref = _source_notice({"system": blocks})["source_ref"]
    arguments["basis_refs"] = [source_ref]
    for detail in [*arguments.get("outcomes", []), *arguments.get("requirements", [])]:
        detail["basis_refs"] = [source_ref]
    return name, arguments


@contextmanager
def offline_model(evidence):
    """Pinned native SDK/adapter; exactly four synthetic model responses.

    Reuse the proven fixture's read/create replies. The
    dynamic container ref comes from the actual jd_read result, never a guess.
    The fixed script is test data, not an LLM quality or decision-making test.
    """
    import httpx
    import pytest
    from langsmith import tracing_context
    from jd_relational.consultant_model import OPENROUTER_HEADERS, create_consultant_model
    from support.openrouter_replies import reply
    from test_ai_runtime_postgres import _read, _create

    bodies = []
    prefix = uuid4().hex

    def receive(request):
        position, event = evidence.begin_request(len(request.content))
        try:
            if position >= 4:
                raise ValueError("synthetic_plan_exhausted")
            if request.url.host != "openrouter.ai" or request.headers.get("authorization") != f"Bearer {KEY}":
                raise ValueError("synthetic_transport_scope_mismatch")
            payload = json.loads(request.content)
            if (len(payload.get("tools", [])) != 10
                    or not all(tool.get("function", {}).get("strict") is True for tool in payload["tools"])
                    or payload.get("parallel_tool_calls") is not False
                    or payload.get("provider") != {"only": ["OpenAI"], "order": ["OpenAI"],
                        "allow_fallbacks": False, "require_parameters": True}):
                raise ValueError("synthetic_tool_contract_mismatch")
            try:
                name, arguments = (_read(payload) if position == 0
                                   else _cite(_create(payload), payload)
                                   if position == 1 else (None, None))
            except (AssertionError, IndexError, KeyError, TypeError, ValueError) as error:
                raise ValueError("synthetic_plan_input_invalid") from error
            body = reply(f"ui_{prefix}_{position + 1}", name, arguments,
                         text=FIRST_REPLY if position == 2 else SECOND_REPLY)
            response = httpx.Response(200, json=body, request=request)
            bodies.append(response)
            evidence.body(response)
            evidence.end_request(event, tool=name)
            return response
        except BaseException:
            evidence.end_request(event, failed=True)
            raise

    with pytest.MonkeyPatch.context() as patch, tracing_context(enabled=False):
        patch.setenv("LANGSMITH_TRACING", "false")
        patch.setenv("LANGCHAIN_TRACING_V2", "false")
        with httpx.Client(transport=httpx.MockTransport(receive), trust_env=False,
                          headers=OPENROUTER_HEADERS) as client:
            async_client = httpx.AsyncClient(transport=httpx.MockTransport(receive),
                                             trust_env=False, headers=OPENROUTER_HEADERS)
            model = create_consultant_model(api_key=KEY, http_client=client,
                                            async_http_client=async_client,
                                            request_timeout=5, max_output_tokens=2048)
            try:
                yield model
            finally:
                asyncio.run(async_client.aclose())
                evidence.flush()
                if not all(body.is_closed for body in bodies):
                    raise ValueError("synthetic_model_body_unclosed")


def serve(target):
    import uvicorn
    from jd_relational.consultant_context import build_consultant_node
    from jd_relational.consultant_tools import AiToolMiddleware, build_jd_tools
    from jd_relational.managed_app import open_managed_app

    value = manifest(target)
    if any((target / name).exists() for name in ("serve.ready.json", "serve.finished.json", "stop.request")):
        raise ValueError("probe_already_served")
    with (target / "serve.claimed.json").open("x", encoding="utf-8") as claim:
        json.dump({"pid": os.getpid(), "parent_pid": os.getppid()}, claim)
    file = fixture_file(target, value)
    file.read()  # Validate every real DPAPI read before any selected DB is opened.
    evidence = Evidence(target)
    with offline_model(evidence) as model:
        child = build_consultant_node(model, tools=build_jd_tools(),
            guidance="只供合成 UI 驗收；忠實保存原話描述的工作。", extra_middleware=(AiToolMiddleware(),))
        managed = open_managed_app(file, consultant=child, enable_chat=True)
        done, control, started = Event(), {"reason": "server_exit"}, monotonic()
        server = None
        try:
            settings = managed.opened.settings
            check_settings(settings, value)
            original_execute = managed.opened.host.runtime.storage.execute

            def execute(intent):
                result = original_execute(intent)  # Real SQL and writer authority, unchanged.
                evidence.write(intent, result)
                return result

            managed.opened.host.runtime.storage.execute = execute

            async def app(scope, receive, send):
                await evidence.routes(managed.app, scope, receive, send)

            with bound_socket(managed.port) as bound:
                server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=managed.port,
                    workers=1, reload=False, access_log=False, log_level="critical", log_config=None,
                    timeout_graceful_shutdown=20))

                def controls():
                    try:
                        deadline = monotonic() + 45
                        while not server.started:
                            if done.wait(0.05):
                                return
                            if monotonic() >= deadline:
                                control["reason"] = "startup_timeout"
                                server.should_exit = True
                                return
                        write_report(target / "serve.ready.json", {"pid": os.getpid(), "parent_pid": os.getppid(),
                            "status": "ready", "api_origin": f"http://127.0.0.1:{managed.port}", "ui_origin": ORIGIN,
                            "dataset_id": settings.dataset_id, "installation_id": settings.installation_id,
                            "database": settings.database, "chat_enabled": True, "provider_network": False,
                            "model_transport": "httpx2.MockTransport", "expected_model_requests": 4})
                        while not done.wait(0.1):
                            if (target / "stop.request").exists() or monotonic() - started >= 3600:
                                control["reason"] = "requested" if (target / "stop.request").exists() else "probe_deadline"
                                server.should_exit = True
                                return
                    except Exception:
                        control["reason"] = "control_failed"
                        server.should_exit = True

                thread = Thread(target=controls, daemon=True, name="synthetic-ui-chat-controls")
                thread.start()
                try:
                    server.run(sockets=[bound])
                finally:
                    done.set()
                    thread.join(timeout=2)
        finally:
            done.set()
            closed = managed.close()
            write_report(target / "serve.finished.json", {"pid": os.getpid(), "closed": closed,
                "saver_connection_closed": managed.opened.host.saver_connection.closed,
                "reason": control["reason"], **evidence.snapshot()})
        if server is None or not server.started or not closed:
            raise ValueError("probe_shutdown_unconfirmed")


def stop(target):
    manifest(target)
    try:
        ready = json.loads((target / "serve.ready.json").read_text(encoding="utf-8"))
        if type(ready.get("pid")) is not int or ready["pid"] <= 0 or ready.get("status") != "ready":
            raise ValueError()
    except (OSError, ValueError, TypeError, AttributeError):
        raise ValueError("probe_not_ready") from None
    with (target / "stop.request").open("x", encoding="utf-8"):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "initialize", "serve", "stop"))
    parser.add_argument("directory", type=directory)
    parser.add_argument("--api-port", type=int, default=8768)
    args = parser.parse_args()
    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise ValueError("explicit_test_scope_required")
    if args.mode == "prepare":
        prepare(args.directory, args.api_port)
    elif args.mode == "stop":
        stop(args.directory)
    else:
        with (args.directory / f"{args.mode}.boot.json").open("x", encoding="utf-8") as boot:
            json.dump({"pid": os.getpid(), "parent_pid": os.getppid(),
                "started_at": datetime.now(timezone.utc).isoformat()}, boot)
        if args.mode == "initialize":
            initialize(args.directory)
        else:
            serve(args.directory)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        print("ui_chat_probe_failed", file=sys.stderr, flush=True)
        sys.exit(1)
