"""Offline checks for the P3 acceptance entry; no listener or provider network."""

import asyncio
from datetime import datetime
from decimal import Decimal
import json
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from langsmith import tracing_context

from jd_relational.openrouter_model import OPENROUTER_HEADERS
from langchain_openai import ChatOpenAI
from support.p3_spend_gate import BudgetGateError, P3SpendGate
from support.openai_replies import reply
from support import p3_trial_server as trial


def _spend(tmp_path):
    return P3SpendGate(
        tmp_path / "spend.json", trial_id="p3-c-w", authorized=False,
        usd_cap=Decimal("1.00"), request_cap=180, wait_timeout_seconds=1,
    )


def test_no_approval_stops_before_credential_or_host(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("credential_or_host_accessed")

    monkeypatch.setattr(trial, "read_key", forbidden)
    monkeypatch.setattr(trial, "fixture_file", forbidden)
    monkeypatch.setattr(trial, "manifest", lambda *_args: {"fixture": "offline"})
    monkeypatch.setenv("JD_RELATIONAL_TEST_DB", "1")
    with pytest.raises(trial.TrialPreflightError, match="trial_not_authorized"):
        trial.serve(tmp_path)


def test_formal_a_b1_b2_share_denying_clients_without_provider_network(tmp_path):
    spend = _spend(tmp_path)
    observed = []

    def forbidden(request):
        observed.append(request)
        raise AssertionError("provider_network")

    transport = httpx.MockTransport(forbidden)
    with trial.open_trial_runtime(spend, "synthetic-not-a-secret", transport=transport) as runtime:
        assert runtime.role_models.consultant is not runtime.role_models.case
        assert runtime.role_models.case is not runtime.role_models.understanding
        assert runtime.http_client.headers["X-OpenRouter-Metadata"] == OPENROUTER_HEADERS["X-OpenRouter-Metadata"]
        assert runtime.graph is not None
        with tracing_context(enabled=False):
            for model in (runtime.role_models.consultant, runtime.role_models.case,
                          runtime.role_models.understanding):
                with pytest.raises(Exception) as failure:
                    model.invoke("合成輸入")
                assert isinstance(failure.value.__cause__.__cause__, BudgetGateError)
                assert str(failure.value.__cause__.__cause__) == "not_authorized"
    assert observed == []
    assert spend.snapshot()["attempt_count"] == 0


def test_formal_role_calls_record_exact_role_and_timing_without_private_content(tmp_path):
    spend = P3SpendGate(
        tmp_path / "spend.json", trial_id="p3-c-w", authorized=True,
        usd_cap=Decimal("1.00"), request_cap=180, wait_timeout_seconds=1,
    )
    sent = []

    def receive(request):
        sent.append(request)
        wire = reply(f"gen-synthetic-{len(sent)}")
        wire["model"] = "openai/gpt-6-luna"
        wire["provider"] = "OpenAI"
        wire["usage"]["cost"] = "0.001"
        return httpx.Response(200, json=wire,
                              headers={"X-Generation-Id": f"gen-router-{len(sent)}"},
                              request=request)

    with trial.open_trial_runtime(spend, "synthetic-not-a-secret",
                                  transport=httpx.MockTransport(receive)) as runtime:
        with tracing_context(enabled=False):
            runtime.role_models.consultant.invoke("PRIVATE-EMPLOYEE-A")
            runtime.role_models.case.invoke("PRIVATE-CASE-B1")
            asyncio.run(runtime.role_models.understanding.ainvoke("PRIVATE-UNDERSTANDING-B2"))

    attempts = spend.snapshot()["attempts"]
    assert len(sent) == 3
    assert [item["role"] for item in attempts] == [
        "consultant", "background-case-maintainer", "background-understanding-maintainer",
    ]
    assert [item["max_output_tokens"] for item in attempts] == [8192, 32768, 32768]
    assert [item["response_id"] for item in attempts] == [
        "resp_gen-synthetic-1", "resp_gen-synthetic-2", "resp_gen-synthetic-3",
    ]
    assert [item["router_generation_id"] for item in attempts] == [
        "gen-router-1", "gen-router-2", "gen-router-3",
    ]
    assert all(item["http_status"] == 200 for item in attempts)
    for item in attempts:
        start = datetime.fromisoformat(item["started_at_utc"])
        end = datetime.fromisoformat(item["ended_at_utc"])
        assert start.tzinfo is not None and end.tzinfo is not None
        assert end >= start
    ledger = (tmp_path / "spend.json").read_text(encoding="utf-8")
    assert "PRIVATE-" not in ledger
    assert "synthetic-not-a-secret" not in ledger


def test_trial_runtime_refuses_missing_model_role_before_provider_network(tmp_path):
    spend = P3SpendGate(
        tmp_path / "spend.json", trial_id="p3-c-w", authorized=True,
        usd_cap=Decimal("1.00"), request_cap=180, wait_timeout_seconds=1,
    )
    sent = []

    def receive(request):
        sent.append(request)
        raise AssertionError("provider_network")

    with trial.open_trial_runtime(spend, "synthetic-not-a-secret",
                                  transport=httpx.MockTransport(receive)) as runtime:
        runtime.role_models.case.callbacks = []
        with tracing_context(enabled=False):
            with pytest.raises(Exception) as failure:
                runtime.role_models.case.invoke("合成輸入")
            assert isinstance(failure.value.__cause__.__cause__, BudgetGateError)
            assert str(failure.value.__cause__.__cause__) == "request_role_missing"
    assert sent == []
    assert spend.snapshot()["attempt_count"] == 0


def test_trial_role_is_cleared_after_provider_error(tmp_path):
    spend = P3SpendGate(
        tmp_path / "spend.json", trial_id="p3-c-w", authorized=True,
        usd_cap=Decimal("1.00"), request_cap=180, wait_timeout_seconds=1,
    )
    sent = []

    def receive(request):
        sent.append(request)
        return httpx.Response(500, json={"error": "synthetic"}, request=request)

    with trial.open_trial_runtime(spend, "synthetic-not-a-secret",
                                  transport=httpx.MockTransport(receive)) as runtime:
        with tracing_context(enabled=False):
            with pytest.raises(Exception) as failure:
                runtime.role_models.case.invoke("合成輸入")
            assert isinstance(failure.value.__cause__.__cause__, BudgetGateError)
            assert str(failure.value.__cause__.__cause__) == "provider_http_500"
            with pytest.raises(BudgetGateError, match="request_role_missing"):
                runtime.http_client.send(httpx.Request("POST", "https://openrouter.ai/api/v1/responses"))
    assert len(sent) == 1
    assert spend.snapshot()["attempt_count"] == 1


def test_trial_client_does_not_follow_provider_redirect_outside_gate(tmp_path):
    spend = P3SpendGate(
        tmp_path / "spend.json", trial_id="p3-c-w", authorized=True,
        usd_cap=Decimal("1.00"), request_cap=180, wait_timeout_seconds=1,
    )
    sent_to = []

    def redirected(request):
        sent_to.append(str(request.url))
        return httpx.Response(307, headers={"location": "https://elsewhere.invalid/"},
                              request=request)

    with trial.open_trial_runtime(spend, "synthetic-not-a-secret",
                                  transport=httpx.MockTransport(redirected)) as runtime:
        with tracing_context(enabled=False):
            with pytest.raises(Exception) as failure:
                runtime.role_models.consultant.invoke("合成輸入")
            assert isinstance(failure.value.__cause__.__cause__, BudgetGateError)
            assert str(failure.value.__cause__.__cause__) == "provider_http_307"
    assert sent_to == ["https://openrouter.ai/api/v1/responses"]
    assert spend.snapshot()["status"] == "stopped"


def test_chat_turn_cap_persists_across_trial_gate_reopen(tmp_path):
    saved = tmp_path / "turns.json"
    document = uuid4()
    received = []

    async def app(scope, receive, send):
        received.append((scope["method"], scope["path"]))
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def request(gate, path, method="POST"):
        sent = []

        async def receive():
            raise AssertionError("trial_gate_must_not_read_body")

        async def send(message):
            sent.append(message)

        await gate({"type": "http", "method": method, "path": path}, receive, send)
        return sent[0]["status"]

    path = f"/api/documents/{document}/chat/runs"
    gate = trial.P3TurnGate(app, saved)
    for _ in range(6):
        assert asyncio.run(request(gate, path)) == 200
    gate = trial.P3TurnGate(app, saved)
    for _ in range(6):
        assert asyncio.run(request(gate, path)) == 200
    assert asyncio.run(request(gate, path)) == 429
    assert asyncio.run(request(gate, path + f"/{uuid4()}", "GET")) == 200
    assert len(received) == 13
    assert json.loads(saved.read_text(encoding="utf-8"))["turn_attempts"] == 12


def test_chat_turn_guard_covers_uuid_spelling_and_stops_after_failed_ledger_write(tmp_path, monkeypatch):
    saved = tmp_path / "turns.json"
    received = []

    async def app(scope, receive, send):
        received.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    gate = trial.P3TurnGate(app, saved)
    path = f"/api/documents/{uuid4().hex.upper()}/chat/runs"

    async def request():
        sent = []
        async def send(message):
            sent.append(message)
        await gate({"type": "http", "method": "POST", "path": path},
                   lambda: None, send)
        return sent[0]["status"]

    assert asyncio.run(request()) == 200
    assert gate._state["turn_attempts"] == 1
    monkeypatch.setattr(trial.os, "replace", lambda *_args: (_ for _ in ()).throw(OSError("synthetic")))
    with pytest.raises(trial.TrialPreflightError, match="trial_turn_state_unwritable"):
        asyncio.run(request())
    with pytest.raises(trial.TrialPreflightError, match="trial_turn_state_unwritable"):
        asyncio.run(request())
    assert received == [path]


def test_approved_file_needs_exact_package_and_frozen_commit(tmp_path, monkeypatch):
    package_hash = trial._hash(trial.PACKAGE / "manifest.json")
    unlock = {"format": 1, "trial_id": "p3-c-w", "authorized": True,
              "package_manifest_sha256": package_hash,
              "results_template_sha256": trial._hash(trial.TEMPLATE),
              "git_commit": "fixed-commit",
              "employee_turn_cap": 12, "provider_request_cap": 180,
              "usd_cap": "1.00", "owner_approval_reference": "later-owner-decision"}
    (tmp_path / "paid-authorization.json").write_text(json.dumps(unlock), encoding="utf-8")
    monkeypatch.setattr(trial, "_git", lambda *args: "fixed-commit" if args[0] == "rev-parse" else "")
    assert trial.preflight(tmp_path) == unlock
    unlock["package_manifest_sha256"] = "0" * 64
    (tmp_path / "paid-authorization.json").write_text(json.dumps(unlock), encoding="utf-8")
    with pytest.raises(trial.TrialPreflightError, match="trial_package_changed"):
        trial.preflight(tmp_path)
    unlock["package_manifest_sha256"] = package_hash
    unlock["results_template_sha256"] = "0" * 64
    (tmp_path / "paid-authorization.json").write_text(json.dumps(unlock), encoding="utf-8")
    with pytest.raises(trial.TrialPreflightError, match="trial_template_changed"):
        trial.preflight(tmp_path)


def test_paid_entry_assembles_formal_graph_and_background_roles_before_host(tmp_path, monkeypatch):
    from jd_relational import managed_app as managed_app_module

    class CompositionReached(RuntimeError):
        pass

    seen = {}

    def capture(file, **kwargs):
        seen["file"] = file
        seen.update(kwargs)
        raise CompositionReached

    selected = SimpleNamespace(read=lambda: None)
    monkeypatch.setenv("JD_RELATIONAL_TEST_DB", "1")
    monkeypatch.setattr(trial, "manifest", lambda *_args: {"fixture": "offline"})
    monkeypatch.setattr(trial, "preflight", lambda *_args: {"git_commit": "frozen"})
    monkeypatch.setattr(trial, "fixture_file", lambda *_args: selected)
    monkeypatch.setattr(trial, "read_key", lambda *_args: "synthetic-not-a-secret")
    monkeypatch.setattr(managed_app_module, "open_managed_app", capture)

    with pytest.raises(CompositionReached):
        trial.serve(tmp_path)

    assert seen["file"] is selected
    assert seen["enable_chat"] is True
    assert isinstance(seen["case_model"], ChatOpenAI)
    assert isinstance(seen["understanding_model"], ChatOpenAI)
    assert seen["consultant"] is not None
    assert json.loads((tmp_path / "spend.json").read_text(encoding="utf-8"))["attempt_count"] == 0


def test_trial_evidence_uses_spend_attempts_and_keeps_request_content_out(tmp_path):
    attempt = {"attempt_id": 1, "model": "openai/gpt-6-luna",
               "max_output_tokens": 8192, "reserve_usd": "0.268644",
               "actual_cost_usd": "0.001", "outcome": "settled"}
    spend = SimpleNamespace(snapshot=lambda: {"attempt_count": 1, "attempts": [attempt]})
    evidence = trial.TrialEvidence(tmp_path, spend)
    observed = evidence.snapshot()
    assert observed["provider_network"] is True
    assert observed["model_request_count"] == 1
    assert observed["model_requests"] == [attempt]
    assert "closed_model_bodies" not in observed


def test_invalid_turn_state_fails_closed_before_app(tmp_path):
    saved = tmp_path / "turns.json"
    saved.write_text('{"turn_attempts": "unknown"}', encoding="utf-8")

    async def app(*_args):
        raise AssertionError("invalid_state_reached_app")

    with pytest.raises(trial.TrialPreflightError, match="trial_turn_state_invalid"):
        trial.P3TurnGate(app, saved)


def _continuation_records(tmp_path, monkeypatch):
    document_id = str(uuid4())
    prior_turns = {"format": 1, "trial_id": trial.TRIAL_ID, "turn_attempts": 12}
    prior_spend = {
        "format": 1, "trial_id": trial.TRIAL_ID, "status": "active",
        "attempt_count": 1, "spent_usd": "0.001", "retained_unknown_usd": "0",
        "in_flight": [], "attempts": [{"outcome": "settled"}],
    }
    prior_finish = {
        "reason": "requested", "app_closed": True, "saver_connection_closed": True,
        "spend": prior_spend, "evidence": {"model_request_count": 1,
                                              "http_counts": {"POST chat_runs": 12}},
    }
    for name, data in (("turns.json", prior_turns), ("spend.json", prior_spend),
                       ("serve.finished.json", prior_finish)):
        (tmp_path / name).write_text(json.dumps(data), encoding="utf-8")
    continuation = tmp_path / "continuation"
    continuation.mkdir()
    approval = {
        "format": 1, "trial_id": trial.CONTINUATION_ID, "authorized": True,
        "document_id": document_id, "git_commit": "frozen",
        "employee_turn_cap": 6, "provider_request_cap": 90, "usd_cap": "0.50",
        "prior_turns_sha256": trial._hash(tmp_path / "turns.json"),
        "prior_spend_sha256": trial._hash(tmp_path / "spend.json"),
        "prior_finish_sha256": trial._hash(tmp_path / "serve.finished.json"),
        "owner_approval_reference": "owner-approved-separate-batch",
    }
    (continuation / "paid-authorization.json").write_text(
        json.dumps(approval), encoding="utf-8",
    )
    monkeypatch.setattr(trial, "_git", lambda *args: "frozen" if args[0] == "rev-parse" else "")
    return document_id, approval


def test_continuation_requires_separate_approval_before_credential_or_host(tmp_path, monkeypatch):
    (tmp_path / "continuation").mkdir()
    monkeypatch.setenv("JD_RELATIONAL_TEST_DB", "1")
    monkeypatch.setattr(trial, "manifest", lambda *_args: {"fixture": "offline"})
    monkeypatch.setattr(trial, "read_key", lambda *_args: (_ for _ in ()).throw(
        AssertionError("credential_accessed")))
    monkeypatch.setattr(trial, "fixture_file", lambda *_args: (_ for _ in ()).throw(
        AssertionError("host_accessed")))

    with pytest.raises(trial.TrialPreflightError, match="continuation_not_authorized"):
        trial.serve(tmp_path, continuation=True)


def test_continuation_requires_closed_settled_prior_batch_and_frozen_records(tmp_path, monkeypatch):
    document_id, approval = _continuation_records(tmp_path, monkeypatch)
    assert trial.preflight_continuation(tmp_path)["document_id"] == document_id

    spend_path = tmp_path / "spend.json"
    spend = json.loads(spend_path.read_text(encoding="utf-8"))
    spend["in_flight"] = [{"attempt_id": 2}]
    spend_path.write_text(json.dumps(spend), encoding="utf-8")
    with pytest.raises(trial.TrialPreflightError, match="continuation_prior_changed"):
        trial.preflight_continuation(tmp_path)

    approval["prior_spend_sha256"] = trial._hash(spend_path)
    (tmp_path / "continuation" / "paid-authorization.json").write_text(
        json.dumps(approval), encoding="utf-8",
    )
    with pytest.raises(trial.TrialPreflightError, match="continuation_prior_unsettled"):
        trial.preflight_continuation(tmp_path)

    spend["in_flight"] = []
    spend_path.write_text(json.dumps(spend), encoding="utf-8")
    approval["prior_spend_sha256"] = trial._hash(spend_path)
    approval["document_id"] = str(uuid4()) + "wrong"
    (tmp_path / "continuation" / "paid-authorization.json").write_text(
        json.dumps(approval), encoding="utf-8",
    )
    with pytest.raises(trial.TrialPreflightError, match="continuation_authorization_invalid"):
        trial.preflight_continuation(tmp_path)


def test_continuation_turn_gate_only_allows_existing_document_and_six_new_turns(tmp_path):
    document_id, other_id = str(uuid4()), str(uuid4())
    called = []
    (tmp_path / "continuation").mkdir()

    async def app(scope, receive, send):
        called.append(scope["path"])
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    async def request(gate, method, path):
        messages = []
        async def send(message):
            messages.append(message)
        await gate({"type": "http", "method": method, "path": path},
                   lambda: None, send)
        return messages[0]["status"]

    path = f"/api/documents/{document_id}/chat/runs"
    gate = trial.P3TurnGate(app, tmp_path / "continuation" / "turns.json", cap=6,
                            trial_id=trial.CONTINUATION_ID, document_id=document_id)
    assert asyncio.run(request(gate, "POST", "/api/documents")) == 403
    assert asyncio.run(request(gate, "POST", f"/api/documents/{other_id}/chat/runs")) == 403
    for _ in range(3):
        assert asyncio.run(request(gate, "POST", path)) == 200
    gate = trial.P3TurnGate(app, tmp_path / "continuation" / "turns.json", cap=6,
                            trial_id=trial.CONTINUATION_ID, document_id=document_id)
    for _ in range(3):
        assert asyncio.run(request(gate, "POST", path)) == 200
    assert asyncio.run(request(gate, "POST", path)) == 429
    assert called == [path] * 6
    assert json.loads((tmp_path / "continuation" / "turns.json").read_text())["turn_attempts"] == 6


def test_continuation_formal_app_reuses_original_fixture_with_new_ledger(tmp_path, monkeypatch):
    from jd_relational import managed_app as managed_app_module

    class CompositionReached(RuntimeError):
        pass

    document_id, _approval = _continuation_records(tmp_path, monkeypatch)
    selected = SimpleNamespace(read=lambda: None)
    seen = {}

    def capture(file, **kwargs):
        seen["file"] = file
        seen.update(kwargs)
        raise CompositionReached

    monkeypatch.setenv("JD_RELATIONAL_TEST_DB", "1")
    monkeypatch.setattr(trial, "manifest", lambda *_args: {"fixture": "offline"})
    monkeypatch.setattr(trial, "fixture_file", lambda *_args: selected)
    monkeypatch.setattr(trial, "read_key", lambda *_args: "synthetic-not-a-secret")
    monkeypatch.setattr(managed_app_module, "open_managed_app", capture)
    prior_spend = (tmp_path / "spend.json").read_bytes()

    with pytest.raises(CompositionReached):
        trial.serve(tmp_path, continuation=True)

    assert seen["file"] is selected
    assert seen["enable_chat"] is True
    assert (tmp_path / "spend.json").read_bytes() == prior_spend
    fresh = json.loads((tmp_path / "continuation" / "spend.json").read_text())
    assert fresh["trial_id"] == trial.CONTINUATION_ID
    assert fresh["request_cap"] == 90
    assert fresh["usd_cap"] == "0.50"
    assert fresh["attempt_count"] == 0
    assert document_id == _approval["document_id"]


def test_continuation_does_not_restart_an_already_opened_batch(tmp_path, monkeypatch):
    _continuation_records(tmp_path, monkeypatch)
    (tmp_path / "continuation" / "serve.ready.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("JD_RELATIONAL_TEST_DB", "1")
    monkeypatch.setattr(trial, "manifest", lambda *_args: {"fixture": "offline"})
    monkeypatch.setattr(trial, "fixture_file", lambda *_args: (_ for _ in ()).throw(
        AssertionError("host_accessed")))
    monkeypatch.setattr(trial, "read_key", lambda *_args: (_ for _ in ()).throw(
        AssertionError("credential_accessed")))

    with pytest.raises(trial.TrialPreflightError, match="trial_already_served"):
        trial.serve(tmp_path, continuation=True)


def test_continuation_stop_only_writes_separate_control_file(tmp_path, monkeypatch):
    _continuation_records(tmp_path, monkeypatch)
    monkeypatch.setattr(trial, "manifest", lambda *_args: {"fixture": "offline"})
    with pytest.raises(trial.TrialPreflightError, match="continuation_not_ready"):
        trial.stop_continuation(tmp_path)

    (tmp_path / "continuation" / "serve.ready.json").write_text(json.dumps({
        "pid": 123, "status": "ready", "trial_id": trial.CONTINUATION_ID,
    }), encoding="utf-8")
    trial.stop_continuation(tmp_path)
    assert (tmp_path / "continuation" / "stop.request").is_file()
    assert (tmp_path / "stop.request").is_file() is False
