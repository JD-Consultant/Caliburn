"""V3-4 live probe — no-key preflight、mocked smoke 與 Capture bundle 驗證。

規格 §16:live gate 本身需要真 key,另行執行;這裡只測 CLI 行為與 bundle 完整性,
不打 live API,也絕不以 skip 冒充 live 成功。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest

from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    InMemoryArtifactStore,
)
from app.interview_vnext.observability.events import (
    ExecutionEvent,
    RunManifest,
    validate_event_chain,
)
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1

from evals.interview_vnext.live_probe import build_config, main, run_probe
from evals.interview_vnext.provider_config import OpenAIResponsesEvalConfig

FIXTURES = Path(__file__).parent / "fixtures" / "interview_vnext" / "openai_responses"
API_KEY = "sk-eval-test-not-a-real-key"
FROZEN_NOW = datetime(2026, 7, 17, 3, 0, 0, tzinfo=UTC)


def fixture_handler(name: str):
    manifest = json.loads((FIXTURES / "manifest.json").read_text("utf-8"))
    meta = manifest["fixtures"][name]

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            meta.get("status", 200),
            json=json.loads((FIXTURES / name).read_text("utf-8")),
            headers=meta.get("headers", {}),
        )

    return handler


async def run_mocked_probe(tmp_path: Path, fixture: str) -> tuple[int, Path]:
    output_dir = tmp_path / "live-probes"
    exit_code = await run_probe(
        probe_id="turn-interpret-smoke.v1",
        config=OpenAIResponsesEvalConfig(),
        output_dir=output_dir,
        api_key=API_KEY,
        http_client=httpx.AsyncClient(
            transport=httpx.MockTransport(fixture_handler(fixture))
        ),
        now=lambda: FROZEN_NOW,
    )
    bundles = [path for path in output_dir.iterdir() if path.is_dir()]
    assert len(bundles) == 1
    assert not bundles[0].name.startswith(".tmp")
    return exit_code, bundles[0]


BUNDLE_FILES = (
    "config.json",
    "request.json",
    "result.json",
    "artifacts.jsonl",
    "events.jsonl",
    "manifest.json",
    "probe-report.json",
)


def load_bundle(bundle: Path) -> dict:
    data = {name: (bundle / name).read_text(encoding="utf-8") for name in BUNDLE_FILES}
    for name in BUNDLE_FILES:
        assert data[name].endswith("\n")
    return data


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
        taxonomy=INTERVIEW_VNEXT_EXECUTION_V1,
        artifact_store=store,
        manifest=manifest,
    )
    return events, manifest


class TestLivePreflight:
    def test_missing_api_key_fails_fast_without_run(self, tmp_path, monkeypatch, capsys):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        output_dir = tmp_path / "live-probes"
        exit_code = main(["--output-dir", str(output_dir)])
        assert exit_code == 2
        assert not output_dir.exists()
        captured = capsys.readouterr()
        assert "OPENAI_API_KEY is not set" in captured.err
        assert "passed" not in captured.out

    def test_build_config_applies_cli_allowlist_sorted_unique(self):
        import argparse

        args = argparse.Namespace(
            model="gpt-5.6",
            accepted_resolved_models=["gpt-5.6-sol", "gpt-5.6", "gpt-5.6-sol"],
            reasoning_mode="standard",
            reasoning_effort="medium",
        )
        config = build_config(args)
        assert config.accepted_resolved_models == ("gpt-5.6", "gpt-5.6-sol")


class TestMockedProbeBundle:
    async def test_mocked_smoke_produces_valid_capture_bundle(self, tmp_path):
        exit_code, bundle = await run_mocked_probe(
            tmp_path, "success_reasoning_then_message.json"
        )
        assert exit_code == 0
        data = load_bundle(bundle)
        events, manifest = validate_capture_chain(data)

        event_types = [event.event_type for event in events]
        assert event_types == [
            "workflow.run.started",
            "model.call.started",
            "model.call.completed",
            "workflow.run.completed",
        ]
        assert [event.status.value for event in events] == ["ok", "ok", "ok", "ok"]
        assert {event.stage for event in events} == {"workflow.run", "turn.interpret"}

        report = json.loads(data["probe-report.json"])
        assert report["outcome"] == "succeeded"
        assert report["local_output_validation_passed"] is True
        assert report["resolved_model"] == "gpt-5.6-sol"
        assert report["provider_request_id"] == "req_fx_success"
        assert report["usage"]["input_tokens"] == 1200
        assert report["manifest_hash"] == canonical_hash(manifest)
        assert report["last_event_hash"] == manifest.last_event_hash
        assert report["config_hash"] == OpenAIResponsesEvalConfig().config_hash
        assert report["limitations"]

        result = json.loads(data["result.json"])
        assert result["outcome"] == "succeeded"
        request = json.loads(data["request.json"])
        assert request["schema_version"] == "model_call_request.v2"
        assert request["binding_id"] == "turn-interpret-c1-openai-reference-attribution-strict"
        assert request["requested_model"] == "gpt-5.6"

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

        for name in BUNDLE_FILES:
            assert API_KEY not in data[name], name
            assert "Authorization" not in data[name], name

    async def test_mocked_failure_still_writes_failed_bundle_and_exit_1(self, tmp_path):
        exit_code, bundle = await run_mocked_probe(tmp_path, "server_500.json")
        assert exit_code == 1
        data = load_bundle(bundle)
        events, _ = validate_capture_chain(data)
        event_types = [event.event_type for event in events]
        assert event_types == [
            "workflow.run.started",
            "model.call.started",
            "model.call.failed",
            "workflow.run.failed",
        ]
        assert [event.status.value for event in events] == [
            "ok",
            "ok",
            "failed",
            "failed",
        ]
        report = json.loads(data["probe-report.json"])
        assert report["outcome"] == "failed"
        assert report["failure"]["reason_code"] == "openai.server_error"
        assert report["failure"]["retryable"] is True
        assert report["local_output_validation_passed"] is False

    async def test_refusal_is_partial_model_call_but_failed_run(self, tmp_path):
        exit_code, bundle = await run_mocked_probe(tmp_path, "refusal.json")
        assert exit_code == 1
        data = load_bundle(bundle)
        events, _ = validate_capture_chain(data)
        by_type = {event.event_type: event for event in events}
        assert by_type["model.call.completed"].status.value == "partial"
        assert "workflow.run.failed" in by_type
        report = json.loads(data["probe-report.json"])
        assert report["outcome"] == "refused"
        assert report["refusal"] == "openai.refusal"
        assert report["local_output_validation_passed"] is False

    async def test_incomplete_is_partial_model_call_but_failed_run(self, tmp_path):
        exit_code, bundle = await run_mocked_probe(
            tmp_path, "incomplete_max_output_no_visible.json"
        )
        assert exit_code == 1
        data = load_bundle(bundle)
        events, _ = validate_capture_chain(data)
        by_type = {event.event_type: event for event in events}
        assert by_type["model.call.completed"].status.value == "partial"
        report = json.loads(data["probe-report.json"])
        assert report["outcome"] == "incomplete"
        assert report["finish_reason"] == "max_output_tokens"
