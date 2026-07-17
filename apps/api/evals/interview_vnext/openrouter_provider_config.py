"""Secret-free OpenRouter Chat eval profile (V3-4R §5).

Hard invariants (single exact route, fallback off, metadata on, mutating
plugins disabled, no transport retry) are typed as `Literal` so they appear in
the config dump/hash yet cannot be overridden by a caller. API keys and
environment secrets must never enter this model.

The only public construction path for real runs is
`build_openrouter_eval_config()`, which derives the accepted resolved model,
the expected upstream provider identity and both catalog hashes from verified
model/endpoint snapshots. Tests may call the Pydantic constructor directly to
build invalid cases.

規格:docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256

from .openrouter_model_catalog import (
    OpenRouterEndpointSnapshot,
    OpenRouterModelSnapshot,
    matched_endpoints,
)


OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# §5.1: fixed tuple; every known mutating/plugin surface is explicitly disabled.
DISABLED_PLUGINS: tuple[str, ...] = (
    "context-compression",
    "response-healing",
    "web",
    "file-parser",
)

# Superset accepted by the config type; the model snapshot's
# `reasoning.supported_efforts` gate (§6.2) is the run-time authority.
OpenRouterReasoningEffort = Literal["minimal", "low", "medium", "high", "xhigh", "max"]

_FORBIDDEN_MODELS = frozenset({"openrouter/auto", "openrouter/free"})
_FORBIDDEN_VARIANT_SUFFIXES = (":free", ":nitro", ":floor", ":online", ":latest")


def _validate_model_slug(value: str) -> None:
    if value != value.strip():
        raise ValueError("model slug cannot contain surrounding whitespace")
    if value.startswith("~"):
        raise ValueError("model slug cannot use a '~' alias prefix")
    if value in _FORBIDDEN_MODELS:
        raise ValueError(f"model slug {value!r} is a router alias, not a canonical model")
    for suffix in _FORBIDDEN_VARIANT_SUFFIXES:
        if value.endswith(suffix):
            raise ValueError(
                f"model slug cannot use the {suffix!r} variant shortcut; "
                "use the exact canonical slug"
            )
    if ":" in value:
        raise ValueError("model slug cannot contain a ':' variant shortcut")
    author, separator, slug = value.partition("/")
    if not separator or not author or not slug or "/" in slug:
        raise ValueError("model slug must be exactly 'author/slug'")
    if slug == "latest" or slug.endswith("-latest"):
        raise ValueError("model slug cannot use a 'latest' alias")


def _validate_endpoint_slug(value: str) -> None:
    if value != value.strip():
        raise ValueError("endpoint slug cannot contain surrounding whitespace")
    if not value or any(character.isspace() for character in value):
        raise ValueError("endpoint slug cannot contain whitespace")
    if ":" in value:
        raise ValueError("endpoint slug cannot contain a ':' shortcut")


class OpenRouterChatEvalConfig(DomainModel):
    schema_version: Literal["openrouter_chat_eval_config.v1"] = (
        "openrouter_chat_eval_config.v1"
    )
    provider: Literal["openrouter"] = "openrouter"
    api_format: Literal["chat_completions"] = "chat_completions"
    base_url: Literal["https://openrouter.ai/api/v1"] = OPENROUTER_BASE_URL
    requested_model: NonEmptyText
    accepted_resolved_models: tuple[NonEmptyText, ...]
    upstream_endpoint_slug: NonEmptyText
    expected_upstream_provider_name: NonEmptyText
    model_catalog_hash: Sha256
    endpoint_catalog_hash: Sha256
    provider_order: tuple[NonEmptyText, ...]
    provider_only: tuple[NonEmptyText, ...]
    allow_fallbacks: Literal[False] = False
    require_parameters: Literal[True] = True
    data_collection: Literal["deny", "allow"]
    zdr_required: bool
    reasoning_effort: OpenRouterReasoningEffort | None = None
    reasoning_max_tokens: int | None = Field(default=None, ge=1)
    reasoning_exclude: Literal[True] = True
    connect_timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)
    stream: Literal[False] = False
    choice_count: Literal[1] = 1
    response_format: Literal["json_schema"] = "json_schema"
    strict_schema: Literal[True] = True
    router_metadata: Literal[True] = True
    disabled_plugins: tuple[str, ...] = DISABLED_PLUGINS
    transport_retries: Literal[0] = 0
    response_cache: Literal[False] = False
    session_sticky_routing: Literal[False] = False
    contains_test_data: Literal[True] = True

    @model_validator(mode="after")
    def structural_invariants(self) -> "OpenRouterChatEvalConfig":
        _validate_model_slug(self.requested_model)
        _validate_endpoint_slug(self.upstream_endpoint_slug)
        if self.accepted_resolved_models != (self.requested_model,):
            raise ValueError(
                "accepted resolved models must be exactly the requested canonical model"
            )
        if self.provider_order != (self.upstream_endpoint_slug,):
            raise ValueError(
                "provider order must contain exactly the configured endpoint slug"
            )
        if self.provider_only != (self.upstream_endpoint_slug,):
            raise ValueError(
                "provider only must contain exactly the configured endpoint slug"
            )
        if self.disabled_plugins != DISABLED_PLUGINS:
            raise ValueError(
                "disabled plugins must exactly equal the fixed benchmark tuple"
            )
        if self.reasoning_effort is not None and self.reasoning_max_tokens is not None:
            raise ValueError("reasoning effort and max tokens are mutually exclusive")
        return self

    @property
    def reasoning_enabled(self) -> bool:
        return self.reasoning_effort is not None or self.reasoning_max_tokens is not None

    @property
    def config_hash(self) -> str:
        return canonical_hash(self)


class OpenRouterProbeInputs(DomainModel):
    """Secret-free CLI/runner selections captured before snapshots exist."""

    schema_version: Literal["openrouter_probe_inputs.v1"] = "openrouter_probe_inputs.v1"
    requested_model: NonEmptyText
    upstream_endpoint_slug: NonEmptyText
    data_collection: Literal["deny", "allow"]
    zdr_required: bool
    reasoning_effort: OpenRouterReasoningEffort | None = None
    reasoning_max_tokens: int | None = Field(default=None, ge=1)
    connect_timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)

    @model_validator(mode="after")
    def structural_invariants(self) -> "OpenRouterProbeInputs":
        _validate_model_slug(self.requested_model)
        _validate_endpoint_slug(self.upstream_endpoint_slug)
        if self.reasoning_effort is not None and self.reasoning_max_tokens is not None:
            raise ValueError("reasoning effort and max tokens are mutually exclusive")
        return self


class ConfigConstructionError(ValueError):
    """Snapshot-derived config construction failed before any inference."""


def build_openrouter_eval_config(
    probe_inputs: OpenRouterProbeInputs,
    model_snapshot: OpenRouterModelSnapshot,
    endpoint_snapshot: OpenRouterEndpointSnapshot,
) -> OpenRouterChatEvalConfig:
    """Sole public construction path (§5.1).

    Derives the accepted resolved model from the requested model, the expected
    upstream provider name from the unique endpoint the configured slug matches
    in the snapshot, and binds both catalog content hashes.
    """

    if model_snapshot.requested_model != probe_inputs.requested_model:
        raise ConfigConstructionError(
            "model snapshot does not belong to the requested model"
        )
    if endpoint_snapshot.requested_model != probe_inputs.requested_model:
        raise ConfigConstructionError(
            "endpoint snapshot does not belong to the requested model"
        )
    matches = matched_endpoints(
        probe_inputs.upstream_endpoint_slug, endpoint_snapshot
    )
    if len(matches) != 1:
        raise ConfigConstructionError(
            "configured endpoint slug must match exactly one endpoint in the snapshot; "
            f"matched {len(matches)}"
        )
    endpoint = matches[0]
    if not endpoint.provider_name:
        raise ConfigConstructionError(
            "matched endpoint snapshot entry does not expose a provider identity"
        )
    return OpenRouterChatEvalConfig(
        requested_model=probe_inputs.requested_model,
        accepted_resolved_models=(probe_inputs.requested_model,),
        upstream_endpoint_slug=probe_inputs.upstream_endpoint_slug,
        expected_upstream_provider_name=endpoint.provider_name,
        model_catalog_hash=model_snapshot.snapshot_hash,
        endpoint_catalog_hash=endpoint_snapshot.snapshot_hash,
        provider_order=(probe_inputs.upstream_endpoint_slug,),
        provider_only=(probe_inputs.upstream_endpoint_slug,),
        data_collection=probe_inputs.data_collection,
        zdr_required=probe_inputs.zdr_required,
        reasoning_effort=probe_inputs.reasoning_effort,
        reasoning_max_tokens=probe_inputs.reasoning_max_tokens,
        connect_timeout_seconds=probe_inputs.connect_timeout_seconds,
    )
