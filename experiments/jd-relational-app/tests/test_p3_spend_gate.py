from __future__ import annotations

import asyncio
from decimal import Decimal
import json
from threading import Event, Thread
from time import sleep

import httpx
import pytest

from jd_relational.openrouter_model import OPENROUTER_HEADERS
from jd_relational.role_models import create_role_models
import support.p3_spend_gate as p3_spend_gate
from support.openai_replies import reply
from support.p3_spend_gate import (
    BudgetGateError,
    GuardedAsyncClient,
    GuardedClient,
    LunaBudgetPolicy,
    P3SpendGate,
)


URL = "https://openrouter.ai/api/v1/responses"
PROVIDER = {
    "only": ["openai"],
    "order": ["openai"],
    "allow_fallbacks": False,
    "require_parameters": False,
}


def payload(*, max_tokens: int = 8192) -> dict:
    return {
        "model": "openai/gpt-6-luna",
        "input": [{"role": "user", "content": "合成測試"}],
        "max_output_tokens": max_tokens,
        "parallel_tool_calls": False,
        "provider": PROVIDER,
        "reasoning": {"effort": "high"},
        "store": False,
        "include": ["reasoning.encrypted_content"],
    }


def request(*, max_tokens: int = 8192, body: dict | None = None) -> httpx.Request:
    return httpx.Request(
        "POST",
        URL,
        json=body if body is not None else payload(max_tokens=max_tokens),
        headers={"X-OpenRouter-Metadata": "enabled"},
    )


def response(
    sent: httpx.Request,
    *,
    cost: str | None = "0.01",
    status_code: int = 200,
    provider: str = "OpenAI",
    model: str = "openai/gpt-6-luna",
    service_tier: str | None = "default",
) -> httpx.Response:
    usage = {"input_tokens": 100, "output_tokens": 20}
    if cost is not None:
        usage["cost"] = cost
    return httpx.Response(
        status_code,
        json={
            "model": model,
            "provider": provider,
            "service_tier": service_tier,
            "status": "completed",
            "error": None,
            "usage": usage,
            "output": [{"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "完成"}]}],
        },
        request=sent,
    )


def gate(tmp_path, *, cap="1.00", request_cap=180, wait_timeout=1.0):
    return P3SpendGate(
        tmp_path / "p3-spend-ledger.json",
        trial_id="p3-c-w",
        authorized=True,
        usd_cap=Decimal(cap),
        request_cap=request_cap,
        wait_timeout_seconds=wait_timeout,
    )


def test_policy_reserves_full_standard_long_context_and_role_output():
    policy = LunaBudgetPolicy()

    assert policy.reserve_for(payload(max_tokens=8192)) == Decimal("0.268644")
    assert policy.reserve_for(payload(max_tokens=32768)) == Decimal("0.287076")


@pytest.mark.parametrize("limit", [2048, 32768])
def test_role_cannot_disguise_a_different_output_limit(tmp_path, limit):
    spend = gate(tmp_path)

    with pytest.raises(BudgetGateError, match="request_role_mismatch"):
        spend.begin(request(max_tokens=limit), role="consultant")

    assert spend.snapshot()["attempt_count"] == 0


@pytest.mark.parametrize(
    "change",
    [
        lambda value: value.update(model="openai/gpt-6-terra"),
        lambda value: value.update(service_tier="flex"),
        lambda value: value.update(parallel_tool_calls=True),
        lambda value: value.update(provider={**PROVIDER, "allow_fallbacks": True}),
        lambda value: value.update(max_output_tokens=128000),
        lambda value: value.update(max_output_tokens=4096),
        lambda value: value.update(plugins=[{"id": "web"}]),
        lambda value: value.update(stream=True),
        lambda value: value.update(tools=[{"type": "web_search"}]),
    ],
)
def test_request_contract_fails_closed_before_network(tmp_path, change):
    value = payload()
    change(value)
    spend = gate(tmp_path)

    with pytest.raises(BudgetGateError, match="request_contract"):
        spend.begin(request(body=value))

    assert spend.snapshot()["attempt_count"] == 0


def test_only_one_provider_request_is_in_flight(tmp_path):
    spend = gate(tmp_path)
    first = request()
    second = request(max_tokens=32768)
    spend.begin(first)
    admitted = Event()

    def begin_second():
        spend.begin(second)
        admitted.set()

    worker = Thread(target=begin_second)
    worker.start()
    sleep(0.05)
    assert not admitted.is_set()

    spend.complete(response(first, cost="0.01"))
    assert admitted.wait(1)
    spend.complete(response(second, cost="0.02"))
    worker.join(1)

    state = spend.snapshot()
    assert state["attempt_count"] == 2
    assert state["spent_usd"] == "0.03"
    assert state["in_flight"] == []


def test_missing_cost_retains_full_reserve_and_stops(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    spend.begin(sent)
    missing_cost = response(sent, cost=None)
    missing_cost.headers["X-Generation-Id"] = "gen-unknown-cost-123"

    with pytest.raises(BudgetGateError, match="usage_cost_missing"):
        spend.complete(missing_cost)

    state = spend.snapshot()
    assert state["status"] == "stopped"
    assert state["retained_unknown_usd"] == "0.268644"
    assert state["attempts"][0]["router_generation_id"] == "gen-unknown-cost-123"
    with pytest.raises(BudgetGateError, match="usage_cost_missing"):
        spend.begin(request())


@pytest.mark.parametrize(
    "reply_options, reason",
    [
        ({"status_code": 500}, "provider_http_500"),
        ({"cost": "-0.1"}, "usage_cost_invalid"),
        ({"cost": "NaN"}, "usage_cost_invalid"),
        ({"provider": "Other"}, "provider_mismatch"),
        ({"model": "other/model"}, "provider_model_mismatch"),
        ({"service_tier": "flex"}, "provider_service_tier_mismatch"),
        ({"model": "openai/gpt-6-luna-unapproved-snapshot"}, "provider_model_mismatch"),
    ],
)
def test_unaccountable_response_stops_with_full_reserve(
    tmp_path, reply_options, reason
):
    spend = gate(tmp_path)
    sent = request()
    spend.begin(sent)

    with pytest.raises(BudgetGateError, match=reason):
        spend.complete(response(sent, **reply_options))

    state = spend.snapshot()
    assert state["status"] == "stopped"
    assert state["retained_unknown_usd"] == "0.268644"


@pytest.mark.parametrize(
    "body_model, selected_model",
    [
        ("openai/gpt-6-luna-unapproved-snapshot", "openai/gpt-6-luna-20260922"),
        ("openai/gpt-6-luna", "openai/gpt-6-luna-unapproved-snapshot"),
    ],
)
def test_rejected_reply_keeps_only_bounded_route_identity_for_diagnosis(
    tmp_path, body_model, selected_model,
):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent, model=body_model).json()
    wire["output"][0]["content"][0]["text"] = "private synthetic interview text"
    wire["openrouter_metadata"] = {"endpoints": {"available": [
        {"selected": True, "provider": "OpenAI", "model": selected_model},
    ]}}
    spend.begin(sent)

    with pytest.raises(BudgetGateError, match="provider_model_mismatch"):
        spend.complete(httpx.Response(200, json=wire, request=sent))

    state = json.loads((tmp_path / "p3-spend-ledger.json").read_text(encoding="utf-8"))
    attempt = state["attempts"][0]
    assert attempt["observed_model"] == body_model
    assert attempt["observed_selected_model"] == selected_model
    assert attempt["observed_provider"] == "OpenAI"
    assert attempt["observed_selected_provider"] == "OpenAI"
    assert attempt["observed_service_tier"] == "default"
    assert attempt["observed_cost_present"] is True
    assert state["retained_unknown_usd"] == "0.268644"
    assert "private synthetic interview text" not in json.dumps(state)


def test_conflicting_response_and_router_provider_evidence_stops(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent).json()
    wire["openrouter_metadata"] = {"endpoints": {"available": [
        {"selected": True, "provider": "Azure"},
    ]}}
    spend.begin(sent)
    with pytest.raises(BudgetGateError, match="provider_mismatch"):
        spend.complete(httpx.Response(200, json=wire, request=sent))
    assert spend.snapshot()["status"] == "stopped"


def test_selected_router_provider_is_accepted_when_top_level_is_absent(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent).json()
    wire.pop("provider")
    wire["openrouter_metadata"] = {"endpoints": {"available": [
        {"selected": True, "provider": "OpenAI"},
    ]}}
    spend.begin(sent)
    spend.complete(httpx.Response(200, json=wire, request=sent))
    assert spend.snapshot()["attempts"][0]["actual_provider"] == "OpenAI"


@pytest.mark.parametrize(
    "body_model, selected_model",
    [
        ("openai/gpt-6-luna-20260922", None),
        ("openai/gpt-6-luna", "openai/gpt-6-luna-20260922"),
    ],
)
def test_requested_luna_accepts_only_its_verified_canonical_snapshot(
    tmp_path, body_model, selected_model,
):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent, model=body_model, cost="0.0021").json()
    if selected_model is not None:
        wire["openrouter_metadata"] = {"endpoints": {"available": [
            {"selected": True, "provider": "OpenAI", "model": selected_model},
        ]}}

    spend.begin(sent)
    spend.complete(httpx.Response(200, json=wire, request=sent))

    state = spend.snapshot()
    assert state["status"] == "active"
    assert state["spent_usd"] == "0.0021"
    assert state["attempts"][0]["actual_model"] == body_model
    assert state["attempts"][0]["actual_provider"] == "OpenAI"


@pytest.mark.parametrize("status,error", [
    ("incomplete", None), ("completed", {"code": "synthetic"}),
])
def test_unfinished_responses_reply_stops_trial_after_accounting_unknown(
    tmp_path, status, error,
):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent).json()
    wire["status"] = status
    wire["error"] = error
    spend.begin(sent)
    with pytest.raises(BudgetGateError, match="provider_response_incomplete"):
        spend.complete(httpx.Response(200, json=wire, request=sent))
    assert spend.snapshot()["status"] == "stopped"


def test_incomplete_reply_records_bounded_reason_and_observed_cost_without_settling(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent, cost="0.0013058").json()
    wire["status"] = "incomplete"
    wire["incomplete_details"] = {"reason": "max_output_tokens"}
    wire["output"][0]["content"][0]["text"] = "private synthetic interview text"
    spend.begin(sent)

    with pytest.raises(BudgetGateError, match="provider_response_incomplete"):
        spend.complete(httpx.Response(200, json=wire, request=sent))

    state = json.loads((tmp_path / "p3-spend-ledger.json").read_text(encoding="utf-8"))
    attempt = state["attempts"][0]
    assert attempt["observed_status"] == "incomplete"
    assert attempt["observed_incomplete_reason"] == "max_output_tokens"
    assert attempt["observed_cost_usd"] == "0.0013058"
    assert state["spent_usd"] == "0"
    assert state["retained_unknown_usd"] == "0.268644"
    assert "private synthetic interview text" not in json.dumps(state)


@pytest.mark.parametrize("tool_count", [0, 1])
def test_admitted_request_records_only_declared_tool_count_on_incomplete_reply(
    tmp_path, tool_count,
):
    spend = gate(tmp_path)
    body = payload()
    body["input"][0]["content"] = "private synthetic interview"
    if tool_count:
        body["tools"] = [{
            "type": "function",
            "name": "synthetic_read",
            "description": "private synthetic tool description",
            "parameters": {"type": "object", "properties": {}},
        }]
    sent = request(body=body)
    wire = response(sent).json()
    wire["status"] = "incomplete"
    wire["incomplete_details"] = {"reason": "max_output_tokens"}

    spend.begin(sent, role="consultant")
    with pytest.raises(BudgetGateError, match="provider_response_incomplete"):
        spend.complete(httpx.Response(200, json=wire, request=sent))

    ledger = (tmp_path / "p3-spend-ledger.json").read_text(encoding="utf-8")
    attempt = json.loads(ledger)["attempts"][0]
    assert attempt["declared_tool_count"] == tool_count
    assert "private synthetic interview" not in ledger
    assert "private synthetic tool description" not in ledger


def test_duplicate_response_cannot_charge_or_release_twice(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    spend.begin(sent)
    provider_response = response(sent, cost="0.01")
    spend.complete(provider_response)

    with pytest.raises(BudgetGateError, match="response_not_admitted"):
        spend.complete(provider_response)

    assert spend.snapshot()["spent_usd"] == "0.01"


def test_settled_attempt_durably_records_only_actual_provider_usage_metadata(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent, cost="0.0123").json()
    wire["id"] = "resp-synthetic-123"
    wire["usage"] = {
        "input_tokens": 100,
        "output_tokens": 20,
        "total_tokens": 120,
        "cost": "0.0123",
        "input_tokens_details": {"cached_tokens": 30, "cache_write_tokens": 10},
    }
    wire["output"][0]["content"][0]["text"] = "private-model-answer"

    spend.begin(sent)
    spend.complete(httpx.Response(200, json=wire, request=sent))
    attempt = gate(tmp_path).snapshot()["attempts"][0]

    assert attempt["actual_model"] == "openai/gpt-6-luna"
    assert attempt["actual_provider"] == "OpenAI"
    assert attempt["actual_service_tier"] == "default"
    assert attempt["response_id"] == "resp-synthetic-123"
    assert attempt["input_tokens"] == 100
    assert attempt["output_tokens"] == 20
    assert attempt["total_tokens"] == 120
    assert attempt["cached_tokens"] == 30
    assert attempt["cache_write_tokens"] == 10
    assert attempt["actual_cost_usd"] == "0.0123"
    ledger_bytes = (tmp_path / "p3-spend-ledger.json").read_text(encoding="utf-8")
    assert "private-model-answer" not in ledger_bytes
    assert "合成測試" not in ledger_bytes


def test_responses_id_and_router_generation_id_are_recorded_separately(tmp_path):
    spend = gate(tmp_path)
    sent = request()
    wire = response(sent).json()
    wire["id"] = "resp-synthetic-123"

    spend.begin(sent)
    spend.complete(httpx.Response(
        200, json=wire, headers={"X-Generation-Id": "gen-synthetic-456"}, request=sent,
    ))

    attempt = spend.snapshot()["attempts"][0]
    assert attempt["response_id"] == "resp-synthetic-123"
    assert attempt["router_generation_id"] == "gen-synthetic-456"
    assert "generation_id" not in attempt


def test_ledger_write_failure_stops_the_live_gate(tmp_path, monkeypatch):
    spend = gate(tmp_path)
    sent = request()
    spend.begin(sent)

    def fail_replace(*_args):
        raise OSError("synthetic")

    monkeypatch.setattr(p3_spend_gate.os, "replace", fail_replace)
    with pytest.raises(BudgetGateError, match="ledger_persist_failed"):
        spend.complete(response(sent, cost="0.01"))

    state = spend.snapshot()
    assert state["status"] == "stopped"
    assert state["stop_reason"] == "ledger_persist_failed"
    with pytest.raises(BudgetGateError, match="ledger_persist_failed"):
        spend.begin(request())


def test_transport_failure_retains_reserve_and_restart_fails_closed(tmp_path):
    ledger = tmp_path / "p3-spend-ledger.json"
    spend = gate(tmp_path)
    sent = request(max_tokens=32768)
    spend.begin(sent)
    spend.fail(sent, "transport_unknown")

    recovered = P3SpendGate(
        ledger,
        trial_id="p3-c-w",
        authorized=True,
        usd_cap=Decimal("1.00"),
        request_cap=180,
        wait_timeout_seconds=1,
    )
    state = recovered.snapshot()
    assert state["status"] == "stopped"
    assert state["stop_reason"] == "transport_unknown"
    assert state["retained_unknown_usd"] == "0.287076"


def test_restart_turns_unsettled_request_into_unknown_and_stops(tmp_path):
    spend = gate(tmp_path)
    spend.begin(request())

    recovered = gate(tmp_path)
    state = recovered.snapshot()

    assert state["status"] == "stopped"
    assert state["stop_reason"] == "recovered_in_flight_unknown"
    assert state["retained_unknown_usd"] == "0.268644"
    assert state["in_flight"] == []


def test_request_and_dollar_caps_block_before_send(tmp_path):
    count_gate = gate(tmp_path / "count", request_cap=1)
    first = request()
    count_gate.begin(first)
    count_gate.complete(response(first, cost="0"))
    with pytest.raises(BudgetGateError, match="request_cap"):
        count_gate.begin(request())

    cost_gate = gate(tmp_path / "cost", cap="0.28")
    first = request()
    cost_gate.begin(first)
    cost_gate.complete(response(first, cost="0.02"))
    with pytest.raises(BudgetGateError, match="usd_cap"):
        cost_gate.begin(request())
    assert cost_gate.snapshot()["attempt_count"] == 1


def test_guarded_sync_client_accounts_real_wire_and_exception(tmp_path):
    spend = gate(tmp_path / "success")
    observed = []

    def handler(sent):
        observed.append(json.loads(sent.content))
        return response(sent, cost="0.0123")

    with GuardedClient(
        spend,
        transport=httpx.MockTransport(handler),
        headers={"X-OpenRouter-Metadata": "enabled"},
    ) as client:
        result = client.post(URL, json=payload())

    assert result.status_code == 200
    assert observed == [payload()]
    assert spend.snapshot()["spent_usd"] == "0.0123"

    failed = gate(tmp_path / "failure")

    def broken(sent):
        raise httpx.ReadError("synthetic", request=sent)

    with GuardedClient(
        failed,
        transport=httpx.MockTransport(broken),
        headers={"X-OpenRouter-Metadata": "enabled"},
    ) as client:
        with pytest.raises(httpx.ReadError):
            client.post(URL, json=payload())
    assert failed.snapshot()["retained_unknown_usd"] == "0.268644"


def test_guarded_sync_client_rejects_per_send_redirect_override_before_network(tmp_path):
    spend = gate(tmp_path)
    sent_urls = []

    def handler(sent):
        sent_urls.append(str(sent.url))
        return httpx.Response(307, headers={"location": "https://elsewhere.invalid/"}, request=sent)

    with GuardedClient(spend, transport=httpx.MockTransport(handler),
                       follow_redirects=False) as client:
        with pytest.raises(BudgetGateError, match="request_contract_redirect_override"):
            client.send(request(), follow_redirects=True)

    assert sent_urls == []
    assert spend.snapshot()["attempt_count"] == 0


def test_guarded_async_client_rejects_per_send_redirect_override_before_network(tmp_path):
    spend = gate(tmp_path)
    sent_urls = []

    async def handler(sent):
        sent_urls.append(str(sent.url))
        return httpx.Response(307, headers={"location": "https://elsewhere.invalid/"}, request=sent)

    async def run():
        async with GuardedAsyncClient(spend, transport=httpx.MockTransport(handler),
                                      follow_redirects=False) as client:
            with pytest.raises(BudgetGateError, match="request_contract_redirect_override"):
                await client.send(request(), follow_redirects=True)

    asyncio.run(run())
    assert sent_urls == []
    assert spend.snapshot()["attempt_count"] == 0


def test_guarded_async_client_uses_the_same_gate(tmp_path):
    spend = gate(tmp_path)

    async def run():
        async def handler(sent):
            return response(sent, cost="0.0042")

        async with GuardedAsyncClient(
            spend,
            transport=httpx.MockTransport(handler),
            headers={"X-OpenRouter-Metadata": "enabled"},
        ) as client:
            return await client.post(URL, json=payload(max_tokens=32768))

    result = asyncio.run(run())
    assert result.status_code == 200
    assert spend.snapshot()["spent_usd"] == "0.0042"


def test_authorization_is_required_even_for_a_valid_request(tmp_path):
    spend = P3SpendGate(
        tmp_path / "ledger.json",
        trial_id="p3-c-w",
        authorized=False,
        usd_cap=Decimal("1.00"),
        request_cap=180,
        wait_timeout_seconds=1,
    )

    with pytest.raises(BudgetGateError, match="not_authorized"):
        spend.begin(request())


def test_formal_a_b1_b2_factory_uses_the_same_guarded_wire(tmp_path):
    spend = gate(tmp_path)
    costs = iter(("0.001", "0.002", "0.003", "0.004", "0.005"))
    observed_limits = []

    def handler(sent):
        observed_limits.append(json.loads(sent.content)["max_output_tokens"])
        body = reply(f"p3-{len(observed_limits)}")
        body["model"] = "openai/gpt-6-luna"
        body["provider"] = "OpenAI"
        body["service_tier"] = "default"
        body["usage"]["cost"] = next(costs)
        return httpx.Response(200, json=body, request=sent)

    transport = httpx.MockTransport(handler)
    with GuardedClient(
        spend,
        transport=transport,
        trust_env=False,
        headers=OPENROUTER_HEADERS,
    ) as client:
        async_client = GuardedAsyncClient(
            spend,
            transport=transport,
            trust_env=False,
            headers=OPENROUTER_HEADERS,
        )
        try:
            roles = create_role_models(
                api_key="synthetic-openrouter-not-a-key",
                http_client=client,
                async_http_client=async_client,
            )
            for model in (roles.consultant, roles.case, roles.understanding):
                model.invoke("合成輸入")
            roles.consultant.invoke("合成摘要", max_tokens=8192)
            roles.case.invoke("合成背景摘要", max_tokens=8192)
        finally:
            asyncio.run(async_client.aclose())

    assert observed_limits == [8192, 32768, 32768, 8192, 8192]
    state = spend.snapshot()
    assert state["attempt_count"] == 5
    assert state["spent_usd"] == "0.015"
    assert state["status"] == "active"
