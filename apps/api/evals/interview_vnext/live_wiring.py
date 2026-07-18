"""Live OpenRouter batch wiring: catalog snapshot + config + eval DB safety (§10/§17.3).

The batch fetches model/endpoints snapshots exactly once, derives the immutable
``OpenRouterChatEvalConfig`` from them (never hardcoding a prior probe's catalog
hash), and reuses one adapter across every trial. Eval DB access only reads a
named environment variable and refuses any database whose name is not clearly a
test/eval database, so a batch can never touch the ``caliburn`` production DB.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx

from app.interview_vnext.application.operation_executor import (
    TurnInterpretProviderProfile,
)
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.result import ModelCallResult

from .openrouter_model_catalog import (
    OpenRouterEndpointSnapshot,
    OpenRouterModelCatalogClient,
    OpenRouterModelSnapshot,
    preflight,
)
from .openrouter_provider_config import (
    OpenRouterChatEvalConfig,
    OpenRouterProbeInputs,
    build_openrouter_eval_config,
)
from .providers.openrouter_chat import OpenRouterChatEvalAdapter
from .providers.openrouter_chat import ROUTING_ARTIFACT_KIND
from .capture_export import CaptureBundle
from .contracts import TrialAttemptRecord, TrialRouteEvidence


API_KEY_ENV = "OPENROUTER_API_KEY"


class EvalDatabaseError(ValueError):
    """The requested eval database URL is missing or unsafe (§17.3)."""


def resolve_eval_database_url(env_name: str) -> str:
    """Read the eval DB URL only from ``env_name``; reject non-test databases.

    Full URLs are never accepted as a CLI argument — the caller passes the
    environment variable *name*, and the database must end in ``_test``/``_eval``
    so a batch can never point at the ``caliburn`` production database (§17.3).
    """

    url = os.environ.get(env_name)
    if not url:
        raise EvalDatabaseError(
            f"eval database env var {env_name!r} is not set"
        )
    tail = url.rsplit("/", 1)[-1].split("?", 1)[0]
    if not (tail.endswith("_test") or tail.endswith("_eval")):
        raise EvalDatabaseError(
            "eval database name must end with '_test' or '_eval'; "
            f"refusing {tail!r} (production DB is never eligible)"
        )
    return url


@dataclass(frozen=True)
class LiveBatchProfile:
    """Immutable per-batch route:snapshots + config + provider profile."""

    config: OpenRouterChatEvalConfig
    model_snapshot: OpenRouterModelSnapshot
    endpoint_snapshot: OpenRouterEndpointSnapshot
    provider_profile: TurnInterpretProviderProfile


class LivePreflightError(RuntimeError):
    """Catalog/config/preflight failed before any inference (exit code 3)."""


async def build_live_batch_profile(
    *,
    api_key: str,
    probe_inputs: OpenRouterProbeInputs,
    reasoning_effort: str | None,
    http_client: httpx.AsyncClient | None = None,
) -> LiveBatchProfile:
    """Fetch one snapshot pair, build the config and run preflight (§10.1)."""

    client = OpenRouterModelCatalogClient(api_key=api_key, http_client=http_client)
    try:
        model_snapshot = await client.fetch_model(probe_inputs.requested_model)
        endpoint_snapshot = await client.fetch_endpoints(probe_inputs.requested_model)
    finally:
        if http_client is None:
            await client.aclose()

    try:
        config = build_openrouter_eval_config(
            probe_inputs, model_snapshot, endpoint_snapshot
        )
        preflight(
            model_snapshot=model_snapshot,
            endpoint_snapshot=endpoint_snapshot,
            requested_model=probe_inputs.requested_model,
            upstream_endpoint_slug=probe_inputs.upstream_endpoint_slug,
            reasoning_effort=reasoning_effort,
            reasoning_max_tokens=probe_inputs.reasoning_max_tokens,
            required_output_tokens=turn_interpret_operation().max_output_tokens,
            now=datetime.now(UTC),
        )
    except Exception as exc:  # noqa: BLE001 — surface as preflight failure (exit 3)
        raise LivePreflightError(str(exc)) from exc

    return LiveBatchProfile(
        config=config,
        model_snapshot=model_snapshot,
        endpoint_snapshot=endpoint_snapshot,
        provider_profile=TurnInterpretProviderProfile(
            provider="openrouter",
            requested_model=probe_inputs.requested_model,
        ),
    )


def build_live_adapter(
    profile: LiveBatchProfile,
    *,
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
) -> OpenRouterChatEvalAdapter:
    """One adapter over the batch's immutable config, reused across trials."""

    return OpenRouterChatEvalAdapter(
        api_key=api_key, config=profile.config, http_client=http_client
    )


def _json_payload(record) -> dict:
    if record.inline_content is None:
        return {}
    try:
        value = json.loads(record.inline_content)
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _decimal_cost(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed >= 0 else None


def openrouter_attempt_records(
    capture: CaptureBundle,
) -> tuple[TrialAttemptRecord, ...]:
    """Recover every durable provider attempt plus route/cost evidence.

    ``TurnInterpretExecutionOutcome`` only exposes the terminal provider result;
    retries remain authoritative in Capture.  The live batch therefore rebuilds
    the attempt ledger from immutable ``model.result`` and routing artifacts.
    """

    routes = {
        record.attempt_id: _json_payload(record)
        for record in capture.artifacts
        if record.ref.kind == ROUTING_ARTIFACT_KIND and record.attempt_id is not None
    }
    errors = {
        record.attempt_id: _json_payload(record)
        for record in capture.artifacts
        if record.ref.kind == "provider.openrouter.error" and record.attempt_id is not None
    }
    results: list[ModelCallResult] = []
    for record in capture.artifacts:
        if record.ref.kind != "model.result" or record.inline_content is None:
            continue
        results.append(ModelCallResult.model_validate_json(record.inline_content))

    attempts: list[TrialAttemptRecord] = []
    for result in sorted(results, key=lambda item: item.attempt):
        route_payload = routes.get(result.attempt_id)
        error_payload = errors.get(result.attempt_id, {})
        route = None
        generation_id = error_payload.get("generation_id")
        cost = None
        if route_payload is not None:
            conformance = route_payload.get("conformance")
            conformance = conformance if isinstance(conformance, dict) else {}
            failed_checks = tuple(
                sorted(
                    name
                    for name, passed in conformance.items()
                    if passed is not True
                )
            )
            route = TrialRouteEvidence(
                metadata_present=conformance.get("metadata_present") is True,
                strategy=route_payload.get("strategy"),
                selected_provider_name=route_payload.get("selected_provider_name"),
                selected_model=route_payload.get("selected_model"),
                single_upstream_attempt=conformance.get("single_upstream_attempt"),
                pipeline_clean=conformance.get("pipeline_clean"),
                failures=failed_checks,
            )
            generation_id = route_payload.get("generation_id") or generation_id
            cost = _decimal_cost(route_payload.get("cost"))
        attempts.append(
            TrialAttemptRecord(
                attempt=result.attempt,
                outcome=result.outcome,
                finish_reason=result.finish_reason,
                failure_kind=result.failure.kind if result.failure else None,
                reason_code=(
                    result.failure.reason_code if result.failure else None
                ),
                retryable=(result.failure.retryable if result.failure else None),
                resolved_model=result.resolved_model,
                provider_request_id=result.provider_request_id,
                generation_id=(
                    generation_id if isinstance(generation_id, str) else None
                ),
                usage=result.usage,
                observed_cost_usd=cost,
                latency_ms=result.latency_ms,
                route=route,
            )
        )
    return tuple(attempts)


def openrouter_observed_cost(capture: CaptureBundle) -> Decimal | None:
    costs = [
        item.observed_cost_usd
        for item in openrouter_attempt_records(capture)
        if item.observed_cost_usd is not None
    ]
    return sum(costs, Decimal(0)) if costs else None


def openrouter_route_is_clean(attempt: TrialAttemptRecord) -> bool:
    route = attempt.route
    return bool(
        route is not None
        and route.metadata_present
        and route.single_upstream_attempt is True
        and route.pipeline_clean is True
        and not route.failures
    )
