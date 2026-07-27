"""Segment 2 測試：request 精確性、單次 HTTP、route facts、redaction、manifest。

**全部 mocked HTTP，沒有任何真實網路請求**（設計 §12.1 第 7–11 項）。
真實 provider 只會在 Segment 4 的 disposable live preflight 出現，且需 owner 核准。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest

from capture import (
    REDACTED_REASONING,
    REDACTED_SECRET,
    TrialCapture,
    contains_secret_or_reasoning,
    load_manifest,
    redact,
    verify_manifest,
)
from provider_request import (
    DISABLED_PLUGINS,
    ProviderConfig,
    build_chat_request,
    validate_config,
    verify_request_is_exact,
)
from routing_facts import (
    CACHE_STATUS_HEADER,
    LIMITATION_CACHE_REPLAY,
    LIMITATION_METADATA_MISSING,
    LIMITATION_MODEL_MISMATCH,
    LIMITATION_ROUTER_RETRIED,
    LIMITATION_SELECTED_NOT_UNIQUE,
    normalize_route_facts,
)
from transport import (
    OUTCOME_HTTP_ERROR,
    OUTCOME_INVALID_JSON,
    OUTCOME_OK,
    OUTCOME_REQUEST_REJECTED,
    OUTCOME_TRANSPORT_ERROR,
    build_client,
    send_once,
)

MODEL = "openai/gpt-5.6-sol-pro"


@pytest.fixture()
def config() -> ProviderConfig:
    return ProviderConfig(
        requested_model=MODEL,
        provider_only=("openai",),
        provider_order=("openai",),
        reasoning_effort="high",
    )


@pytest.fixture()
def schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["analysis_decision"],
        "properties": {"analysis_decision": {"type": "string"}},
    }


@pytest.fixture()
def request_obj(config: ProviderConfig, schema: dict[str, Any]):
    return build_chat_request(
        config,
        system_instruction="你是受測的職務分析模型。",
        user_content="員工說：我平常用 Java 開發。",
        output_schema=schema,
        schema_name="r1_task_review",
        max_output_tokens=2048,
    )


def _checks(result) -> list[str]:
    return [f.check for f in result.findings]


# --- §12.1 第 7 項：request body exact routing ------------------------------------


def test_config_validates(config: ProviderConfig) -> None:
    assert validate_config(config).ok


@pytest.mark.parametrize(
    "slug",
    ["openai/gpt-auto", "openai/gpt-5.6-sol-pro:free", "openai/gpt-latest", "openai/x:nitro",
     "openai/x:floor", "not-a-slug"],
)
def test_config_rejects_floating_slugs(config: ProviderConfig, slug: str) -> None:
    bad = ProviderConfig(**{**config.__dict__, "requested_model": slug})
    assert "model_slug" in _checks(validate_config(bad))


def test_config_rejects_multiple_upstreams(config: ProviderConfig) -> None:
    bad = ProviderConfig(
        **{**config.__dict__, "provider_only": ("openai", "azure"), "provider_order": ("openai", "azure")}
    )
    assert "provider_pinning" in _checks(validate_config(bad))


def test_config_rejects_order_differing_from_only(config: ProviderConfig) -> None:
    bad = ProviderConfig(**{**config.__dict__, "provider_order": ("azure",)})
    assert "provider_pinning" in _checks(validate_config(bad))


def test_request_body_pins_route_and_disables_fallback(request_obj) -> None:
    body = request_obj.body
    assert body["provider"]["allow_fallbacks"] is False
    assert body["provider"]["require_parameters"] is True
    assert body["provider"]["only"] == ["openai"] == body["provider"]["order"]
    assert body["stream"] is False
    assert body["model"] == MODEL


def test_request_body_uses_strict_json_schema(request_obj) -> None:
    fmt = request_obj.body["response_format"]
    assert fmt["type"] == "json_schema"
    assert fmt["json_schema"]["strict"] is True


def test_request_body_disables_every_plugin(request_obj) -> None:
    plugins = request_obj.body["plugins"]
    assert {p["id"] for p in plugins} == set(DISABLED_PLUGINS)
    assert all(p["enabled"] is False for p in plugins)


def test_request_body_excludes_reasoning_content(request_obj) -> None:
    assert request_obj.body["reasoning"]["exclude"] is True


def test_request_body_has_no_tools_or_preset(request_obj) -> None:
    for key in ("tools", "tool_choice", "preset", "route", "models", "transforms", "store"):
        assert key not in request_obj.body


def test_exactness_check_passes_on_built_request(request_obj) -> None:
    assert verify_request_is_exact(request_obj.body).ok


@pytest.mark.parametrize(
    "mutate,expected",
    [
        (lambda b: b["provider"].__setitem__("allow_fallbacks", True), "provider_pinning"),
        (lambda b: b["provider"].__setitem__("require_parameters", False), "provider_pinning"),
        (lambda b: b["provider"].__setitem__("only", ["openai", "azure"]), "provider_pinning"),
        (lambda b: b.__setitem__("stream", True), "request_shape"),
        (lambda b: b.__setitem__("tools", [{"type": "function"}]), "request_shape"),
        (lambda b: b.__setitem__("preset", "fast"), "request_shape"),
        (lambda b: b["response_format"]["json_schema"].__setitem__("strict", False), "structured_output"),
        (lambda b: b.__setitem__("plugins", [{"id": "web", "enabled": True}]), "plugins"),
        (lambda b: b.__setitem__("reasoning", {"effort": "high"}), "reasoning"),
    ],
)
def test_exactness_check_catches_each_relaxation(request_obj, mutate, expected) -> None:
    body = json.loads(json.dumps(request_obj.body))
    mutate(body)
    assert expected in _checks(verify_request_is_exact(body))


# --- §12.1 第 8 項：每個 attempt 只有一次 HTTP ------------------------------------


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_success_issues_exactly_one_http_call(request_obj) -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "{}"}}], "usage": {"prompt_tokens": 10}},
            headers={CACHE_STATUS_HEADER: "MISS"},
        )

    async with _client(handler) as client:
        result = await send_once(client, request_obj, api_key="sk-test")

    assert len(calls) == 1
    assert result.outcome == OUTCOME_OK
    assert result.attempt_count == 1
    assert result.is_quality_sample


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [429, 500, 502, 503])
async def test_http_error_does_not_retry(request_obj, status: int) -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        return httpx.Response(status, text="upstream unhappy")

    async with _client(handler) as client:
        result = await send_once(client, request_obj, api_key="sk-test")

    assert len(calls) == 1, "同一個 attempt 內不得重試"
    assert result.outcome == OUTCOME_HTTP_ERROR
    assert result.status_code == status
    assert not result.is_quality_sample


@pytest.mark.asyncio
async def test_timeout_does_not_retry(request_obj) -> None:
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append(req)
        raise httpx.ConnectTimeout("timed out", request=req)

    async with _client(handler) as client:
        result = await send_once(client, request_obj, api_key="sk-test")

    assert len(calls) == 1
    assert result.outcome == OUTCOME_TRANSPORT_ERROR
    assert not result.is_quality_sample


@pytest.mark.asyncio
async def test_invalid_json_is_its_own_outcome(request_obj) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json at all")

    async with _client(handler) as client:
        result = await send_once(client, request_obj, api_key="sk-test")

    assert result.outcome == OUTCOME_INVALID_JSON
    assert result.raw_text == "not json at all"


@pytest.mark.asyncio
async def test_inexact_request_is_never_sent(request_obj) -> None:
    """請求不合 §8.3 就在送出前擋下，一次 HTTP 都不發。"""
    calls: list[httpx.Request] = []

    def handler(req: httpx.Request) -> httpx.Response:  # pragma: no cover - 不該被呼叫
        calls.append(req)
        return httpx.Response(200, json={})

    request_obj.body["provider"]["allow_fallbacks"] = True
    async with _client(handler) as client:
        result = await send_once(client, request_obj, api_key="sk-test")

    assert calls == []
    assert result.outcome == OUTCOME_REQUEST_REJECTED


@pytest.mark.asyncio
async def test_api_key_never_appears_in_the_wire_result(request_obj) -> None:
    def handler(req: httpx.Request) -> httpx.Response:
        assert req.headers["Authorization"] == "Bearer sk-secret"
        return httpx.Response(200, json={"usage": {}})

    async with _client(handler) as client:
        result = await send_once(client, request_obj, api_key="sk-secret")

    assert "sk-secret" not in json.dumps(result.headers)
    assert "sk-secret" not in (result.raw_text or "")


def test_build_client_disables_redirects_and_uses_explicit_transport() -> None:
    client = build_client(30.0)
    try:
        assert client.follow_redirects is False
        assert isinstance(client._transport, httpx.AsyncHTTPTransport)
    finally:
        client._transport.__class__  # noqa: B018 - 只做型別確認，不發任何請求


def test_usage_cost_is_decimal_normalized(request_obj) -> None:
    from transport import _normalize_usage

    usage = _normalize_usage({"usage": {"cost": 0.0000123, "prompt_tokens": 5}})
    assert usage.cost == "0.0000123"
    assert usage.prompt_tokens == 5


def test_usage_missing_is_a_limitation_not_a_crash() -> None:
    from transport import _normalize_usage

    assert _normalize_usage({}).limitations


# --- §12.1 第 9 項：resolved route 只能由 response metadata 取得 -------------------


def _nested_metadata(model: str = MODEL, attempt: int = 1) -> dict[str, Any]:
    return {
        "requested": model,
        "attempt": attempt,
        "endpoints": {
            "selected": {"provider": "openai", "model": model},
            "available": [{"provider": "openai", "model": model, "selected": True}],
        },
    }


def test_nested_metadata_yields_resolved_route() -> None:
    facts = normalize_route_facts(
        _nested_metadata(), headers={CACHE_STATUS_HEADER: "MISS"}, requested_model=MODEL
    )
    assert facts.resolved_model == MODEL
    assert facts.resolved_provider == "openai"
    assert facts.usable


def test_legacy_flat_metadata_still_readable() -> None:
    metadata = {"endpoints": [{"provider": "openai", "model": MODEL, "selected": True}]}
    facts = normalize_route_facts(metadata, headers={CACHE_STATUS_HEADER: "MISS"})
    assert facts.resolved_model == MODEL


def test_missing_metadata_never_falls_back_to_the_request() -> None:
    """ADR 0040 決定 22：resolved 事實不得由 request 推斷。"""
    facts = normalize_route_facts(None, headers={CACHE_STATUS_HEADER: "MISS"}, requested_model=MODEL)
    assert facts.resolved_model is None
    assert LIMITATION_METADATA_MISSING in facts.limitations
    assert not facts.usable


def test_ambiguous_selection_is_fail_closed() -> None:
    metadata = {
        "endpoints": {
            "available": [
                {"provider": "openai", "model": MODEL, "selected": True},
                {"provider": "azure", "model": MODEL, "selected": True},
            ]
        }
    }
    facts = normalize_route_facts(metadata, headers={CACHE_STATUS_HEADER: "MISS"})
    assert LIMITATION_SELECTED_NOT_UNIQUE in facts.limitations
    assert facts.resolved_model is None


def test_cache_hit_marks_the_trial_as_replay() -> None:
    facts = normalize_route_facts(_nested_metadata(), headers={CACHE_STATUS_HEADER: "HIT"})
    assert LIMITATION_CACHE_REPLAY in facts.limitations
    assert not facts.usable


def test_router_retry_is_flagged() -> None:
    facts = normalize_route_facts(
        _nested_metadata(attempt=2), headers={CACHE_STATUS_HEADER: "MISS"}
    )
    assert LIMITATION_ROUTER_RETRIED in facts.limitations


def test_resolved_model_mismatch_is_flagged() -> None:
    facts = normalize_route_facts(
        _nested_metadata(model="openai/gpt-5.6-luna-pro"),
        headers={CACHE_STATUS_HEADER: "MISS"},
        requested_model=MODEL,
    )
    assert LIMITATION_MODEL_MISMATCH in facts.limitations


def test_unknown_cache_header_is_not_silently_accepted() -> None:
    facts = normalize_route_facts(_nested_metadata(), headers={CACHE_STATUS_HEADER: "MAYBE"})
    assert facts.limitations


@pytest.mark.parametrize("metadata", [123, "text", [], True])
def test_malformed_metadata_never_raises(metadata) -> None:
    facts = normalize_route_facts(metadata)
    assert not facts.usable


# --- §12.1 第 10 項：secret／reasoning 不進 capture --------------------------------


def test_redact_masks_authorization_and_reasoning() -> None:
    payload = {
        "headers": {"Authorization": "Bearer sk-live", "Content-Type": "application/json"},
        "choices": [{"message": {"content": "{}", "reasoning": "先想了很久"}}],
    }
    safe = redact(payload)
    assert safe["headers"]["Authorization"] == REDACTED_SECRET
    assert safe["choices"][0]["message"]["reasoning"] == REDACTED_REASONING
    assert safe["headers"]["Content-Type"] == "application/json"
    assert not contains_secret_or_reasoning(safe)
    assert "sk-live" not in json.dumps(safe, ensure_ascii=False)


def test_detector_flags_unredacted_payload() -> None:
    assert contains_secret_or_reasoning({"api_key": "sk-live"})
    assert contains_secret_or_reasoning({"a": [{"reasoning_content": "chain"}]})


def test_capture_write_redacts_before_touching_disk(tmp_path: Path) -> None:
    capture = TrialCapture(tmp_path / "trial-001")
    capture.write(
        "request-final.json",
        {"headers": {"Authorization": "Bearer sk-live"}, "body": {"model": MODEL}},
    )
    written = (tmp_path / "trial-001" / "request-final.json").read_text(encoding="utf-8")
    assert "sk-live" not in written
    assert REDACTED_SECRET in written


def test_capture_is_immutable(tmp_path: Path) -> None:
    capture = TrialCapture(tmp_path / "trial-002")
    capture.write("response-final.json", {"ok": True})
    with pytest.raises(ValueError):
        capture.write("response-final.json", {"ok": False})


# --- §12.1 第 11 項：Trial Manifest 可驗 refs、版本與 hash -------------------------


def _manifest(files: dict[str, str], **overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "case_id": "TI-R1-01",
        "case_revision": 1,
        "case_family_id": "TI-R1-01",
        "source_type": "constructed_edge",
        "suite_hash": "6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7",
        "arm": "A6",
        "round": 1,
        "attempt": 1,
        "prompt_version": "r1-prompt-1",
        "schema_hash": "abc",
        "context_assembler_version": "r1-context-1",
        "requested_model": MODEL,
        "resolved_model": MODEL,
        "resolved_provider": "openai",
        "provider_config_hash": "def",
        "files": files,
        "outcomes": {"transport": "ok", "parse": "ok", "local_verifier": "ok"},
        "usage": {"prompt_tokens": 10},
        "latency_ms": 1234,
        "limitations": [],
    }
    base.update(overrides)
    return base


def test_manifest_round_trips_and_validates(tmp_path: Path) -> None:
    capture = TrialCapture(tmp_path / "trial-003")
    digest = capture.write("response-final.json", {"choices": []})
    manifest = _manifest({"response-final.json": digest})

    capture.write_manifest(manifest)
    loaded = load_manifest(capture.directory)
    assert verify_manifest(loaded, capture).ok


def test_manifest_detects_tampered_file_hash(tmp_path: Path) -> None:
    capture = TrialCapture(tmp_path / "trial-004")
    capture.write("response-final.json", {"choices": []})
    manifest = _manifest({"response-final.json": "0" * 64})
    assert "manifest_refs" in _checks(verify_manifest(manifest, capture))


def test_manifest_detects_reference_to_missing_file(tmp_path: Path) -> None:
    capture = TrialCapture(tmp_path / "trial-005")
    digest = capture.write("response-final.json", {"choices": []})
    manifest = _manifest({"response-final.json": digest, "ghost.json": "x"})
    assert "manifest_refs" in _checks(verify_manifest(manifest, capture))


@pytest.mark.parametrize("missing", ["suite_hash", "resolved_model", "provider_config_hash", "files"])
def test_manifest_requires_every_mandatory_field(missing: str) -> None:
    manifest = _manifest({})
    del manifest[missing]
    assert "manifest_shape" in _checks(verify_manifest(manifest))


def test_manifest_rejects_missing_resolved_model_on_success() -> None:
    manifest = _manifest({}, resolved_model=None)
    assert "resolved_route" in _checks(verify_manifest(manifest))


def test_manifest_rejects_unredacted_secret() -> None:
    manifest = _manifest({}, api_key="sk-live")
    assert "manifest_redaction" in _checks(verify_manifest(manifest))


# --- 依賴防線（設計 §9.2）---------------------------------------------------------


def test_r1_eval_never_imports_interview_vnext() -> None:
    """R1 eval 不得依賴 vNext —— ADR 0034 說 vNext 達 gate 後要刪。"""
    here = Path(__file__).parent
    offenders = []
    for path in sorted(here.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")) and (
                "app.interview_vnext" in stripped or stripped.startswith("from app.")
            ):
                offenders.append(f"{path.name}: {stripped}")
    assert offenders == [], offenders
