"""One-shot synthetic ASGI response gate; never imported by production.

Checked 2026-09-13: ASGI HTTP 2.5 (2024-06-05), response-start/body,
disconnected-client/send-exception and disconnect-receive contracts:
https://asgi.readthedocs.io/en/latest/specs/www.html
Starlette 1.6.0 pure ASGI send wrapping (installed source and official guide):
https://www.starlette.io/middleware/#pure-asgi-middleware
Holding response.start before forwarding also holds 202; delaying execute alone
would not. Disconnect is not writer-death proof, nor is send success proof that
the browser consumed a response. No request/response body is inspected or logged.
"""

import asyncio
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from threading import Lock
from time import monotonic
from uuid import UUID


class GateError(RuntimeError):
    pass


def canonical_uuid(value):
    try:
        return type(value) is str and str(UUID(value)) == value
    except (ValueError, TypeError, AttributeError):
        return False


def write_report(path, value):
    # Only internally constructed fixed fields reach this test-artifact writer.
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class ResponseGate:
    def __init__(self, app, directory: Path, *, timeout=60):
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise GateError("gate_invalid_timeout")
        self.app, self.directory, self.timeout = app, Path(directory), timeout
        self._lock = Lock()
        self._document = self._operation = self._revision = None
        self._forwarded = False
        self._evidence_failed = False
        self._edit_posts = self._operation_gets = 0

    def _event(self, name, **values):
        try:
            write_report(self.directory / f"gate.{name}.json", {
                "format": 1, "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
                "document_id": self._document, "operation_id": self._operation,
                "result_revision_id": self._revision,
                "response_start_forwarded": self._forwarded,
                "writer_stopped_proven": False, **values,
            })
        except Exception:
            self._evidence_failed = True

    def _claim(self, path):
        with self._lock:
            if self._document is not None or (self.directory / "gate.claimed.json").exists():
                return False
            file = self.directory / "gate.arm.json"
            if not file.exists():
                return False
            try:
                raw = file.read_bytes()
                if len(raw) > 1024:
                    raise ValueError()
                value = json.loads(raw)
                if (type(value) is not dict or set(value) != {"format", "document_id"}
                    or type(value["format"]) is not int or value["format"] != 1
                    or not canonical_uuid(value["document_id"])):
                    raise ValueError()
            except Exception:
                raise GateError("gate_invalid_arm") from None
            if path != f"/api/documents/{value['document_id']}/jd/edits":
                return False
            # Durable one-shot sentinel: a normal helper restart never re-arms it.
            try:
                with (self.directory / "gate.claimed.json").open("x", encoding="utf-8") as stream:
                    json.dump(value, stream)
            except Exception:
                raise GateError("gate_claim_failed") from None
            self._document = value["document_id"]
            return True

    def record_execution(self, document, operation_id, observed):
        """Observe the original storage return unchanged; no DB or writer action."""
        with self._lock:
            if document != self._document:
                return
            operation = str(operation_id)
            if self._revision is not None and operation != self._operation:
                return  # Later independent edits are counted by the host probe.
            if not canonical_uuid(operation) or self._operation not in (None, operation):
                self._evidence_failed = True
                return
            self._operation = operation
            receipt = getattr(observed, "receipt", None)
            if (getattr(observed, "confirmed", None) is not True or receipt is None
                or getattr(receipt, "status", None) != "committed"):
                self._event("observed", committed=False)
                return
            revision = str(receipt.result_revision_id)
            if (receipt.document_id != document or str(receipt.operation_id) != operation
                or not canonical_uuid(revision)):
                self._evidence_failed = True
                return
            self._revision = revision
            self._event("committed", committed=True)

    def _ready(self):
        with self._lock:
            return self._revision is not None, (self.directory / "gate.release.request").exists(), self._evidence_failed

    def _note(self, name, **values):
        with self._lock:
            self._event(name, **values)

    def _trace(self, method, path):
        with self._lock:
            if self._document is None:
                return
            prefix = f"/api/documents/{self._document}/jd/"
            if method == "POST" and path == prefix + "edits":
                self._edit_posts += 1
            elif self._operation is not None and method == "GET" and path == prefix + "operations/" + self._operation:
                self._operation_gets += 1
            else:
                return
            self._event("routes", edit_post_count=self._edit_posts,
                original_operation_get_count=self._operation_gets)

    async def __call__(self, scope, receive, send):
        selected = (scope.get("type") == "http" and scope.get("method") == "POST"
            and re.fullmatch(r"/api/documents/[^/]+/jd/edits", scope.get("path", ""))
            and await asyncio.to_thread(self._claim, scope["path"]))
        if scope.get("type") == "http":
            # Count only these two fixed routes, even when a repeated POST is
            # deduplicated before storage.execute. No body/headers/query logging.
            await asyncio.to_thread(self._trace, scope.get("method"), scope.get("path"))
        if not selected:
            await self.app(scope, receive, send)
            return
        released = False

        async def held_send(message):
            nonlocal released
            if message["type"] == "http.response.start" and not released:
                await asyncio.to_thread(self._note, "held", http_status=message["status"])
                started = monotonic()
                while True:
                    committed, release, failed = await asyncio.to_thread(self._ready)
                    if failed:
                        await asyncio.to_thread(self._note, "finished", outcome="evidence_failed")
                        raise GateError("gate_evidence_failed")
                    if committed and release:
                        break
                    if monotonic() - started >= self.timeout:
                        await asyncio.to_thread(self._note, "finished", outcome="timeout",
                            committed_observed=committed, release_requested=release)
                        raise GateError("gate_timeout")
                    await asyncio.sleep(0.02)
                # This records forwarding, not TCP delivery or browser ACK.
                with self._lock:
                    self._forwarded = True
                released = True
            await send(message)

        try:
            await self.app(scope, receive, held_send)
        except OSError:
            await asyncio.to_thread(self._note, "finished", outcome="send_disconnected")
            raise
        except asyncio.CancelledError:
            await asyncio.to_thread(self._note, "finished", outcome="request_cancelled")
            raise
        else:
            await asyncio.to_thread(self._note, "finished", outcome="released" if released else "no_response_start")
