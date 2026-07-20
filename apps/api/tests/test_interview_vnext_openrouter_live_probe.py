"""V3-4R/R4 OpenRouter live probe — no-key preflight、mocked smoke 與 bundle 驗證。

規格 §15/§10.2:真 live gate 需真 key 另行執行(R6);這裡只測 CLI 行為、catalog/
inference 分離與 bundle 完整性(result/evidence/conformance closure),不打 live
API,也絕不以 skip 冒充 live 成功。

規格:docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest

from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.llm.capture import (
    ModelCallCaptureError,
    validate_model_call_capture_closure,
)
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    InMemoryArtifactStore,
)
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    RunManifest,
    validate_event_chain,
)
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V2

from evals.interview_vnext.openrouter_live_probe import main, run_probe
from evals.interview_vnext.openrouter_provider_config import OpenRouterProbeInputs

FIXTURES = Path(__file__).parent / "fixtures" / "interview_vnext" / "openrouter_chat"
API_KEY = "sk-or-eval-test-not-a-real-key"
FROZEN_NOW = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)
MODEL = "testlab/analyst-large"
ENDPOINT = "testhost"


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text("utf-8"))


def make_handler(
    *,
    chat: str | httpx.Response | None = "success.json",
    model: str = "catalog-model.json",
    endpoints: str = "catalog-endpoints.json",
    model_status: int = 200,
    chat_headers: dict[str, str] | None = None,
):
    manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET" and path.endswith("/endpoints"):
            return httpx.Response(200, json=fixture_json(endpoints))
        if request.method == "GET" and "/model/" in path:
            if model_status != 200:
                return httpx.Response(
                    model_status, json={"error": {"code": model_status}}
                )
            return httpx.Response(200, json=fixture_json(model))
        if request.method == "POST":
            if isinstance(chat, httpx.Response):
                return chat
            meta = manifest["fixtures"].get(chat, {})
            return httpx.Response(
                meta.get("status", 200),
                json=fixture_json(chat),
                headers=(
                    meta.get("headers", {})
                    if chat_headers is None
                    else chat_headers
                ),
            )
        return httpx.Response(404, json={"error": {"code": 404}})

    return handler


def probe_inputs(**overrides: Any) -> OpenRouterProbeInputs:
    values: dict[str, Any] = {
        "requested_model": MODEL,
        "upstream_endpoint_slug": ENDPOINT,
        "data_collection": "deny",
        "zdr_required": False,
        "reasoning_effort": "medium",
    }
    values.update(overrides)
    return OpenRouterProbeInputs(**values)


async def run_mocked(tmp_path: Path, handler, inputs=None) -> tuple[int, Path]:
    output_dir = tmp_path / "openrouter-live-probes"
    exit_code = await run_probe(
        probe_id="turn-interpret-openrouter-smoke.v1",
        probe_inputs=inputs or probe_inputs(),
        output_dir=output_dir,
        api_key=API_KEY,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        now=lambda: FROZEN_NOW,
    )
    bundles = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(bundles) == 1
    assert not bundles[0].name.startswith(".tmp")
    return exit_code, bundles[0]


def load_bundle(bundle: Path) -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in bundle.iterdir()
        if path.is_file()
    }


def validate_capture_chain(data: dict) -> tuple[list[ExecutionEvent], RunManifest]:
    events = [
        ExecutionEvent.model_validate_json(line)
        for line in data["events.jsonl"].strip().splitlines()
    ]
    manifest = RunManifest.model_validate_json(data["manifest.json"])
    records = {
        record.ref.artifact_id: record
        for record in (
            ArtifactRecord.model_validate_json(line)
            for line in data["artifacts.jsonl"].strip().splitlines()
        )
    }
    store = InMemoryArtifactStore(records)
    validate_event_chain(
        tuple(events),
        taxonomy=INTERVIEW_VNEXT_EXECUTION_V2,
        artifact_store=store,
        manifest=manifest,
    )
    validate_model_call_capture_closure(
        tuple(events), manifest=manifest, artifact_store=store
    )
    return events, manifest


class TestNoKey:
    def test_missing_api_key_fails_fast_without_run(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        output_dir = tmp_path / "openrouter-live-probes"
        exit_code = main(
            ["--model", MODEL, "--upstream-endpoint", ENDPOINT,
             "--output-dir", str(output_dir)]
        )
        assert exit_code == 2
        assert not output_dir.exists()
        captured = capsys.readouterr()
        assert "OPENROUTER_API_KEY is not set" in captured.err
        assert "passed" not in captured.out

    def test_reasoning_none_maps_to_null(self):
        import argparse

        from evals.interview_vnext.openrouter_live_probe import build_probe_inputs

        args = argparse.Namespace(
            model=MODEL, upstream_endpoint=ENDPOINT, data_collection="deny",
            zdr_required="false", reasoning_effort="none", reasoning_max_tokens=None,
        )
        inputs = build_probe_inputs(args)
        assert inputs.reasoning_effort is None


class TestSuccessBundle:
    async def test_mocked_smoke_produces_valid_bundle(self, tmp_path):
        exit_code, bundle = await run_mocked(tmp_path, make_handler())
        assert exit_code == 0
        data = load_bundle(bundle)
        for name in (
            "probe-inputs.json", "config.json", "model-catalog.json",
            "endpoint-catalog.json", "request.json", "result.json",
            "artifacts.jsonl", "events.jsonl", "manifest.json", "probe-report.json",
        ):
            assert name in data, name
            assert data[name].endswith("\n")

        events, manifest = validate_capture_chain(data)
        assert [event.event_type for event in events] == [
            "workflow.run.started",
            "artifact.created",
            "model.call.started",
            "model.call.completed",
            "provider.conformance.completed",
            "workflow.run.completed",
        ]
        assert [event.status.value for event in events] == [
            "ok", "ok", "ok", "ok", "ok", "ok",
        ]
        call_started = events[2]
        call_completed = events[3]
        conformance_event = events[4]
        assert [ref.kind for ref in call_started.input_artifacts] == [
            "model.request",
            "model.provider_binding",
            "provider.config",
            "model.schema_projection",
        ]
        assert call_completed.input_artifacts == call_started.input_artifacts
        # R4 §10.2:result event 的 deterministic tail 是 result 再 evidence。
        assert [ref.kind for ref in call_completed.output_artifacts[-2:]] == [
            "model.result",
            "model.provider_execution_evidence",
        ]
        # conformance event 的 input 是 binding、evidence;output 只有 report。
        assert [ref.kind for ref in conformance_event.input_artifacts] == [
            "model.provider_binding",
            "model.provider_execution_evidence",
        ]
        assert conformance_event.input_artifacts[0] == call_started.input_artifacts[1]
        assert conformance_event.input_artifacts[1] == (
            call_completed.output_artifacts[-1]
        )
        assert [ref.kind for ref in conformance_event.output_artifacts] == [
            "model.provider_conformance",
        ]
        assert [ref.kind for ref in manifest.root_artifacts] == [
            "probe.inputs",
            "model.request",
            "model.provider_binding",
            "provider.config",
            "model.schema_projection",
            "model.result",
            "model.provider_execution_evidence",
            "model.provider_conformance",
        ]

        # R3-C1(§7.6):provider.config artifact 不宣告不存在的 generic schema ID,
        # 但 content hash 仍必須是 binding 引用的 config hash。
        records = [
            ArtifactRecord.model_validate_json(line)
            for line in data["artifacts.jsonl"].strip().splitlines()
        ]
        config_refs = [
            record.ref for record in records if record.ref.kind == "provider.config"
        ]
        assert len(config_refs) == 1
        assert config_refs[0].schema_id is None
        binding_records = [
            record for record in records
            if record.ref.kind == "model.provider_binding"
        ]
        assert len(binding_records) == 1
        binding_payload = json.loads(binding_records[0].inline_content)
        assert binding_payload["provider_config_hash"] == config_refs[0].content_hash

        report = json.loads(data["probe-report.json"])
        assert report["schema_version"] == "openrouter_live_probe_report.v2"
        assert report["outcome"] == "succeeded"
        assert report["final_config_created"] is True
        assert report["local_output_validation_passed"] is True
        assert report["resolved_model"] == MODEL
        assert report["catalog_model_id"] == MODEL
        assert report["catalog_canonical_slug"] == "testlab/analyst-large-20260717"
        assert report["selected_provider_name"] == "TestHost"
        assert report["router_strategy"] == "direct"
        assert report["router_attempt"] == 1
        assert report["generation_id"] == "gen-fx-success"
        assert report["provider_request_id"] == "req_fx_success"
        assert report["catalog_http_calls"] == 2
        assert report["inference_http_calls"] == 1
        # R4 report v2:conformance authority 欄位;v1 route_conformance verdict 移除。
        assert "route_conformance" not in report
        assert report["conformance_eligible"] is True
        assert report["conformance_reason_codes"] == []
        assert report["conformance_policy_name"] == "attribution-strict"
        assert report["conformance_policy_version"] == "1.0.0"
        assert report["conformance_policy_hash"].startswith("sha256:")
        assert report["conformance_report_hash"].startswith("sha256:")
        assert report["execution_evidence_hash"].startswith("sha256:")
        assert report["binding_id"] == (
            "turn-interpret-c1-openrouter-attribution-strict"
        )
        assert report["binding_hash"].startswith("sha256:")
        assert report["transformation_status"] == "clean"
        assert report["cache_status"] == "absent"
        assert report["pipeline_stage_summaries"] == []
        assert report["evidence_artifact_id"]
        assert report["conformance_artifact_id"]
        assert report["production_promotable"] is False
        assert report["usage"]["input_tokens"] == 1200
        assert report["manifest_hash"] == canonical_hash(manifest)
        assert report["last_event_hash"] == manifest.last_event_hash

        for name, content in data.items():
            assert API_KEY not in content, name
            assert "Authorization" not in content, name
            assert "sk-or-eval" not in content, name

    async def test_missing_provider_request_id_is_an_explicit_limitation(
        self, tmp_path
    ):
        exit_code, bundle = await run_mocked(
            tmp_path, make_handler(chat_headers={})
        )
        assert exit_code == 0
        report = json.loads((bundle / "probe-report.json").read_text("utf-8"))
        assert report["provider_request_id"] is None
        assert "provider HTTP request ID was not returned" in report["limitations"]


class TestFailureBundles:
    async def test_catalog_failure_writes_bundle_and_no_inference(self, tmp_path):
        exit_code, bundle = await run_mocked(
            tmp_path, make_handler(model_status=401)
        )
        assert exit_code == 1
        data = load_bundle(bundle)
        assert "config.json" not in data
        assert "request.json" not in data
        report = json.loads(data["probe-report.json"])
        assert report["failed_stage"] == "catalog_probe_failed"
        assert report["final_config_created"] is False
        assert report["inference_http_calls"] == 0
        assert report["catalog_http_calls"] == 1
        events, _ = validate_capture_chain(data)
        assert [event.event_type for event in events] == [
            "workflow.run.started",
            "workflow.run.failed",
        ]

    async def test_ambiguous_slug_fails_at_config_before_inference(self, tmp_path):
        # Ambiguous base slug matches two endpoints -> config construction fails,
        # no config.json and no POST.
        exit_code, bundle = await run_mocked(
            tmp_path,
            make_handler(),
            inputs=probe_inputs(upstream_endpoint_slug="regionhost"),
        )
        assert exit_code == 1
        data = load_bundle(bundle)
        assert "config.json" not in data
        assert "request.json" not in data
        assert "result.json" not in data
        report = json.loads(data["probe-report.json"])
        assert report["inference_http_calls"] == 0
        assert report["final_config_created"] is False
        events, _ = validate_capture_chain(data)
        assert [event.event_type for event in events] == [
            "workflow.run.started",
            "artifact.created",
            "workflow.run.failed",
        ]

    async def test_preflight_failure_after_config_has_no_inference(self, tmp_path):
        # Endpoint lacks a required parameter -> config builds, preflight fails,
        # config.json present but no POST.
        endpoints = fixture_json("catalog-endpoints.json")
        endpoints["data"]["endpoints"][0]["supported_parameters"] = [
            "max_tokens", "response_format"
        ]

        manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))

        def handler(request: httpx.Request) -> httpx.Response:
            path = request.url.path
            if request.method == "GET" and path.endswith("/endpoints"):
                return httpx.Response(200, json=endpoints)
            if request.method == "GET" and "/model/" in path:
                return httpx.Response(200, json=fixture_json("catalog-model.json"))
            meta = manifest["fixtures"].get("success.json", {})
            return httpx.Response(200, json=fixture_json("success.json"),
                                  headers=meta.get("headers", {}))

        exit_code, bundle = await run_mocked(tmp_path, handler)
        assert exit_code == 1
        data = load_bundle(bundle)
        assert "config.json" in data
        assert "request.json" not in data
        report = json.loads(data["probe-report.json"])
        assert report["inference_http_calls"] == 0
        assert report["final_config_created"] is True
        assert "endpoint_parameters_missing" in report["failed_stage"]

    async def test_contaminated_route_is_wire_success_but_conformance_failed(
        self, tmp_path
    ):
        """R4 §10.2:污染 route 整體仍 fail,但 authority 是 conformance report。"""

        body = fixture_json("success.json")
        body["openrouter_metadata"]["strategy"] = "auto"
        exit_code, bundle = await run_mocked(
            tmp_path, make_handler(chat=httpx.Response(200, json=body))
        )
        assert exit_code == 1
        data = load_bundle(bundle)
        report = json.loads(data["probe-report.json"])
        # wire result 仍是 succeeded;沒有偽造的 ModelFailure。
        assert report["outcome"] == "succeeded"
        assert report["failure"] is None
        assert report["conformance_eligible"] is False
        assert report["conformance_reason_codes"] == [
            "conformance.route_strategy_mismatch"
        ]
        assert report["router_strategy"] == "auto"
        assert report["inference_http_calls"] == 1
        # §10.2 item 11:ineligible 時不得執行 local output validation。
        assert report["local_output_validation_passed"] is False
        assert report["local_validation_error"] is None
        events, _ = validate_capture_chain(data)
        assert events[-1].event_type == "workflow.run.failed"
        event_status = {
            event.event_type: event.status.value for event in events
        }
        assert event_status["model.call.completed"] == "ok"
        assert event_status["provider.conformance.completed"] == "failed"
        assert "model.call.failed" not in event_status

    async def test_wire_failure_conformance_event_is_skipped(self, tmp_path):
        exit_code, bundle = await run_mocked(
            tmp_path,
            make_handler(
                chat=httpx.Response(
                    429,
                    json={
                        "error": {
                            "code": 429,
                            "message": "synthetic rate limit",
                            "metadata": {"error_type": "rate_limit_exceeded"},
                        }
                    },
                )
            ),
        )
        assert exit_code == 1
        data = load_bundle(bundle)
        report = json.loads(data["probe-report.json"])
        assert report["outcome"] == "failed"
        assert report["failure"]["reason_code"] == "openrouter.rate_limited"
        assert report["conformance_eligible"] is False
        assert report["conformance_reason_codes"] == [
            "conformance.wire_not_succeeded"
        ]
        events, _ = validate_capture_chain(data)
        event_status = {
            event.event_type: event.status.value for event in events
        }
        assert event_status["model.call.failed"] == "failed"
        assert event_status["provider.conformance.completed"] == "skipped"

    async def test_bundle_corruption_fails_validation(self, tmp_path):
        exit_code, bundle = await run_mocked(tmp_path, make_handler())
        assert exit_code == 0
        data = load_bundle(bundle)
        events = tuple(
            ExecutionEvent.model_validate_json(line)
            for line in data["events.jsonl"].strip().splitlines()
        )
        manifest = RunManifest.model_validate_json(data["manifest.json"])
        records = {
            record.ref.artifact_id: record
            for record in (
                ArtifactRecord.model_validate_json(line)
                for line in data["artifacts.jsonl"].strip().splitlines()
            )
        }
        store = InMemoryArtifactStore(records)

        # 移除 conformance root → closure 驗證必須失敗。
        pruned_roots = tuple(
            ref for ref in manifest.root_artifacts
            if ref.kind != "model.provider_conformance"
        )
        pruned = manifest.model_copy(update={"root_artifacts": pruned_roots})
        with pytest.raises(ModelCallCaptureError):
            validate_model_call_capture_closure(
                events, manifest=pruned, artifact_store=store
            )

        # 移除 evidence root → 同樣失敗。
        no_evidence_roots = tuple(
            ref for ref in manifest.root_artifacts
            if ref.kind != "model.provider_execution_evidence"
        )
        no_evidence = manifest.model_copy(
            update={"root_artifacts": no_evidence_roots}
        )
        with pytest.raises(ModelCallCaptureError):
            validate_model_call_capture_closure(
                events, manifest=no_evidence, artifact_store=store
            )

        # 竄改 conformance event 的 input 順序 → 失敗。
        tampered_events = tuple(
            event.model_copy(
                update={
                    "input_artifacts": tuple(reversed(event.input_artifacts))
                }
            )
            if event.event_type == "provider.conformance.completed"
            else event
            for event in events
        )
        with pytest.raises(ModelCallCaptureError):
            validate_model_call_capture_closure(
                tampered_events, manifest=manifest, artifact_store=store
            )

    async def test_data_collection_allow_is_not_promotable(self, tmp_path):
        exit_code, bundle = await run_mocked(
            tmp_path, make_handler(), inputs=probe_inputs(data_collection="allow")
        )
        assert exit_code == 0
        report = json.loads((bundle / "probe-report.json").read_text("utf-8"))
        assert report["production_promotable"] is False
        assert any("data_collection=allow" in item for item in report["limitations"])
