"""Opt-in single-shot OpenRouter Chat live conformance probe (V3-4R §15).

Fetches immutable model/endpoints snapshots, constructs the snapshot-derived
config, runs preflight, then performs exactly one inference POST through the
neutral adapter and writes an immutable Capture bundle. It never grades model
quality: a refusal, incomplete or contaminated route is a valid neutral result
but still fails the conformance run because no verifiable structured payload was
obtained on the approved route.

Catalog GETs are separate from the durable inference attempt: a catalog/preflight
failure writes a bundle but never calls inference.

Exit codes: 0 = conformance passed; 1 = probe ran but did not pass (a bundle with
failed events is still written); 2 = missing OPENROUTER_API_KEY (nothing created).

規格:docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md
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
from app.interview_vnext.llm.schema_ids import (
    MODEL_REQUEST_SCHEMA_ID,
    MODEL_RESULT_SCHEMA_ID,
    PROVIDER_BINDING_SCHEMA_ID,
    SCHEMA_PROJECTION_SCHEMA_ID,
)
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

from .openrouter_model_catalog import (
    CatalogProbeError,
    OpenRouterModelCatalogClient,
    PreflightError,
    build_catalog_snapshot_artifact,
    preflight,
)
from .openrouter_provider_config import (
    ConfigConstructionError,
    OpenRouterProbeInputs,
    build_openrouter_eval_binding,
    build_openrouter_eval_config,
)
from .providers.openrouter_chat import (
    ROUTING_ARTIFACT_KIND,
    OpenRouterChatEvalAdapter,
)
from .schema_catalog import TURN_INTERPRET_OUTPUT_SCHEMA_ID


ARCHITECTURE_ID = "interview-vnext-evidence-workflow"
WORKFLOW_VERSION = "1.0.0"
PROBE_DIR = Path(__file__).with_name("probes")
SPEC_PATH = "docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md"

# 共用 LLM contract schema IDs 收斂在 llm/schema_ids.py(R3-C1 §6.1.1);
# provider config artifact 刻意無 schema ID(§5.2)。
TURN_INPUT_SCHEMA_ID = "https://caliburn.local/schemas/turn-interpret-input.v1.schema.json"

PROBE_LIMITATION = (
    "single-run gateway conformance probe; not a model quality or production "
    "readiness result"
)
PROMOTION_LIMITATION = (
    "conformance probe is never production_promotable; production promotion is a "
    "separate slice (spec §16.5)"
)

REASONING_EFFORT_CHOICES = ("none", "minimal", "low", "medium", "high", "xhigh", "max")


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="evals.interview_vnext.openrouter_live_probe",
        description="Single-shot OpenRouter Chat conformance probe (eval-only).",
    )
    parser.add_argument("--probe", default="turn-interpret-openrouter-smoke.v1")
    parser.add_argument(
        "--model",
        required=True,
        help="exact Models API id (dynamic aliases and variant shortcuts forbidden)",
    )
    parser.add_argument(
        "--upstream-endpoint", required=True, help="exact provider endpoint slug"
    )
    parser.add_argument(
        "--data-collection", choices=["deny", "allow"], default="deny"
    )
    parser.add_argument(
        "--zdr-required", choices=["true", "false"], default="false"
    )
    parser.add_argument(
        "--reasoning-effort", choices=REASONING_EFFORT_CHOICES, default="medium"
    )
    parser.add_argument("--reasoning-max-tokens", type=int, default=None)
    parser.add_argument(
        "--output-dir",
        default="../../output/interview_vnext/openrouter-live-probes",
    )
    return parser.parse_args(argv)


def _turn_output_projection():
    """The active turn output projection (byte-identical to the published schema)."""

    schema_id, title, _factory = SCHEMA_EXPORTS["turn-interpret-output.v1.schema.json"]
    source = {**TurnInterpretOutput.model_json_schema(), "$id": schema_id, "title": title}
    return project_portable_strict_output_schema(
        source,
        source_schema_id=schema_id,
        target_profile=PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile,
    )


def build_probe_inputs(args: argparse.Namespace) -> OpenRouterProbeInputs:
    effort = None if args.reasoning_effort == "none" else args.reasoning_effort
    return OpenRouterProbeInputs(
        requested_model=args.model,
        upstream_endpoint_slug=args.upstream_endpoint,
        data_collection=args.data_collection,
        zdr_required=args.zdr_required == "true",
        reasoning_effort=effort,
        reasoning_max_tokens=args.reasoning_max_tokens,
    )


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print(
            "OPENROUTER_API_KEY is not set; live probe aborted before creating any run.",
            file=sys.stderr,
        )
        return 2
    probe_inputs = build_probe_inputs(args)
    return asyncio.run(
        run_probe(
            probe_id=args.probe,
            probe_inputs=probe_inputs,
            output_dir=Path(args.output_dir),
            api_key=os.environ["OPENROUTER_API_KEY"],
        )
    )


async def run_probe(
    *,
    probe_id: str,
    probe_inputs: OpenRouterProbeInputs,
    output_dir: Path,
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
    now=None,
) -> int:
    probe = json.loads((PROBE_DIR / f"{probe_id}.json").read_text(encoding="utf-8"))
    clock = now or (lambda: datetime.now(UTC))
    owns_client = http_client is None
    client = http_client or httpx.AsyncClient(follow_redirects=False)

    run_id = uuid4()
    session_id = uuid5(run_id, "session")
    operation = turn_interpret_operation()
    started_at = clock()

    store = InMemoryArtifactStore()
    recorder = CaptureRecorder(
        taxonomy=INTERVIEW_VNEXT_EXECUTION_V1, artifacts=store, outbox=InMemoryOutbox()
    )

    def run_artifact(
        label: str, *, kind: str, payload: Any, media_type: str = "application/json",
        schema_id: str | None = None, created_at: datetime | None = None,
    ) -> ArtifactRecord:
        record = build_inline_artifact(
            artifact_id=uuid5(run_id, label),
            kind=kind, media_type=media_type, payload=payload, schema_id=schema_id,
            run_id=run_id, session_id=session_id,
            created_at=created_at or started_at, retention_class="eval",
            redaction_status=RedactionStatus.NOT_REQUIRED, contains_test_data=True,
        )
        store.put(record)
        return record

    def record_event(
        label: str, *, event_type: str, status: ExecutionStatus,
        occurred_at: datetime, stage: str = "workflow.run",
        turn_id: UUID | None = None, operation_id: UUID | None = None,
        attempt_id: UUID | None = None, attempt: int | None = None,
        input_artifacts: tuple = (), output_artifacts: tuple = (),
    ) -> None:
        recorder.record(
            event_id=uuid5(run_id, label), occurred_at=occurred_at,
            architecture_id=ARCHITECTURE_ID, workflow_version=WORKFLOW_VERSION,
            run_id=run_id, session_id=session_id, event_type=event_type, stage=stage,
            status=status, turn_id=turn_id, operation_id=operation_id,
            attempt_id=attempt_id, attempt=attempt,
            input_artifacts=input_artifacts, output_artifacts=output_artifacts,
        )

    probe_inputs_artifact = run_artifact(
        "probe-inputs", kind="probe.inputs", payload=probe_inputs.model_dump(mode="json")
    )
    record_event(
        "event/run-started", event_type="workflow.run.started",
        status=ExecutionStatus.OK, occurred_at=started_at,
        output_artifacts=(probe_inputs_artifact.ref,),
    )

    bundle_files: dict[str, str] = {
        "probe-inputs.json": canonical_json(probe_inputs),
    }
    catalog_http_calls = 0
    catalog_statuses: list[int] = []
    inference_http_calls = 0
    final_config_created = False
    catalog_client = OpenRouterModelCatalogClient(
        api_key=api_key, http_client=client, now=clock
    )

    try:
        # ---- catalog snapshots (separate from the inference attempt) ---------
        try:
            model_snapshot = await catalog_client.fetch_model(
                probe_inputs.requested_model
            )
            catalog_http_calls += 1
            catalog_statuses.append(200)
            endpoint_snapshot = await catalog_client.fetch_endpoints(
                probe_inputs.requested_model
            )
            catalog_http_calls += 1
            catalog_statuses.append(200)
        except CatalogProbeError as exc:
            catalog_http_calls += 1
            if exc.http_status is not None:
                catalog_statuses.append(exc.http_status)
            failed_at = clock()
            record_event(
                "event/run-failed", event_type="workflow.run.failed",
                status=ExecutionStatus.FAILED, occurred_at=failed_at,
                output_artifacts=(probe_inputs_artifact.ref,),
            )
            manifest = recorder.build_manifest(
                run_id=run_id, completed_at=failed_at,
                root_artifacts=(probe_inputs_artifact.ref,),
            )
            report = _catalog_failure_report(
                probe_id=probe_id, run_id=run_id, probe_inputs=probe_inputs,
                stage="catalog_probe_failed", detail=exc.detail,
                catalog_http_calls=catalog_http_calls, catalog_statuses=catalog_statuses,
                manifest=manifest, started_at=started_at, completed_at=failed_at,
            )
            bundle_files.update(
                {
                    "events.jsonl": _jsonl(recorder.events(run_id)),
                    "artifacts.jsonl": _jsonl(store.all()),
                    "manifest.json": canonical_json(manifest),
                    "probe-report.json": canonical_json(report),
                }
            )
            _write_bundle(output_dir, run_id=run_id, files=bundle_files)
            _print_summary(run_id, "failed", output_dir / str(run_id), report)
            return 1

        model_catalog_artifact = build_catalog_snapshot_artifact(
            model_snapshot, run_id=run_id, session_id=session_id, created_at=started_at
        )
        endpoint_catalog_artifact = build_catalog_snapshot_artifact(
            endpoint_snapshot, run_id=run_id, session_id=session_id, created_at=started_at
        )
        store.put(model_catalog_artifact)
        store.put(endpoint_catalog_artifact)
        record_event(
            "event/model-catalog", event_type="artifact.created",
            status=ExecutionStatus.OK, occurred_at=started_at,
            output_artifacts=(model_catalog_artifact.ref, endpoint_catalog_artifact.ref),
        )
        bundle_files["model-catalog.json"] = canonical_json(model_snapshot)
        bundle_files["endpoint-catalog.json"] = canonical_json(endpoint_snapshot)

        # ---- config + preflight (local; still no inference) ------------------
        try:
            config = build_openrouter_eval_config(
                probe_inputs, model_snapshot, endpoint_snapshot
            )
            binding = build_openrouter_eval_binding(config)
            final_config_created = True
            bundle_files["config.json"] = canonical_json(config)
            preflight_facts = preflight(
                model_snapshot=model_snapshot, endpoint_snapshot=endpoint_snapshot,
                requested_model=probe_inputs.requested_model,
                upstream_endpoint_slug=probe_inputs.upstream_endpoint_slug,
                reasoning_effort=probe_inputs.reasoning_effort,
                reasoning_max_tokens=probe_inputs.reasoning_max_tokens,
                required_output_tokens=operation.max_output_tokens,
                now=started_at,
            )
        except (ConfigConstructionError, PreflightError) as exc:
            reason_code = getattr(exc, "reason_code", "openrouter.config_construction_failed")
            failed_at = clock()
            record_event(
                "event/run-failed", event_type="workflow.run.failed",
                status=ExecutionStatus.FAILED, occurred_at=failed_at,
                output_artifacts=(model_catalog_artifact.ref,),
            )
            manifest = recorder.build_manifest(
                run_id=run_id, completed_at=failed_at,
                root_artifacts=(probe_inputs_artifact.ref,),
            )
            report = _catalog_failure_report(
                probe_id=probe_id, run_id=run_id, probe_inputs=probe_inputs,
                stage=reason_code, detail=str(exc),
                catalog_http_calls=catalog_http_calls, catalog_statuses=catalog_statuses,
                manifest=manifest, started_at=started_at, completed_at=failed_at,
                model_snapshot_hash=model_snapshot.snapshot_hash,
                endpoint_snapshot_hash=endpoint_snapshot.snapshot_hash,
                final_config_created=final_config_created,
            )
            bundle_files.update(
                {
                    "events.jsonl": _jsonl(recorder.events(run_id)),
                    "artifacts.jsonl": _jsonl(store.all()),
                    "manifest.json": canonical_json(manifest),
                    "probe-report.json": canonical_json(report),
                }
            )
            _write_bundle(output_dir, run_id=run_id, files=bundle_files)
            _print_summary(run_id, "failed", output_dir / str(run_id), report)
            return 1

        # ---- build request artifacts -----------------------------------------
        turn_id = uuid5(run_id, "turn/current")
        preceding_turn_id = uuid5(run_id, "turn/preceding")
        operation_id = uuid5(run_id, "operation")
        attempt_id = uuid5(operation_id, "attempt/1")
        prompt = TURN_INTERPRET_PROMPT_PATH.read_text(encoding="utf-8")
        schema = published_schema("turn-interpret-output.v1.schema.json")
        input_value = TurnInterpretInput(
            input_boundary=INJECTION_BOUNDARY,
            preceding_question=TurnInputTurn(
                turn_id=preceding_turn_id, sequence=1, locale=probe["locale"],
                text=probe["preceding_question"],
            ),
            current_turn=TurnInputTurn(
                turn_id=turn_id, sequence=2, locale=probe["locale"],
                text=probe["turn_text"],
            ),
            active_episode=None, contradictions=(), correction_candidates=(),
            recent_active_evidence=(),
        )

        def call_artifact(
            label: str, *, kind: str, payload: Any,
            media_type: str = "application/json", schema_id: str | None = None,
            attempt: bool = False, created_at: datetime | None = None,
        ) -> ArtifactRecord:
            record = build_inline_artifact(
                artifact_id=uuid5(operation_id, label), kind=kind, media_type=media_type,
                payload=payload, schema_id=schema_id, run_id=run_id, session_id=session_id,
                turn_id=turn_id, operation_id=operation_id,
                attempt_id=attempt_id if attempt else None,
                created_at=created_at or started_at, retention_class="eval",
                redaction_status=RedactionStatus.NOT_REQUIRED, contains_test_data=True,
            )
            store.put(record)
            return record

        projection = _turn_output_projection()
        config_artifact = call_artifact(
            "eval-config", kind="eval.provider_config",
            payload=config.model_dump(mode="json"),
        )
        prompt_artifact = call_artifact(
            "prompt", kind="prompt.template",
            media_type="text/markdown; charset=utf-8", payload=prompt,
        )
        schema_artifact = call_artifact(
            "output-schema", kind="schema.output", payload=schema,
            schema_id=TURN_INTERPRET_OUTPUT_SCHEMA_ID,
        )
        context_artifact = call_artifact(
            "context-packet", kind="probe.context",
            payload={
                "schema_version": "probe_context.v1", "probe_id": probe_id,
                "input": input_value.model_dump(mode="json"),
            },
        )
        manifest_artifact = call_artifact(
            "context-manifest", kind="probe.selection_manifest",
            payload={"schema_version": "probe_selection_manifest.v1", "items": []},
        )
        # V3-5A: immutable binding/config/projection artifacts the resolved call
        # (and fresh-process recovery) reads back; their content hashes bind the
        # request to this exact runtime binding.
        binding_artifact = call_artifact(
            "provider-binding", kind="model.provider_binding", payload=binding,
            schema_id=PROVIDER_BINDING_SCHEMA_ID,
        )
        binding_config_artifact = call_artifact(
            "provider-config", kind="provider.config", payload=config,
        )
        projection_artifact = call_artifact(
            "schema-projection", kind="model.schema_projection",
            payload=projection.report, schema_id=SCHEMA_PROJECTION_SCHEMA_ID,
        )

        request = ModelCallRequest(
            run_id=run_id, session_id=session_id, turn_id=turn_id,
            operation_id=operation_id, attempt_id=attempt_id, attempt=1,
            operation_name=operation.name,
            operation_definition_hash=operation.definition_hash,
            idempotency_key=f"openrouter-live-probe:{run_id}:attempt:1",
            binding_id=binding.binding_id, binding_hash=binding.binding_hash,
            requested_model=binding.requested_model, instructions=prompt,
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
            created_at=started_at, max_output_tokens=operation.max_output_tokens,
        )
        resolved_call = ResolvedModelCall(
            request=request, binding=binding, schema_projection=projection.report
        )
        request_artifact = call_artifact(
            "attempt/1/request", kind="model.request", payload=request,
            schema_id=MODEL_REQUEST_SCHEMA_ID, attempt=True,
        )
        bundle_files["request.json"] = canonical_json(request)

        record_event(
            "event/model-call-started", event_type="model.call.started",
            status=ExecutionStatus.OK, occurred_at=started_at, stage="turn.interpret",
            turn_id=turn_id, operation_id=operation_id, attempt_id=attempt_id, attempt=1,
            input_artifacts=(request_artifact.ref,),
        )

        # ---- one inference POST ----------------------------------------------
        adapter = OpenRouterChatEvalAdapter(
            api_key=api_key, config=config, http_client=client, now=clock
        )
        envelope = await adapter.generate_structured(resolved_call)
        inference_http_calls = 1
        result = envelope.result
        for record in envelope.supporting_artifacts:
            store.put(record)
        result_artifact = call_artifact(
            "attempt/1/result", kind="model.result", payload=result,
            schema_id=MODEL_RESULT_SCHEMA_ID, attempt=True,
            created_at=result.completed_at,
        )
        bundle_files["result.json"] = canonical_json(result)

        supporting_refs = tuple(r.ref for r in envelope.supporting_artifacts)
        if result.outcome == ModelOutcome.FAILED:
            call_event = ("event/model-call-failed", "model.call.failed", ExecutionStatus.FAILED)
        elif result.outcome == ModelOutcome.SUCCEEDED:
            call_event = ("event/model-call-completed", "model.call.completed", ExecutionStatus.OK)
        else:
            call_event = ("event/model-call-completed", "model.call.completed", ExecutionStatus.PARTIAL)
        record_event(
            call_event[0], event_type=call_event[1], status=call_event[2],
            occurred_at=result.completed_at, stage="turn.interpret", turn_id=turn_id,
            operation_id=operation_id, attempt_id=attempt_id, attempt=1,
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
            event_type="workflow.run.completed" if conformance_passed
            else "workflow.run.failed",
            status=ExecutionStatus.OK if conformance_passed else ExecutionStatus.FAILED,
            occurred_at=completed_at, output_artifacts=(result_artifact.ref,),
        )
        manifest = recorder.build_manifest(
            run_id=run_id, completed_at=completed_at,
            root_artifacts=(
                probe_inputs_artifact.ref, request_artifact.ref, result_artifact.ref
            ),
        )
        report = _build_report(
            probe_id=probe_id, run_id=run_id, config=config, probe_inputs=probe_inputs,
            model_snapshot_hash=model_snapshot.snapshot_hash,
            endpoint_snapshot_hash=endpoint_snapshot.snapshot_hash,
            catalog_model_id=model_snapshot.data.get("id"),
            catalog_canonical_slug=preflight_facts.canonical_slug,
            schema_hash=canonical_hash(schema),
            request_artifact=request_artifact, result_artifact=result_artifact,
            result=result, envelope_artifacts=envelope.supporting_artifacts,
            manifest=manifest, local_output_validation_passed=local_output_validation_passed,
            local_validation_error=local_validation_error,
            catalog_http_calls=catalog_http_calls, catalog_statuses=catalog_statuses,
            inference_http_calls=inference_http_calls,
            started_at=started_at, completed_at=completed_at,
        )
        bundle_files.update(
            {
                "events.jsonl": _jsonl(recorder.events(run_id)),
                "artifacts.jsonl": _jsonl(store.all()),
                "manifest.json": canonical_json(manifest),
                "probe-report.json": canonical_json(report),
            }
        )
        _write_bundle(output_dir, run_id=run_id, files=bundle_files)
        _print_summary(
            run_id, "passed" if conformance_passed else "failed",
            output_dir / str(run_id), report,
        )
        return 0 if conformance_passed else 1
    finally:
        if owns_client:
            await client.aclose()


def _routing_facts(
    envelope_artifacts: tuple[ArtifactRecord, ...],
) -> dict[str, Any]:
    for record in envelope_artifacts:
        if record.ref.kind == ROUTING_ARTIFACT_KIND and record.inline_content:
            return json.loads(record.inline_content)
    return {}


def _error_type(envelope_artifacts: tuple[ArtifactRecord, ...]) -> str | None:
    for record in envelope_artifacts:
        if record.ref.kind == "provider.openrouter.error" and record.inline_content:
            return json.loads(record.inline_content).get("error_type")
    return None


def _build_report(
    *,
    probe_id: str,
    run_id: UUID,
    config,
    probe_inputs: OpenRouterProbeInputs,
    model_snapshot_hash: str,
    endpoint_snapshot_hash: str,
    catalog_model_id: str | None,
    catalog_canonical_slug: str,
    schema_hash: str,
    request_artifact: ArtifactRecord,
    result_artifact: ArtifactRecord,
    result: ModelCallResult,
    envelope_artifacts: tuple[ArtifactRecord, ...],
    manifest: RunManifest,
    local_output_validation_passed: bool,
    local_validation_error: str | None,
    catalog_http_calls: int,
    catalog_statuses: list[int],
    inference_http_calls: int,
    started_at: datetime,
    completed_at: datetime,
) -> dict[str, Any]:
    routing = _routing_facts(envelope_artifacts)
    limitations = sorted(
        {PROBE_LIMITATION, PROMOTION_LIMITATION, *result.usage.limitations}
    )
    if probe_inputs.data_collection == "allow":
        limitations = sorted(
            {*limitations, "data_collection=allow run is not production_promotable"}
        )
    if result.provider_request_id is None:
        limitations = sorted(
            {*limitations, "provider HTTP request ID was not returned"}
        )
    return {
        "schema_version": "openrouter_live_probe_report.v1",
        "run_id": str(run_id),
        "probe_id": probe_id,
        "final_config_created": True,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "config_hash": config.config_hash,
        "schema_hash": schema_hash,
        "model_catalog_hash": model_snapshot_hash,
        "endpoint_catalog_hash": endpoint_snapshot_hash,
        "catalog_model_id": catalog_model_id,
        "catalog_canonical_slug": catalog_canonical_slug,
        "catalog_http_calls": catalog_http_calls,
        "catalog_statuses": catalog_statuses,
        "inference_http_calls": inference_http_calls,
        "requested_model": result.requested_model,
        "resolved_model": result.resolved_model,
        "configured_endpoint_slug": config.upstream_endpoint_slug,
        "expected_provider_name": config.expected_upstream_provider_name,
        "selected_provider_name": routing.get("selected_provider_name"),
        "selected_model": routing.get("selected_model"),
        "router_strategy": routing.get("strategy"),
        "router_attempt": routing.get("router_attempt"),
        "router_pipeline": routing.get("pipeline"),
        "generation_id": routing.get("generation_id"),
        "provider_request_id": result.provider_request_id,
        "outcome": result.outcome.value,
        "finish_reason": result.finish_reason.value,
        "provider_finish_reason": result.provider_finish_reason,
        "error_type": _error_type(envelope_artifacts),
        "failure": (
            {
                "kind": result.failure.kind.value,
                "reason_code": result.failure.reason_code,
                "retryable": result.failure.retryable,
            }
            if result.failure is not None else None
        ),
        "refusal": result.refusal.reason_code if result.refusal is not None else None,
        "usage": result.usage.model_dump(mode="json"),
        "cost": routing.get("cost"),
        "usage_total_mismatch": routing.get("usage_total_mismatch"),
        "route_conformance": routing.get("conformance"),
        "local_output_validation_passed": local_output_validation_passed,
        "local_validation_error": local_validation_error,
        "manifest_hash": canonical_hash(manifest),
        "last_event_hash": manifest.last_event_hash,
        "production_promotable": False,
        "limitations": limitations,
        "source_versions": {"httpx": httpx.__version__, "spec": SPEC_PATH},
    }


def _catalog_failure_report(
    *,
    probe_id: str,
    run_id: UUID,
    probe_inputs: OpenRouterProbeInputs,
    stage: str,
    detail: str,
    catalog_http_calls: int,
    catalog_statuses: list[int],
    manifest: RunManifest,
    started_at: datetime,
    completed_at: datetime,
    model_snapshot_hash: str | None = None,
    endpoint_snapshot_hash: str | None = None,
    final_config_created: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": "openrouter_live_probe_report.v1",
        "run_id": str(run_id),
        "probe_id": probe_id,
        "final_config_created": final_config_created,
        "failed_stage": stage,
        "failure_detail": detail,
        "started_at": started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "requested_model": probe_inputs.requested_model,
        "configured_endpoint_slug": probe_inputs.upstream_endpoint_slug,
        "catalog_http_calls": catalog_http_calls,
        "catalog_statuses": catalog_statuses,
        "inference_http_calls": 0,
        "model_catalog_hash": model_snapshot_hash,
        "endpoint_catalog_hash": endpoint_snapshot_hash,
        "outcome": "failed",
        "manifest_hash": canonical_hash(manifest),
        "last_event_hash": manifest.last_event_hash,
        "production_promotable": False,
        "limitations": [PROBE_LIMITATION, PROMOTION_LIMITATION],
        "source_versions": {"httpx": httpx.__version__, "spec": SPEC_PATH},
    }


def _jsonl(items) -> str:
    return "\n".join(canonical_json(item) for item in items)


def _write_bundle(output_dir: Path, *, run_id: UUID, files: dict[str, str]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = output_dir / f".tmp-{run_id}"
    final_dir = output_dir / str(run_id)
    temp_dir.mkdir()
    for name, content in files.items():
        (temp_dir / name).write_text(content + "\n", encoding="utf-8", newline="\n")
    temp_dir.rename(final_dir)
    return final_dir


def _print_summary(run_id: UUID, verdict: str, bundle_dir: Path, report: dict) -> None:
    print(f"openrouter live probe run {run_id}: {verdict}")
    print(f"bundle: {bundle_dir}")
    print(
        "requested={} resolved={} endpoint={} selected_provider={}".format(
            report.get("requested_model"),
            report.get("resolved_model"),
            report.get("configured_endpoint_slug"),
            report.get("selected_provider_name"),
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
