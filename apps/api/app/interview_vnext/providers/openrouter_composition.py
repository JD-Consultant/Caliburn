"""One explicit OpenRouter profile for the local consultant application.

This module is the composition root, not a provider abstraction framework. It
fetches one catalog snapshot pair, verifies the exact development route, and
builds operation-specific bindings over one secret-free provider config.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Mapping

import httpx

from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.operation_documents import (
    question_select_operation,
    turn_interpret_operation,
)

from .openrouter_catalog import (
    OpenRouterEndpointSnapshot,
    OpenRouterModelCatalogClient,
    OpenRouterModelSnapshot,
    PreflightError,
    PreflightFacts,
    preflight,
)
from .openrouter_chat import OpenRouterChatAdapter
from .openrouter_config import (
    OpenRouterChatConfig,
    OpenRouterProbeInputs,
    build_openrouter_binding,
    build_openrouter_config,
)


OPENROUTER_API_KEY_ENV = "OPENROUTER_API_KEY"
DEVELOPMENT_MODEL = "openai/gpt-5.4-mini"
DEVELOPMENT_CANONICAL_MODEL = "openai/gpt-5.4-mini-20260317"
DEVELOPMENT_ENDPOINT = "openai/flex"


class OpenRouterCompositionError(RuntimeError):
    """The fixed local consultant profile could not be constructed safely."""


@dataclass(frozen=True)
class OpenRouterConsultantProfile:
    config: OpenRouterChatConfig
    model_snapshot: OpenRouterModelSnapshot
    endpoint_snapshot: OpenRouterEndpointSnapshot
    preflight_facts: PreflightFacts
    turn_interpret_binding: ProviderBinding
    question_select_binding: ProviderBinding


def load_openrouter_api_key(
    environ: Mapping[str, str] | None = None,
) -> str:
    """Read the only provider secret without copying it into typed config."""

    source = os.environ if environ is None else environ
    value = source.get(OPENROUTER_API_KEY_ENV)
    if value is None or not value.strip():
        raise OpenRouterCompositionError(
            f"{OPENROUTER_API_KEY_ENV} is required"
        )
    return value


async def build_openrouter_consultant_profile(
    *,
    api_key: str,
    contains_test_data: bool,
    http_client: httpx.AsyncClient | None = None,
    now: datetime | None = None,
) -> OpenRouterConsultantProfile:
    """Fetch and preflight the one approved GPT-5.4 mini flex profile."""

    probe = OpenRouterProbeInputs(
        requested_model=DEVELOPMENT_MODEL,
        upstream_endpoint_slug=DEVELOPMENT_ENDPOINT,
        data_collection="deny",
        zdr_required=False,
        reasoning_effort="low",
    )
    client = OpenRouterModelCatalogClient(
        api_key=api_key,
        http_client=http_client,
    )
    try:
        model_snapshot = await client.fetch_model(probe.requested_model)
        endpoint_snapshot = await client.fetch_endpoints(probe.requested_model)
    finally:
        if http_client is None:
            await client.aclose()

    try:
        config = build_openrouter_config(
            probe,
            model_snapshot,
            endpoint_snapshot,
            contains_test_data=contains_test_data,
        )
        if config.catalog_canonical_model != DEVELOPMENT_CANONICAL_MODEL:
            raise OpenRouterCompositionError(
                "GPT-5.4 mini canonical model changed; review the catalog "
                "before running inference"
            )
        facts = preflight(
            model_snapshot=model_snapshot,
            endpoint_snapshot=endpoint_snapshot,
            requested_model=probe.requested_model,
            upstream_endpoint_slug=probe.upstream_endpoint_slug,
            reasoning_effort=probe.reasoning_effort,
            reasoning_max_tokens=probe.reasoning_max_tokens,
            required_output_tokens=max(
                turn_interpret_operation().max_output_tokens,
                question_select_operation().max_output_tokens,
            ),
            now=now or datetime.now(UTC),
        )
    except (PreflightError, ValueError) as exc:
        raise OpenRouterCompositionError(str(exc)) from exc

    reasoning_policy = "effort-low-excluded"
    return OpenRouterConsultantProfile(
        config=config,
        model_snapshot=model_snapshot,
        endpoint_snapshot=endpoint_snapshot,
        preflight_facts=facts,
        turn_interpret_binding=build_openrouter_binding(
            config,
            operation_name="turn.interpret",
            binding_id="openrouter-gpt-5.4-mini-flex-turn-interpret-v1",
            quality_profile="turn-interpret-verifier-v2",
            reasoning_policy=reasoning_policy,
        ),
        question_select_binding=build_openrouter_binding(
            config,
            operation_name="question.select",
            binding_id="openrouter-gpt-5.4-mini-flex-question-select-v1",
            quality_profile="question-select-verifier-v1",
            reasoning_policy=reasoning_policy,
        ),
    )


def build_openrouter_consultant_adapter(
    profile: OpenRouterConsultantProfile,
    *,
    api_key: str,
    http_client: httpx.AsyncClient | None = None,
) -> OpenRouterChatAdapter:
    return OpenRouterChatAdapter(
        api_key=api_key,
        config=profile.config,
        http_client=http_client,
    )
