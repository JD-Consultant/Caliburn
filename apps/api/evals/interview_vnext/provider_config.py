"""Secret-free OpenAI Responses eval profile (V3-4).

Hard invariants (stateless call, no SDK retry, disabled truncation) are typed as
`Literal` so they appear in the config dump/hash yet cannot be overridden by a
caller. API keys and environment secrets must never enter this model.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText
from app.interview_vnext.llm.binding import ProviderBinding, define_provider_binding
from app.interview_vnext.llm.conformance import ATTRIBUTION_STRICT_POLICY_V1
from app.interview_vnext.llm.operation import ContractIdentity
from app.interview_vnext.llm.portable_schema import PORTABLE_STRICT_OUTPUT_POLICY_V2


# SDK 2.46.0 accepted reasoning efforts; the V3-4 baseline only exercises "medium".
ReasoningEffort = Literal["none", "minimal", "low", "medium", "high", "xhigh", "max"]

DEFAULT_REQUESTED_MODEL = "gpt-5.6"
DEFAULT_ACCEPTED_RESOLVED_MODELS: tuple[str, ...] = ("gpt-5.6", "gpt-5.6-sol")


class OpenAIResponsesEvalConfig(DomainModel):
    schema_version: Literal["openai_responses_eval_config.v1"] = (
        "openai_responses_eval_config.v1"
    )
    provider: Literal["openai"] = "openai"
    requested_model: NonEmptyText = DEFAULT_REQUESTED_MODEL
    accepted_resolved_models: tuple[NonEmptyText, ...] = (
        DEFAULT_ACCEPTED_RESOLVED_MODELS
    )
    reasoning_mode: Literal["standard"] = "standard"
    reasoning_effort: ReasoningEffort = "medium"
    service_tier: Literal["default"] = "default"
    connect_timeout_seconds: float = Field(default=10.0, gt=0.0, le=60.0)
    store: Literal[False] = False
    background: Literal[False] = False
    stream: Literal[False] = False
    truncation: Literal["disabled"] = "disabled"
    sdk_max_retries: Literal[0] = 0
    contains_test_data: Literal[True] = True

    @model_validator(mode="after")
    def accepted_models_are_unique_and_sorted(self) -> "OpenAIResponsesEvalConfig":
        if not self.accepted_resolved_models:
            raise ValueError("accepted resolved models cannot be empty")
        if (
            tuple(sorted(set(self.accepted_resolved_models)))
            != self.accepted_resolved_models
        ):
            raise ValueError("accepted resolved models must be unique and sorted")
        return self

    @property
    def config_hash(self) -> str:
        return canonical_hash(self)


OPENAI_ADAPTER_ID = "openai.responses"
OPENAI_ADAPTER_VERSION = "2.0.0"


def build_openai_reference_binding(
    config: OpenAIResponsesEvalConfig,
    *,
    operation_name: str = "turn.interpret",
    binding_id: str = "turn-interpret-c1-openai-reference-attribution-strict",
    quality_profile: str = "turn-interpret-c1-high-precision",
    reasoning_policy: str = "medium-standard",
) -> ProviderBinding:
    """OpenAI Responses **reference-only** binding (ADR 0036 §8.3).

    The direct reference adapter only proves the neutral v2 contract holds across
    a second provider; the gateway is ``openai`` with the stable logical
    ``responses`` endpoint. This binding is mocked/reference only — it is never run
    live and asserting it grants no live-run or promotion authorization. ``usage.cost``
    is deliberately absent from the required capabilities: the Responses API does
    not expose per-call cost, so the adapter records ``cost_decimal=None`` and the
    binding must not claim a capability the adapter cannot satisfy.
    """

    accepted_upstream = tuple(sorted(set(config.accepted_resolved_models)))
    return define_provider_binding(
        binding_id=binding_id,
        operation_name=operation_name,
        quality_profile=quality_profile,
        adapter_id=OPENAI_ADAPTER_ID,
        adapter_version=OPENAI_ADAPTER_VERSION,
        gateway_provider=config.provider,
        requested_model=config.requested_model,
        accepted_gateway_models=accepted_upstream,
        upstream_provider="OpenAI",
        upstream_endpoint="responses",
        accepted_upstream_models=accepted_upstream,
        required_capabilities=(
            "single-choice",
            "structured-output.native-json-schema",
            "usage.tokens",
        ),
        schema_projection_policy=ContractIdentity(
            name=PORTABLE_STRICT_OUTPUT_POLICY_V2.name,
            version=PORTABLE_STRICT_OUTPUT_POLICY_V2.version,
            content_hash=PORTABLE_STRICT_OUTPUT_POLICY_V2.policy_hash,
        ),
        conformance_policy=ContractIdentity(
            name=ATTRIBUTION_STRICT_POLICY_V1.name,
            version=ATTRIBUTION_STRICT_POLICY_V1.version,
            content_hash=ATTRIBUTION_STRICT_POLICY_V1.policy_hash,
        ),
        storage_policy="stateless-no-provider-store",
        cache_policy="disabled",
        reasoning_policy=reasoning_policy,
        data_collection_policy="deny",
        provider_config_hash=config.config_hash,
    )
