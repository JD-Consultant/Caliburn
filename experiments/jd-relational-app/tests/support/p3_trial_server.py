"""P3 C-W acceptance entry over the formal managed App, for an approved trial.

This is test support. The existing App, A/B1/B2 factory, isolated PostgreSQL
fixture and spend gate remain the owners of their respective behavior.
"""

from __future__ import annotations

import argparse
import asyncio
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from threading import Event, Lock, Thread
from time import monotonic
from uuid import UUID

APP = Path(__file__).resolve().parents[2]
ROOT = APP.parents[1]
sys.path.insert(0, str(APP / "src"))
sys.path.insert(0, str(APP / "tests"))

if __package__:
    from .p3_spend_gate import GuardedAsyncClient, GuardedClient, P3SpendGate, TrialRoleCapture
    from .ui_response_gate_server import (
        ORIGIN, bound_socket, check_settings, directory, fixture_file,
        initialize, manifest, prepare, write_report,
    )
    from .ui_chat_server import Evidence, stop
else:
    from p3_spend_gate import GuardedAsyncClient, GuardedClient, P3SpendGate, TrialRoleCapture
    from ui_response_gate_server import (
        ORIGIN, bound_socket, check_settings, directory, fixture_file,
        initialize, manifest, prepare, write_report,
    )
    from ui_chat_server import Evidence, stop

from jd_relational.consultant_runtime import ConsultantRuntime
from jd_relational.consultant_app import build_consultant
from jd_relational.catalog_service import CatalogService
from jd_relational.chat_history import ChatHistoryCodec, ChatHistoryService
from jd_relational.openrouter_model import OPENROUTER_HEADERS
from jd_relational.provider_keys import read_key
from jd_relational.role_models import create_role_models


PACKAGE = ROOT / "docs/specs/evidence/jd-product-p3-calibration"
TEMPLATE = PACKAGE / "results-template-v3.md"
TRIAL_ID = "p3-c-w"
TURN_CAP = 12
REQUEST_CAP = 180
USD_CAP = Decimal("1.00")
CONTINUATION_ID = "p3-c-w-continuation-1"
CONTINUATION_TURN_CAP = 6
CONTINUATION_REQUEST_CAP = 90
CONTINUATION_USD_CAP = Decimal("0.50")
SECOND_CONTINUATION_ID = "p3-c-w-continuation-2"
SECOND_CONTINUATION_TURN_CAP = 1
SECOND_CONTINUATION_REQUEST_CAP = 120
SECOND_CONTINUATION_USD_CAP = Decimal("0.50")


class TrialPreflightError(RuntimeError):
    """The acceptance entry is not ready to open a paid model route."""


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git(*args: str) -> str:
    try:
        result = subprocess.run(
            ["git", *args], cwd=ROOT, capture_output=True, text=True,
            check=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        raise TrialPreflightError("trial_revision_unverifiable") from None
    return result.stdout.strip()


def preflight(target: Path) -> dict:
    """Require the Owner's later trial unlock and a frozen clean revision.

    Presence of a file is only an operational interlock; it is not evidence
    that the Owner granted approval. The file may be created only after that
    separate decision is recorded.
    """
    unlock = target / "paid-authorization.json"
    if not unlock.is_file():
        raise TrialPreflightError("trial_not_authorized")
    try:
        value = json.loads(unlock.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise TrialPreflightError("trial_authorization_invalid") from None
    if not isinstance(value, dict) or value != {
        "format": 1,
        "trial_id": TRIAL_ID,
        "authorized": True,
        "package_manifest_sha256": value.get("package_manifest_sha256"),
        "results_template_sha256": value.get("results_template_sha256"),
        "git_commit": value.get("git_commit"),
        "employee_turn_cap": TURN_CAP,
        "provider_request_cap": REQUEST_CAP,
        "usd_cap": str(USD_CAP),
        "owner_approval_reference": value.get("owner_approval_reference"),
    }:
        raise TrialPreflightError("trial_authorization_invalid")
    if not isinstance(value["owner_approval_reference"], str) or not value["owner_approval_reference"].strip():
        raise TrialPreflightError("trial_authorization_invalid")
    try:
        package = json.loads((PACKAGE / "manifest.json").read_text(encoding="utf-8"))
        if package.get("version") != 2 or package.get("case") != "C-W":
            raise ValueError()
        # The historical v2 manifest recorded preparation-time raw bytes.
        # Git normalizes the package's mixed line endings on Windows checkout;
        # the exact clean commit below is the runnable content authority.
        for item in package["files"]:
            if not (PACKAGE / item["path"]).is_file():
                raise ValueError()
        actual_package_hash = _hash(PACKAGE / "manifest.json")
    except (OSError, KeyError, TypeError, ValueError):
        raise TrialPreflightError("trial_package_changed") from None
    if value["package_manifest_sha256"] != actual_package_hash:
        raise TrialPreflightError("trial_package_changed")
    try:
        template_hash = _hash(TEMPLATE)
    except OSError:
        raise TrialPreflightError("trial_template_changed") from None
    if value["results_template_sha256"] != template_hash:
        raise TrialPreflightError("trial_template_changed")
    if value["git_commit"] != _git("rev-parse", "HEAD") or _git("status", "--porcelain", "--untracked-files=all"):
        raise TrialPreflightError("trial_revision_changed")
    return value


def preflight_continuation(target: Path, *, second: bool = False) -> dict:
    """Unlock only closed, settled earlier batches on one frozen document."""
    trial_id = SECOND_CONTINUATION_ID if second else CONTINUATION_ID
    turn_cap = SECOND_CONTINUATION_TURN_CAP if second else CONTINUATION_TURN_CAP
    request_cap = SECOND_CONTINUATION_REQUEST_CAP if second else CONTINUATION_REQUEST_CAP
    usd_cap = SECOND_CONTINUATION_USD_CAP if second else CONTINUATION_USD_CAP
    prior_dir = target / "continuation" if second else target
    prior_id = CONTINUATION_ID if second else TRIAL_ID
    prior_turn_count = 1 if second else TURN_CAP
    approval_path = target / ("continuation-2" if second else "continuation") / "paid-authorization.json"
    if not approval_path.is_file():
        raise TrialPreflightError("continuation_not_authorized")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise TrialPreflightError("continuation_authorization_invalid") from None
    required = {
        "format", "trial_id", "authorized", "document_id", "git_commit",
        "employee_turn_cap", "provider_request_cap", "usd_cap",
        "prior_turns_sha256", "prior_spend_sha256", "prior_finish_sha256",
        "owner_approval_reference",
    }
    if second:
        required.add("prior_approval_sha256")
    if (type(approval) is not dict or set(approval) != required
            or type(approval["format"]) is not int or approval["format"] != 1
            or approval["trial_id"] != trial_id or approval["authorized"] is not True
            or approval["employee_turn_cap"] != turn_cap
            or approval["provider_request_cap"] != request_cap
            or approval["usd_cap"] != str(usd_cap)
            or type(approval["git_commit"]) is not str
            or type(approval["owner_approval_reference"]) is not str
            or not approval["owner_approval_reference"].strip()):
        raise TrialPreflightError("continuation_authorization_invalid")
    try:
        if (type(approval["document_id"]) is not str
                or str(UUID(approval["document_id"])) != approval["document_id"]):
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise TrialPreflightError("continuation_authorization_invalid") from None
    if (approval["git_commit"] != _git("rev-parse", "HEAD")
            or _git("status", "--porcelain", "--untracked-files=all")):
        raise TrialPreflightError("continuation_revision_changed")

    if second:
        first_approval_path = prior_dir / "paid-authorization.json"
        try:
            if _hash(first_approval_path) != approval["prior_approval_sha256"]:
                raise TrialPreflightError("continuation_prior_changed")
            first_approval = json.loads(first_approval_path.read_text(encoding="utf-8"))
            if (first_approval.get("document_id") != approval["document_id"]
                    or any(_hash(target / f"{name}.json") != first_approval[f"prior_{label}_sha256"]
                           for label, name in (("turns", "turns"), ("spend", "spend"),
                                               ("finish", "serve.finished")))):
                raise TrialPreflightError("continuation_prior_changed")
        except (OSError, KeyError, AttributeError, TypeError, json.JSONDecodeError):
            raise TrialPreflightError("continuation_prior_changed") from None
    prior_paths = {"turns": prior_dir / "turns.json", "spend": prior_dir / "spend.json",
                   "finish": prior_dir / "serve.finished.json"}
    try:
        if any(_hash(path) != approval[f"prior_{name}_sha256"]
               for name, path in prior_paths.items()):
            raise TrialPreflightError("continuation_prior_changed")
        prior = {name: json.loads(path.read_text(encoding="utf-8"))
                 for name, path in prior_paths.items()}
    except (OSError, json.JSONDecodeError):
        raise TrialPreflightError("continuation_prior_changed") from None
    turns, spend, finish = prior["turns"], prior["spend"], prior["finish"]
    if (type(turns) is not dict or turns.get("trial_id") != prior_id
            or type(turns.get("turn_attempts")) is not int
            or turns["turn_attempts"] != prior_turn_count
            or type(spend) is not dict or spend.get("trial_id") != prior_id
            or spend.get("status") != "active" or spend.get("in_flight") != []
            or spend.get("retained_unknown_usd") != "0"
            or type(spend.get("attempt_count")) is not int
            or type(spend.get("attempts")) is not list
            or len(spend["attempts"]) != spend["attempt_count"]
            or not all(type(attempt) is dict and attempt.get("outcome") == "settled"
                       for attempt in spend["attempts"])
            or type(finish) is not dict or finish.get("app_closed") is not True
            or finish.get("saver_connection_closed") is not True
            or finish.get("reason") != "requested"
            or finish.get("spend") != spend
            or type(finish.get("evidence")) is not dict
            or finish["evidence"].get("model_request_count") != spend["attempt_count"]
            or finish["evidence"].get("http_counts", {}).get("POST chat_runs") != prior_turn_count):
        raise TrialPreflightError("continuation_prior_unsettled")
    return approval


class P3TurnGate:
    """Conservatively count chat POST attempts before reaching the App."""

    def __init__(self, app, path: Path, *, cap: int = TURN_CAP,
                 trial_id: str = TRIAL_ID, document_id: str | None = None):
        self.app, self.path, self.cap = app, Path(path), cap
        self.trial_id, self.document_id = trial_id, document_id
        self._lock = Lock()
        self._stopped = False
        if self.path.exists():
            try:
                state = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                raise TrialPreflightError("trial_turn_state_invalid") from None
            if (type(state) is not dict or set(state) != {"format", "trial_id", "turn_attempts"}
                    or state["format"] != 1 or state["trial_id"] != trial_id
                    or type(state["turn_attempts"]) is not int
                    or not 0 <= state["turn_attempts"] <= cap):
                raise TrialPreflightError("trial_turn_state_invalid")
            self._state = state
        else:
            self._state = {"format": 1, "trial_id": trial_id, "turn_attempts": 0}
            self._persist()

    def _persist(self):
        temporary = self.path.with_name(self.path.name + ".tmp")
        try:
            with temporary.open("w", encoding="utf-8", newline="\n") as stream:
                json.dump(self._state, stream)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except OSError:
            self._stopped = True
            raise TrialPreflightError("trial_turn_state_unwritable") from None

    async def __call__(self, scope, receive, send):
        if (self.document_id is not None and scope["type"] == "http"
                and scope.get("method") in {"POST", "PUT", "PATCH", "DELETE"}):
            path = scope.get("path", "")
            match = re.fullmatch(r"/api/documents(?:/([^/]+)(?:/.*)?)?/?", path)
            if match and match.group(1) != self.document_id:
                body = b'{"code":"trial_document_scope"}'
                await send({"type": "http.response.start", "status": 403,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        if (scope["type"] == "http" and scope.get("method") == "POST"
                and re.fullmatch(r"/api/documents/[^/]+/chat/runs/?", scope.get("path", ""))):
            with self._lock:
                if self._stopped:
                    raise TrialPreflightError("trial_turn_state_unwritable")
                if self._state["turn_attempts"] >= self.cap:
                    denied = True
                else:
                    self._state["turn_attempts"] += 1
                    self._persist()
                    denied = False
            if denied:
                body = b'{"code":"trial_turn_cap"}'
                await send({"type": "http.response.start", "status": 429,
                    "headers": [(b"content-type", b"application/json"),
                                (b"content-length", str(len(body)).encode())]})
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


class TrialEvidence(Evidence):
    """Reuse the existing HTTP/JD receipt observer with the real spend ledger."""

    def __init__(self, target: Path, spend: P3SpendGate):
        self.spend = spend
        super().__init__(target)

    def _snapshot(self):
        value = super()._snapshot()
        state = self.spend.snapshot()
        value["provider_network"] = True
        value["model_request_count"] = state["attempt_count"]
        value["model_requests"] = state["attempts"]
        value.pop("closed_model_bodies", None)
        return value


def verify_prior_conversation(managed, document_id: str, target: Path,
                              *, expected_turns: int = TURN_CAP) -> None:
    """Read the existing App authority before admitting any continuation HTTP."""
    settings = managed.opened.settings
    try:
        initialized = json.loads((target / "initialize.finished.json").read_text(encoding="utf-8"))
        if (type(initialized) is not dict
                or initialized.get("dataset_id") != settings.dataset_id):
            raise ValueError()
        catalog = CatalogService(managed.opened.host.runtime, settings.dataset_id).list(archived=None)
        if (catalog.get("dataset_id") != settings.dataset_id
                or catalog.get("next_after") is not None
                or len(catalog.get("documents", [])) != 1
                or catalog["documents"][0]["document_id"] != document_id):
            raise TrialPreflightError("continuation_document_mismatch")
        history = ChatHistoryService(managed.ai_runtime.checkpoints, ChatHistoryCodec(
            settings.signing_key_bytes(), settings.dataset_id)).read(document_id, limit=50)
        messages = history.get("messages")
        if (history.get("dataset_id") != settings.dataset_id
                or history.get("document_id") != document_id
                or history.get("next_cursor") is not None
                or type(messages) is not list or len(messages) != 2 * expected_turns):
            raise TrialPreflightError("continuation_prior_run_incomplete")
        seen = set()
        for index in range(0, len(messages), 2):
            employee, assistant = messages[index:index + 2]
            run_id = employee.get("run_id")
            if (employee.get("role") != "user" or employee.get("message_id") != run_id
                    or run_id in seen or assistant.get("role") != "assistant"
                    or assistant.get("run_id") != run_id
                    or not assistant.get("message_id")):
                raise TrialPreflightError("continuation_prior_run_incomplete")
            seen.add(run_id)
            observed = managed.ai_runtime.run_history.find(document_id, run_id,
                                                            settings.dataset_id)
            if (observed is None or not observed.closed
                    or observed.record.run_id != run_id
                    or observed.record.document_id != document_id
                    or observed.record.dataset_id != settings.dataset_id
                    or observed.record.status != "completed"):
                raise TrialPreflightError("continuation_prior_run_incomplete")
    except TrialPreflightError:
        raise
    except Exception:
        raise TrialPreflightError("continuation_prior_run_incomplete") from None


@contextmanager
def open_trial_runtime(spend: P3SpendGate, api_key: str, *, transport=None):
    """Formal A/B1/B2 graph with one guarded sync/async provider boundary."""
    clients = {
        "headers": OPENROUTER_HEADERS,
        "trust_env": False,
        # httpx follows redirects inside one send(), bypassing this trial's
        # per-request admission hook. A redirect is an unaccountable response.
        "follow_redirects": False,
    }
    if transport is not None:
        clients["transport"] = transport
    sync_client = GuardedClient(spend, require_role=True, **clients)
    async_client = GuardedAsyncClient(spend, require_role=True, **clients)
    try:
        roles = create_role_models(api_key=api_key, http_client=sync_client,
                                   async_http_client=async_client)
        for model in (roles.consultant, roles.case, roles.understanding):
            model.callbacks = [*(model.callbacks or []), TrialRoleCapture()]
        runtime = ConsultantRuntime(build_consultant(roles.consultant), roles,
                                    sync_client, async_client)
        try:
            yield runtime
        finally:
            if not runtime.close():
                raise TrialPreflightError("trial_model_clients_not_closed")
    except BaseException:
        sync_client.close()
        if not async_client.is_closed:
            asyncio.run(async_client.aclose())
        raise


def serve(target: Path, *, continuation: bool = False,
          second_continuation: bool = False):
    """Explicit later paid run. No service starts without the unlock preflight."""
    import uvicorn
    from jd_relational.managed_app import open_managed_app

    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise TrialPreflightError("explicit_test_scope_required")
    value = manifest(target)
    if continuation and second_continuation:
        raise TrialPreflightError("trial_mode_invalid")
    is_continuation = continuation or second_continuation
    approval = preflight_continuation(target, second=second_continuation) if is_continuation else preflight(target)
    artifacts = target / ("continuation-2" if second_continuation else "continuation") if is_continuation else target
    trial_id = SECOND_CONTINUATION_ID if second_continuation else CONTINUATION_ID if continuation else TRIAL_ID
    turn_cap = SECOND_CONTINUATION_TURN_CAP if second_continuation else CONTINUATION_TURN_CAP if continuation else TURN_CAP
    request_cap = SECOND_CONTINUATION_REQUEST_CAP if second_continuation else CONTINUATION_REQUEST_CAP if continuation else REQUEST_CAP
    usd_cap = SECOND_CONTINUATION_USD_CAP if second_continuation else CONTINUATION_USD_CAP if continuation else USD_CAP
    if any((artifacts / name).exists() for name in ("serve.ready.json", "serve.finished.json", "stop.request")):
        raise TrialPreflightError("trial_already_served")
    file = fixture_file(target, value)
    file.read()
    key = read_key("openrouter")
    if not key:
        raise TrialPreflightError("trial_credential_missing")
    spend = P3SpendGate(artifacts / "spend.json", trial_id=trial_id, authorized=True,
                        usd_cap=usd_cap, request_cap=request_cap, wait_timeout_seconds=30)
    evidence = TrialEvidence(artifacts, spend)
    with open_trial_runtime(spend, key) as runtime:
        del key
        managed = open_managed_app(file, consultant=runtime.graph, enable_chat=True,
                                   case_model=runtime.role_models.case,
                                   understanding_model=runtime.role_models.understanding)
        done, control = Event(), {"reason": "server_exit"}
        started = monotonic()
        try:
            check_settings(managed.opened.settings, value)
            if is_continuation:
                verify_prior_conversation(managed, approval["document_id"], target,
                                          expected_turns=TURN_CAP + (1 if second_continuation else 0))
            original_execute = managed.opened.host.runtime.storage.execute

            def observe_write(intent):
                result = original_execute(intent)
                evidence.write(intent, result)
                return result

            managed.opened.host.runtime.storage.execute = observe_write
            turns = P3TurnGate(managed.app, artifacts / "turns.json", cap=turn_cap,
                               trial_id=trial_id,
                               document_id=approval["document_id"] if is_continuation else None)

            async def app(scope, receive, send):
                await evidence.routes(turns, scope, receive, send)

            with bound_socket(managed.port) as bound:
                server = uvicorn.Server(uvicorn.Config(
                    app, host="127.0.0.1", port=managed.port, workers=1,
                    reload=False, access_log=False, log_level="critical",
                    timeout_graceful_shutdown=30,
                ))

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
                        ready = {
                            "pid": os.getpid(), "status": "ready",
                            "api_origin": f"http://127.0.0.1:{managed.port}",
                            "ui_origin": ORIGIN, "database": value["database"],
                            "trial_id": trial_id,
                            "git_commit": approval["git_commit"],
                            "employee_turn_cap": turn_cap,
                            "provider_request_cap": request_cap,
                            "usd_cap": str(usd_cap),
                        }
                        if is_continuation:
                            ready["document_id"] = approval["document_id"]
                        else:
                            ready["package_manifest_sha256"] = approval["package_manifest_sha256"]
                            ready["results_template_sha256"] = approval["results_template_sha256"]
                        write_report(artifacts / "serve.ready.json", ready)
                        while not done.wait(0.1):
                            if (artifacts / "stop.request").exists() or monotonic() - started >= 3600:
                                control["reason"] = "requested" if (artifacts / "stop.request").exists() else "trial_deadline"
                                server.should_exit = True
                                return
                    except Exception:
                        control["reason"] = "control_failed"
                        server.should_exit = True

                thread = Thread(target=controls, daemon=True, name="p3-trial-controls")
                thread.start()
                try:
                    server.run(sockets=[bound])
                finally:
                    done.set()
                    thread.join(timeout=2)
        finally:
            done.set()
            closed = managed.close()
            write_report(artifacts / "serve.finished.json", {
                "pid": os.getpid(), "app_closed": closed,
                "saver_connection_closed": managed.opened.host.saver_connection.closed,
                "reason": control["reason"], "spend": spend.snapshot(),
                "evidence": evidence.snapshot(),
            })
        if not server.started or not closed:
            raise TrialPreflightError("trial_shutdown_unconfirmed")


def stop_continuation(target: Path, *, second: bool = False):
    manifest(target)
    artifacts = target / ("continuation-2" if second else "continuation")
    trial_id = SECOND_CONTINUATION_ID if second else CONTINUATION_ID
    try:
        ready = json.loads((artifacts / "serve.ready.json").read_text(encoding="utf-8"))
        if (type(ready.get("pid")) is not int or ready["pid"] <= 0
                or ready.get("status") != "ready" or ready.get("trial_id") != trial_id):
            raise ValueError()
    except (OSError, ValueError, TypeError, AttributeError):
        raise TrialPreflightError("continuation_not_ready") from None
    with (artifacts / "stop.request").open("x", encoding="utf-8"):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "initialize", "serve", "stop",
                                         "continue", "stop-continuation",
                                         "continue-2", "stop-continuation-2"))
    parser.add_argument("directory", type=directory)
    parser.add_argument("--api-port", type=int, default=8769)
    args = parser.parse_args()
    if sys.platform != "win32" or os.environ.get("JD_RELATIONAL_TEST_DB") != "1":
        raise TrialPreflightError("explicit_test_scope_required")
    if args.mode == "prepare":
        prepare(args.directory, args.api_port)
    elif args.mode == "initialize":
        initialize(args.directory)
    elif args.mode == "stop":
        stop(args.directory)
    elif args.mode == "stop-continuation":
        stop_continuation(args.directory)
    elif args.mode == "stop-continuation-2":
        stop_continuation(args.directory, second=True)
    else:
        serve(args.directory, continuation=args.mode == "continue",
              second_continuation=args.mode == "continue-2")


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except BaseException:
        print("p3_trial_entry_failed", file=sys.stderr, flush=True)
        sys.exit(1)
