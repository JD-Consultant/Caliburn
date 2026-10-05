"""Offline outbound boundaries; synthetic HTTP only, no credentials or database."""

import json
from decimal import Decimal

import httpx2
import pytest
import study_guard
from caliburn.adapters.openai_responses import ResponseRequest, compaction_payload
from openai import AsyncOpenAI
from study_guard import ResearchStop, StudyGuard


def model_request():
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="合成研究指引",
        input_items=[{"role": "user", "content": "合成原話"}],
        tools=[],
        reasoning_effort="high",
        max_output_tokens=16_384,
    )


def frozen_policy():
    return {
        "model": "gpt-6-luna",
        "effort": "high",
        "max_output_tokens": 16384,
        "instructions": dict.fromkeys(("raw", "summary", "memory"), "合成研究指引"),
        "tools": {arm: [] for arm in ("raw", "summary", "memory")},
        "schedule": [
            {"arm": arm, "case_id": case}
            for arm in ("raw", "summary", "memory")
            for case in ("c01", "c02")
        ],
    }


def prepared_guard(output_dir, *, batch_usd, seconds, prior_usd=Decimal("1.322929315")):
    guard = StudyGuard(output_dir, batch_usd=batch_usd, seconds=seconds, prior_usd=prior_usd)
    guard.frozen_policy = frozen_policy()
    guard.phase = {"arm": "raw", "case_id": "c01"}
    return guard


def outbound(path, payload):
    return httpx2.Request("POST", "https://api.openai.com/v1/responses" + path, json=payload)


def usage_payload():
    return {
        "input_tokens": 1000,
        "input_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 100},
        "output_tokens": 400,
        "output_tokens_details": {"reasoning_tokens": 150},
        "total_tokens": 1400,
    }


def response_payload():
    return {
        "id": "resp_synthetic",
        "object": "response",
        "created_at": 1,
        "model": "gpt-6-luna",
        "service_tier": "default",
        "status": "completed",
        "output": [{"type": "reasoning", "encrypted_content": "private-response-opaque"}],
        "usage": usage_payload(),
    }


async def counted(guard, request=None, tokens=1000):
    request = request or model_request()
    wire = outbound("/input_tokens", request.count_payload())
    await guard.request(wire)
    await guard.response(
        httpx2.Response(
            200, request=wire, json={"object": "response.input_tokens", "input_tokens": tokens}
        )
    )
    return request


@pytest.mark.asyncio
async def test_generation_without_exact_remote_count_stops_before_dispatch(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    with pytest.raises(ResearchStop, match="missing_count"):
        await guard.request(outbound("", model_request().create_payload()))
    assert guard.summary()["outbound_calls"] == 0


@pytest.mark.asyncio
async def test_count_reservation_is_durable_before_transport_and_separate_from_usage(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    guard.phase = {"arm": "raw", "case_id": "c01"}

    def respond(request):
        records = [json.loads(line) for line in (tmp_path / "trace.jsonl").read_text().splitlines()]
        record = records[-1]
        assert record["event"] == "request"
        assert record["arm"] == "raw" and record["case_id"] == "c01"
        assert Decimal(record["accounting"]["batch_occupied_usd"]) == Decimal("0.0001")
        return httpx2.Response(200, json={"object": "response.input_tokens", "input_tokens": 1000})

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(respond),
        event_hooks={"request": [guard.request], "response": [guard.response]},
    ) as client:
        await client.send(outbound("/input_tokens", model_request().count_payload()))
    summary = guard.summary()
    assert summary["count_calls"] == 1
    assert summary["input_tokens"] == 0
    assert Decimal(summary["count_estimated_usd"]) == Decimal("0.0001")
    assert Decimal(summary["cumulative_occupied_usd"]) == Decimal("1.323029315")


@pytest.mark.asyncio
async def test_known_usage_settles_reserve_without_double_charging_reasoning(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    wire = outbound("", (await counted(guard)).create_payload())
    await guard.request(wire)
    assert Decimal(guard.summary()["pending_reserved_usd"]) == Decimal("0.008317")
    await guard.response(httpx2.Response(200, request=wire, json=response_payload()))
    summary = guard.summary()
    assert summary["input_tokens"] == 1000
    assert summary["output_tokens"] == 400
    assert summary["reasoning_tokens"] == 150
    assert summary["cached_input_tokens"] == 200
    assert summary["cache_write_input_tokens"] == 100
    assert summary["total_tokens"] == 1400
    assert Decimal(summary["actual_estimated_usd"]) == Decimal("0.000284500")
    assert Decimal(summary["batch_occupied_usd"]) == Decimal("0.000384500")
    assert Decimal(summary["pending_reserved_usd"]) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"instructions": "different"}, "unapproved_request"),
        ({"input": [{"role": "user", "content": "another arm"}]}, "missing_count"),
        (
            {"tools": [{"type": "function", "name": "another_tool", "parameters": {}}]},
            "unapproved_request",
        ),
    ],
)
async def test_count_must_match_instructions_tools_and_input(tmp_path, change, reason):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    request = await counted(guard)
    with pytest.raises(ResearchStop, match=reason):
        await guard.request(outbound("", {**request.create_payload(), **change}))
    assert guard.summary()["outbound_calls"] == 1


@pytest.mark.asyncio
async def test_counts_are_scoped_to_the_arm_and_case_that_obtained_them(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    guard.phase = {"arm": "raw", "case_id": "c01"}
    request = await counted(guard)
    guard.phase = {"arm": "summary", "case_id": "c01"}
    with pytest.raises(ResearchStop, match="missing_count"):
        await guard.request(outbound("", request.create_payload()))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com.evil.invalid/v1/responses/input_tokens",
        "http://api.openai.com/v1/responses/input_tokens",
        "https://api.openai.com:444/v1/responses/input_tokens",
        "https://user@api.openai.com/v1/responses/input_tokens",
        "https://api.openai.com/v1/responses/input_tokens?route=other",
        "https://api.openai.com/v1/chat/completions",
    ],
)
async def test_unapproved_endpoint_never_occupies_or_dispatches(tmp_path, url):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    with pytest.raises(ResearchStop, match="unapproved_endpoint"):
        await guard.request(httpx2.Request("POST", url, json=model_request().count_payload()))
    assert guard.summary()["outbound_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"model": "gpt-6-sol"},
        {"reasoning": {"effort": "low"}},
        {"max_output_tokens": 20_000},
        {"store": True},
        {"stream": True},
        {"background": True},
        {"service_tier": "priority"},
        {"truncation": "auto"},
        {"previous_response_id": "resp_other"},
        {"context_management": [{}]},
        {"tools": [{"type": "web_search"}]},
    ],
)
async def test_unapproved_generation_contract_is_rejected_before_count_lookup(tmp_path, change):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    with pytest.raises(ResearchStop, match="unapproved_request"):
        await guard.request(outbound("", {**model_request().create_payload(), **change}))
    assert guard.summary()["outbound_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("batch", "prior"),
    [
        ("0.00005", "0"),
        ("0.5", "1.99995"),
    ],
)
async def test_both_budget_boundaries_include_count_estimates(tmp_path, batch, prior):
    guard = prepared_guard(tmp_path, batch_usd=Decimal(batch), prior_usd=Decimal(prior), seconds=60)
    with pytest.raises(ResearchStop, match="budget_limit"):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))
    assert guard.summary()["outbound_calls"] == 0


@pytest.mark.asyncio
async def test_generation_reservation_cannot_cross_batch_limit(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.0084"), seconds=60)
    request = await counted(guard)
    with pytest.raises(ResearchStop, match="budget_limit"):
        await guard.request(outbound("", request.create_payload()))
    assert guard.summary()["outbound_calls"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "usage",
    [
        None,
        {},
        {**usage_payload(), "input_tokens_details": {"cached_tokens": 200}},
        {**usage_payload(), "output_tokens_details": {"reasoning_tokens": 401}},
        {**usage_payload(), "input_tokens": True},
        {**usage_payload(), "total_tokens": 1401},
        {
            **usage_payload(),
            "input_tokens_details": {"cached_tokens": 1001, "cache_write_tokens": 0},
        },
    ],
)
async def test_unknown_usage_retains_reservation_and_permanently_stops(tmp_path, usage):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    wire = outbound("", (await counted(guard)).create_payload())
    await guard.request(wire)
    before = guard.summary()["batch_occupied_usd"]
    with pytest.raises(ResearchStop, match="unknown_usage"):
        await guard.response(
            httpx2.Response(200, request=wire, json={**response_payload(), "usage": usage})
        )
    assert guard.summary()["batch_occupied_usd"] == before
    assert guard.summary()["input_tokens"] == 0
    with pytest.raises(ResearchStop):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))
    assert guard.summary()["outbound_calls"] == 2


@pytest.mark.asyncio
async def test_http_error_bypasses_sdk_retries_and_keeps_unknown_charge(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    request = await counted(guard)
    dispatched = []

    def respond(wire):
        dispatched.append(wire)
        return httpx2.Response(429, json={"error": {"message": "synthetic failure"}})

    async with AsyncOpenAI(
        api_key="synthetic-never-a-credential",
        max_retries=2,
        http_client=httpx2.AsyncClient(
            transport=httpx2.MockTransport(respond),
            event_hooks={"request": [guard.request], "response": [guard.response]},
        ),
    ) as client:
        with pytest.raises(ResearchStop, match="provider_http_failure"):
            await client.responses.create(**request.create_payload())
    assert len(dispatched) == 1
    assert Decimal(guard.summary()["pending_reserved_usd"]) == Decimal("0.008317")
    assert not issubclass(ResearchStop, Exception)


@pytest.mark.asyncio
async def test_missing_response_blocks_the_next_send_in_any_arm(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    request = await counted(guard)
    await guard.request(outbound("", request.create_payload()))
    guard.phase = {"arm": "memory", "case_id": "c02"}
    with pytest.raises(ResearchStop, match="unsettled_prior_request"):
        await guard.request(outbound("/input_tokens", request.count_payload()))
    assert guard.summary()["outbound_calls"] == 2


@pytest.mark.asyncio
async def test_compact_reserves_full_output_allowance_after_counting_whole_window(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    request = await counted(guard)
    wire = outbound(
        "/compact",
        compaction_payload(model="gpt-6-luna", input_items=request.create_payload()["input"]),
    )
    await guard.request(wire)
    assert Decimal(guard.summary()["pending_reserved_usd"]) == Decimal("0.064125")
    payload = {
        "id": "cmp_synthetic",
        "created_at": 1,
        "object": "response.compaction",
        "output": [
            {"role": "user", "content": "retained"},
            {"type": "compaction", "encrypted_content": "private-compact"},
        ],
        "usage": usage_payload(),
    }
    response = httpx2.Response(200, request=wire, json=payload)
    await guard.response(response)
    assert response.json() == payload
    assert guard.summary()["compaction_calls"] == 1
    assert guard.summary()["input_tokens"] == 1000


@pytest.mark.asyncio
async def test_compact_cannot_reuse_count_for_a_pruned_window(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    await counted(guard)
    with pytest.raises(ResearchStop, match="missing_count"):
        await guard.request(
            outbound("/compact", compaction_payload(model="gpt-6-luna", input_items=[]))
        )


@pytest.mark.asyncio
async def test_trace_hashes_opaque_fields_omits_headers_and_pins_response_phase(tmp_path):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    guard.phase = {"arm": "memory", "case_id": "c01"}
    request = model_request().create_payload()
    request["input"].insert(0, {"type": "reasoning", "encrypted_content": "private-input-opaque"})
    model = await counted(guard, ResponseRequest.from_snapshot(request))
    wire = outbound("", model.create_payload())
    wire.headers["Authorization"] = "Bearer synthetic-header-secret"
    await guard.request(wire)
    guard.phase = {"arm": "raw", "case_id": "c02"}
    await guard.response(httpx2.Response(200, request=wire, json=response_payload()))
    trace = (tmp_path / "trace.jsonl").read_text(encoding="utf-8")
    assert "private-input-opaque" not in trace and "private-response-opaque" not in trace
    assert "synthetic-header-secret" not in trace
    records = [json.loads(line) for line in trace.splitlines()]
    sent = next(r for r in records if r["event"] == "request" and r["path"] == "/v1/responses")
    assert len(sent["payload"]["input"][0]["encrypted_content"]["sha256"]) == 64
    received = [r for r in records if r["event"] == "response"][-1]
    assert received["arm"] == "memory" and received["case_id"] == "c01"
    assert received["timestamp"] and received["duration_seconds"] >= 0
    assert wire.content == json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()


@pytest.mark.asyncio
async def test_elapsed_deadline_and_outbound_limit_stop_future_sends(tmp_path, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(study_guard.time, "monotonic", lambda: clock[0])
    guard = prepared_guard(tmp_path / "time", batch_usd=Decimal("0.5"), seconds=1)
    clock[0] = 1.0
    with pytest.raises(ResearchStop, match="time_limit"):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))
    monkeypatch.setattr(study_guard, "MAX_OUTBOUND_CALLS", 1)
    guard = prepared_guard(tmp_path / "calls", batch_usd=Decimal("0.5"), seconds=60)
    await counted(guard)
    with pytest.raises(ResearchStop, match="call_limit"):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))


@pytest.mark.asyncio
async def test_journal_failure_stops_before_transport_can_send(tmp_path, monkeypatch):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)

    def cannot_flush(fd):
        raise OSError("synthetic disk failure")

    monkeypatch.setattr(study_guard.os, "fsync", cannot_flush)
    with pytest.raises(ResearchStop, match="journal_failure"):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))
    with pytest.raises(ResearchStop):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))


def test_existing_journal_cannot_silently_restart_allowance(tmp_path):
    StudyGuard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    with pytest.raises(ResearchStop, match="existing_journal"):
        StudyGuard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)


@pytest.mark.asyncio
async def test_missing_frozen_policy_stops_even_count_dispatch(tmp_path):
    guard = StudyGuard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    guard.phase = {"arm": "raw", "case_id": "c01"}
    with pytest.raises(ResearchStop, match="missing_frozen_policy"):
        await guard.request(outbound("/input_tokens", model_request().count_payload()))
    assert guard.summary()["outbound_calls"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "change",
    [
        {"instructions": "different"},
        {"tools": [{"type": "function", "name": "extra_tool", "parameters": {}}]},
    ],
)
async def test_even_a_matching_count_cannot_authorize_unfrozen_prompt_or_tools(tmp_path, change):
    guard = prepared_guard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    with pytest.raises(ResearchStop, match="unapproved_request"):
        await guard.request(
            outbound("/input_tokens", {**model_request().count_payload(), **change})
        )
    assert guard.summary()["outbound_calls"] == 0


@pytest.mark.asyncio
async def test_frozen_manifest_is_copied_and_cannot_be_reassigned(tmp_path):
    guard = StudyGuard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    manifest = frozen_policy()
    guard.frozen_policy = manifest
    guard.phase = {"arm": "raw", "case_id": "c01"}
    manifest["instructions"]["raw"] = "mutated after assignment"
    await counted(guard)
    with pytest.raises(ValueError, match="already assigned"):
        guard.frozen_policy = manifest


@pytest.mark.asyncio
async def test_frozen_policy_selects_the_current_arm_and_rejects_unscheduled_case(tmp_path):
    guard = StudyGuard(tmp_path, batch_usd=Decimal("0.5"), seconds=60)
    manifest = frozen_policy()
    manifest["instructions"]["memory"] = "memory-specific instructions"
    guard.frozen_policy = manifest
    guard.phase = {"arm": "memory", "case_id": "c01"}
    snapshot = {**model_request().create_payload(), "instructions": "memory-specific instructions"}
    request = await counted(guard, ResponseRequest.from_snapshot(snapshot))
    wire = outbound("", request.create_payload())
    await guard.request(wire)
    await guard.response(httpx2.Response(200, request=wire, json=response_payload()))
    guard.phase = {"arm": "memory", "case_id": "not-in-manifest"}
    with pytest.raises(ResearchStop, match="unapproved_request"):
        await guard.request(outbound("/input_tokens", request.count_payload()))
    assert guard.summary()["outbound_calls"] == 2
