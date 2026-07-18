"""Live OpenRouter batch wiring: catalog snapshot + config + eval DB safety (§10/§17.3).

The batch fetches model/endpoints snapshots exactly once, derives the immutable
``OpenRouterChatEvalConfig`` from them (never hardcoding a prior probe's catalog
hash), and reuses one adapter across every trial. Eval DB access only reads a
named environment variable and refuses any database whose name is not clearly a
test/eval database, so a batch can never touch the ``caliburn`` production DB.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx

from app.interview_vnext.application.operation_executor import (
    TurnInterpretProviderProfile,
)
from app.interview_vnext.llm.operation_documents import turn_interpret_operation

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
