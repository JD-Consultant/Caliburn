"""Opt-in single-shot OpenAI Responses live conformance probe (V3-4 §16).

Verifies that the official endpoint accepts the exact published portable schema
and that the real SDK response shape survives the neutral normalizer, then
writes an immutable Capture bundle. It never grades model quality: a refusal or
incomplete outcome is a valid neutral result but still fails the conformance
run because no verifiable structured payload was obtained.

Exit codes: 0 = conformance passed; 1 = probe ran but did not pass (bundle with
failed events is still written); 2 = missing OPENAI_API_KEY (nothing created).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5

import httpx
import openai
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.context import INJECTION_BOUNDARY
from app.interview_vnext.llm.operation_documents import (
    TURN_INTERPRET_PROMPT_PATH,
    turn_interpret_operation,
)
from app.interview_vnext.llm.port import (
    MessageRole,
    ModelCallRequest,
    ModelMessage,
    ResolvedModelCall,
)
from app.interview_vnext.llm.portable_schema import (
    PORTABLE_STRICT_OUTPUT_POLICY_V2,
    project_portable_strict_output_schema,
)
from app.interview_vnext.llm.result import ModelCallResult, ModelOutcome
from app.interview_vnext.llm.schema_exports import SCHEMA_EXPORTS, published_schema
from app.interview_vnext.llm.turn_interpret import (
    TurnInputTurn,
    TurnInterpretInput,
    TurnInterpretOutput,
)
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    InMemoryArtifactStore,
    RedactionStatus,
    build_inline_artifact,
)
from app.interview_vnext.observability.capture import CaptureRecorder
from app.interview_vnext.observability.events import ExecutionStatus, RunManifest
from app.interview_vnext.observability.outbox import InMemoryOutbox
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V1

from .provider_config import (
    DEFAULT_ACCEPTED_RESOLVED_MODELS,
    DEFAULT_REQUESTED_MODEL,
    OpenAIResponsesEvalConfig,
    build_openai_reference_binding,
)
from .providers.openai_responses import OpenAIResponsesEvalAdapter
from .schema_catalog import TURN_INTERPRET_OUTPUT_SCHEMA_ID


ARCHITECTURE_ID = "interview-vnext-evidence-workflow"
WORKFLOW_VERSION = "1.0.0"
PROBE_DIR = Path(__file__).with_name("probes")
SPEC_PATH = "docs/plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md"

MODEL_REQUEST_SCHEMA_ID = (
    "https://caliburn.local/schemas/model-call-request.v2.schema.json"
)
MODEL_RESULT_SCHEMA_ID = (
    "https://caliburn.local/schemas/model-call-result.v2.schema.json"
)
PROVIDER_BINDING_SCHEMA_ID = (
    "https://caliburn.local/schemas/provider-binding.v1.schema.json"
)
PROVIDER_CONFIG_SCHEMA_ID = (
    "https://caliburn.local/schemas/provider-config.v1.schema.json"
)
SCHEMA_PROJECTION_SCHEMA_ID = (
    "https://caliburn.local/schemas/schema-projection-report.v1.schema.json"
)
TURN_INPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-input.v1.schema.json"
)


def _turn_output_projection():
    """The active turn output projection (byte-identical to the published schema)."""

    schema_id, title, _factory = SCHEMA_EXPORTS["turn-interpret-output.v1.schema.json"]
    source = {**TurnInterpretOutput.model_json_schema(), "$id": schema_id, "title": title}
    return project_portable_strict_output_schema(
        source,
        source_schema_id=schema_id,
        target_profile=PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile,
    )

PROBE_LIMITATION = (
    "single-run conformance probe; not a model quality or production readiness result"
)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.interview_vnext.live_probe",
        description="Single-shot OpenAI Responses conformance probe (eval-only).",
    )
    parser.add_argument("--probe", default="turn-interpret-smoke.v1")
    parser.add_argument("--model", default=DEFAULT_REQUESTED_MODEL)
    parser.add_argument(
        "--accepted-resolved-model",
        action="append",
        dest="accepted_resolved_models",
        default=None,
        help="repeatable; defaults to the config allowlist",
    )
    parser.add_argument("--reasoning-mode", choices=["standard"], default="standard")
    parser.add_argument("--reasoning-effort", default="medium")
    parser.add_argument(
        "--output-dir", default="../../output/interview_vnext/live-probes"
    )
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> OpenAIResponsesEvalConfig:
    accepted = tuple(
        sorted(set(args.accepted_resolved_models or DEFAULT_ACCEPTED_RESOLVED_MODELS))
    )
    return OpenAIResponsesEvalConfig(
        requested_model=args.model,
        accepted_resolved_models=accepted,
        reasoning_mode=args.reasoning_mode,
        reasoning_effort=args.reasoning_effort,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not os.environ.get("OPENAI_API_KEY"):
        print(
            "OPENAI_API_KEY is not set; live probe aborted before creating any run.",
            file=sys.stderr,
        )
        return 2
    config = build_config(args)
    return asyncio.run(
        run_probe(
            probe_id=args.probe,
            config=config,
            output_dir=Path(args.output_dir),
            api_key=os.environ["OPENAI_API_KEY"],
        )
    )


async def run_probe(
    *,
    probe_id: str,
    config: OpenAIResponsesEvalConfig,
    output_dir: Path,
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
    now=None,
) -> int:
    probe = json.loads((PROBE_DIR / f"{probe_id}.json").read_text(encoding="utf-8"))
    clock = now or (lambda: datetime.now(UTC))
    adapter = OpenAIResponsesEvalAdapter(
        api_key=api_key, config=config, http_client=http_client, now=clock
    )

    run_id = uuid4()
    session_id = uuid5(run_id, "session")
    preceding_turn_id = uuid5(run_id, "turn/preceding")
    turn_id = uuid5(run_id, "turn/current")
    operation_id = uuid5(run_id, "operation")
    attempt_id = uuid5(operation_id, "attempt/1")

    operation = turn_interpret_operation()
    binding = build_openai_reference_binding(config)
    projection = _turn_output_projection()
    prompt = TURN_INTERPRET_PROMPT_PATH.read_text(encoding="utf-8")
    schema = published_schema("turn-interpret-output.v1.schema.json")
    input_value = TurnInterpretInput(
        input_boundary=INJECTION_BOUNDARY,
        preceding_question=TurnInputTurn(
            turn_id=preceding_turn_id,
            sequence=1,
            locale=probe["locale"],
            text=probe["preceding_question"],
        ),
        current_turn=TurnInputTurn(
            turn_id=turn_id,
            sequence=2,
            locale=probe["locale"],
            text=probe["turn_text"],
        ),
        active_episode=None,
        contradictions=(),
        correction_candidates=(),
        recent_active_evidence=(),
    )

    started_at = clock()

    def artifact(
        label: str,
        *,
        kind: str,
        payload: Any,
        media_type: str = "application/json",
        schema_id: str | None = None,
        attempt_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> ArtifactRecord:
        return build_inline_artifact(
            artifact_id=uuid5(operation_id, label),
            kind=kind,
            media_type=media_type,
            payload=payload,
            schema_id=schema_id,
            run_id=run_id,
            session_id=session_id,
            turn_id=turn_id,
            operation_id=operation_id,
            attempt_id=attempt_id,
            created_at=created_at or started_at,
            retention_class="eval",
            redaction_status=RedactionStatus.NOT_REQUIRED,
            contains_test_data=True,
        )

    config_artifact = artifact(
        "eval-config", kind="eval.provider_config", payload=config.model_dump(mode="json")
    )
    prompt_artifact = artifact(
        "prompt",
        kind="prompt.template",
        media_type="text/markdown; charset=utf-8",
        payload=prompt,
    )
    schema_artifact = artifact(
        "output-schema",
        kind="schema.output",
        payload=schema,
        schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
    )
    context_artifact = artifact(
        "context-packet",
        kind="probe.context",
        payload={
            "schema_version": "probe_context.v1",
            "probe_id": probe_id,
            "input": input_value.model_dump(mode="json"),
        },
    )
    manifest_artifact = artifact(
        "context-manifest",
        kind="probe.selection_manifest",
        payload={"schema_version": "probe_selection_manifest.v1", "items": []},
    )
    input_artifact = artifact(
        "turn-input",
        kind="operation.input",
        payload=input_value,
        schema_id=TURN_INPUT_SCHEMA_ID,
    )
    # V3-5A: immutable binding/config/projection artifacts the resolved call and
    # fresh-process recovery read back; their content hashes bind the request.
    binding_artifact = artifact(
        "provider-binding",
        kind="model.provider_binding",
        payload=binding,
        schema_id=PROVIDER_BINDING_SCHEMA_ID,
    )
    binding_config_artifact = artifact(
        "provider-config",
        kind="provider.config",
        payload=config,
        schema_id=PROVIDER_CONFIG_SCHEMA_ID,
    )
    projection_artifact = artifact(
        "schema-projection",
        kind="model.schema_projection",
        payload=projection.report,
        schema_id=SCHEMA_PROJECTION_SCHEMA_ID,
    )

    request = ModelCallRequest(
        run_id=run_id,
        session_id=session_id,
        turn_id=turn_id,
        operation_id=operation_id,
        attempt_id=attempt_id,
        attempt=1,
        operation_name=operation.name,
        operation_definition_hash=operation.definition_hash,
        idempotency_key=f"live-probe:{run_id}:attempt:1",
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        requested_model=binding.requested_model,
        instructions=prompt,
        messages=(
            ModelMessage(role=MessageRole.USER, text=canonical_json(input_value)),
        ),
        prompt_artifact=prompt_artifact.ref,
        output_schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
        output_schema_artifact=schema_artifact.ref,
        context_artifact=context_artifact.ref,
        selection_manifest_artifact=manifest_artifact.ref,
        binding_artifact=binding_artifact.ref,
        provider_config_artifact=binding_config_artifact.ref,
        schema_projection_artifact=projection_artifact.ref,
        deadline_at=started_at + timedelta(milliseconds=operation.timeout_ms),
        created_at=started_at,
        max_output_tokens=operation.max_output_tokens,
    )
    resolved_call = ResolvedModelCall(
        request=request, binding=binding, schema_projection=projection.report
    )
    request_artifact = artifact(
        "attempt/1/request",
        kind="model.request",
        payload=request,
        schema_id=MODEL_REQUEST_SCHEMA_ID,
        attempt_id=attempt_id,
    )

    store = InMemoryArtifactStore()
    recorder = CaptureRecorder(
        taxonomy=INTERVIEW_VNEXT_EXECUTION_V1, artifacts=store, outbox=InMemoryOutbox()
    )
    for record in (
        config_artifact,
        prompt_artifact,
        schema_artifact,
        context_artifact,
        manifest_artifact,
        input_artifact,
        binding_artifact,
        binding_config_artifact,
        projection_artifact,
        request_artifact,
    ):
        store.put(record)

    def record_event(
        label: str,
        *,
        event_type: str,
        stage: str,
        status: ExecutionStatus,
        occurred_at: datetime,
        with_attempt: bool = False,
        input_artifacts: tuple = (),
        output_artifacts: tuple = (),
    ) -> None:
        recorder.record(
            event_id=uuid5(run_id, label),
            occurred_at=occurred_at,
            architecture_id=ARCHITECTURE_ID,
            workflow_version=WORKFLOW_VERSION,
            run_id=run_id,
            session_id=session_id,
            event_type=event_type,
            stage=stage,
            status=status,
            turn_id=turn_id,
            operation_id=operation_id if with_attempt else None,
            attempt_id=attempt_id if with_attempt else None,
            attempt=1 if with_attempt else None,
            input_artifacts=input_artifacts,
            output_artifacts=output_artifacts,
        )

    record_event(
        "event/run-started",
        event_type="workflow.run.started",
        stage="workflow.run",
        status=ExecutionStatus.OK,
        occurred_at=started_at,
        output_artifacts=(config_artifact.ref, request_artifact.ref),
    )
    record_event(
        "event/model-call-started",
        event_type="model.call.started",
        stage="turn.interpret",
        status=ExecutionStatus.OK,
        occurred_at=started_at,
        with_attempt=True,
        input_artifacts=(request_artifact.ref,),
    )

    try:
        envelope = await adapter.generate_structured(resolved_call)
    finally:
        await adapter.aclose()
    result = envelope.result

    for record in envelope.supporting_artifacts:
        store.put(record)
    result_artifact = artifact(
        "attempt/1/result",
        kind="model.result",
        payload=result,
        schema_id=MODEL_RESULT_SCHEMA_ID,
        attempt_id=attempt_id,
        created_at=result.completed_at,
    )
    store.put(result_artifact)

    supporting_refs = tuple(record.ref for record in envelope.supporting_artifacts)
    if result.outcome == ModelOutcome.FAILED:
        call_event = ("event/model-call-failed", "model.call.failed", ExecutionStatus.FAILED)
    elif result.outcome == ModelOutcome.SUCCEEDED:
        call_event = ("event/model-call-completed", "model.call.completed", ExecutionStatus.OK)
    else:
        call_event = ("event/model-call-completed", "model.call.completed", ExecutionStatus.PARTIAL)
    record_event(
        call_event[0],
        event_type=call_event[1],
        stage="turn.interpret",
        status=call_event[2],
        occurred_at=result.completed_at,
        with_attempt=True,
        output_artifacts=(result_artifact.ref, *supporting_refs),
    )

    local_output_validation_passed = False
    local_validation_error: str | None = None
    if result.outcome == ModelOutcome.SUCCEEDED and result.parsed_output is not None:
        try:
            TurnInterpretOutput.model_validate(result.parsed_output.load())
            local_output_validation_passed = True
        except (ValidationError, TypeError, ValueError) as exc:
            local_validation_error = str(exc)

    completed_at = clock()
    if completed_at < result.completed_at:
        completed_at = result.completed_at
    conformance_passed = (
        result.outcome == ModelOutcome.SUCCEEDED and local_output_validation_passed
    )
    record_event(
        "event/run-completed" if conformance_passed else "event/run-failed",
        event_type="workflow.run.completed" if conformance_passed else "workflow.run.failed",
        stage="workflow.run",
        status=ExecutionStatus.OK if conformance_passed else ExecutionStatus.FAILED,
        occurred_at=completed_at,
        output_artifacts=(result_artifact.ref,),
    )

    manifest = recorder.build_manifest(
        run_id=run_id,
        completed_at=completed_at,
        root_artifacts=(config_artifact.ref, request_artifact.ref, result_artifact.ref),
    )

    report = _build_report(
        probe_id=probe_id,
        run_id=run_id,
        config=config,
        request_artifact=request_artifact,
        result_artifact=result_artifact,
        result=result,
        manifest=manifest,
        local_output_validation_passed=local_output_validation_passed,
        local_validation_error=local_validation_error,
        started_at=started_at,
        completed_at=completed_at,
    )
    bundle_dir = _write_bundle(
        output_dir,
        run_id=run_id,
        config=config,
        request=request,
        result=result,
        artifacts=store.all(),
        events=recorder.events(run_id),
        manifest=manifest,
        report=report,
    )
    print(f"live probe run {run_id}: {'passed' if conformance_passed else 'failed'}")
    print(f"bundle: {bundle_dir}")
    return 0 if conformance_passed else 1


def _build_report(
    *,
    probe_id: str,
    run_id: UUID,
    config: OpenAIResponsesEvalConfig,
    request_artifact: ArtifactRecord,
    result_artifact: ArtifactRecord,
    result: ModelCallResult,
    manifest: RunManifest,
    local_output_validation_passed: bool,
    local_validation_error: str | None,
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, Any]:
    limitations = sorted({PROBE_LIMITATION, *result.usage.limitations})
    return {
        "schema_version": "live_probe_report.v1",
        "run_id": str(run_id),
        "probe_id": probe_id,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "config_hash": config.config_hash,
        "request_artifact": request_artifact.ref.model_dump(mode="json"),
        "result_artifact": result_artifact.ref.model_dump(mode="json"),
        "outcome": result.outcome.value,
        "finish_reason": result.finish_reason.value,
        "provider_finish_reason": result.provider_finish_reason,
        "failure": (
            {
                "kind": result.failure.kind.value,
                "reason_code": result.failure.reason_code,
                "retryable": result.failure.retryable,
            }
            if result.failure is not None
            else None
        ),
        "refusal": (
            result.refusal.reason_code if result.refusal is not None else None
        ),
        "requested_model": result.requested_model,
        "resolved_model": result.resolved_model,
        "provider_request_id": result.provider_request_id,
        "usage": result.usage.model_dump(mode="json"),
        "local_output_validation_passed": local_output_validation_passed,
        "local_validation_error": local_validation_error,
        "manifest_hash": canonical_hash(manifest),
        "last_event_hash": manifest.last_event_hash,
        "limitations": limitations,
        "source_versions": {
            "openai_python": openai.__version__,
            "spec": SPEC_PATH,
        },
    }


def _write_bundle(
    output_dir: Path,
    *,
    run_id: UUID,
    config: OpenAIResponsesEvalConfig,
    request: ModelCallRequest,
    result: ModelCallResult,
    artifacts: tuple[ArtifactRecord, ...],
    events,
    manifest: RunManifest,
    report: dict[str, Any],
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir / f".tmp-{run_id}"
    final_dir = output_dir / str(run_id)
    temp_dir.mkdir()
    files = {
        "config.json": canonical_json(config),
        "request.json": canonical_json(request),
        "result.json": canonical_json(result),
        "artifacts.jsonl": "\n".join(canonical_json(item) for item in artifacts),
        "events.jsonl": "\n".join(canonical_json(item) for item in events),
        "manifest.json": canonical_json(manifest),
        "probe-report.json": canonical_json(report),
    }
    for name, content in files.items():
        (temp_dir / name).write_text(content + "\n", encoding="utf-8", newline="\n")
    temp_dir.rename(final_dir)
    return final_dir


if __name__ == "__main__":
    raise SystemExit(main())
