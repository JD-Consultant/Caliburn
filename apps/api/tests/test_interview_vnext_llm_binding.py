"""V3-5A R2:`ProviderBinding.v1` runtime binding identity(§6.1/§14.1)。

Binding 是 hash-addressed、caller 不可偽造的 runtime selection artifact:
ordered tuple 排序、requested model 必在 accepted 集合、OpenRouter 必填
upstream identity、secret 樣式字串直接 reject、hash 由 definition 重算。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.llm.binding import (
    ProviderBinding,
    ProviderBindingDefinition,
    define_provider_binding,
)
from app.interview_vnext.llm.operation import ContractIdentity


PROJECTION_POLICY = ContractIdentity(
    name="portable-strict-output", version="2.0.0",
    content_hash="sha256:" + "1" * 64,
)
CONFORMANCE_POLICY = ContractIdentity(
    name="attribution-strict", version="1.0.0",
    content_hash="sha256:" + "2" * 64,
)


def binding_values(**overrides) -> dict:
    values = dict(
        binding_id="turn-interpret-c1-openrouter-attribution-strict",
        operation_name="turn.interpret",
        quality_profile="turn-interpret-c1-high-precision",
        adapter_id="openrouter.chat-completions",
        adapter_version="2.0.0",
        gateway_provider="openrouter",
        requested_model="anthropic/claude-sonnet-5",
        accepted_gateway_models=("anthropic/claude-sonnet-5",),
        upstream_provider="Anthropic",
        upstream_endpoint="anthropic",
        accepted_upstream_models=(
            "anthropic/claude-sonnet-5",
            "claude-sonnet-5-20250929",
        ),
        required_capabilities=(
            "routing-metadata",
            "single-choice",
            "structured-output.native-json-schema",
            "usage.cost",
            "usage.tokens",
        ),
        schema_projection_policy=PROJECTION_POLICY,
        conformance_policy=CONFORMANCE_POLICY,
        storage_policy="stateless-no-provider-store",
        cache_policy="disabled",
        reasoning_policy="medium-excluded",
        data_collection_policy="deny",
        provider_config_hash="sha256:" + "3" * 64,
    )
    values.update(overrides)
    return values


def test_define_provider_binding_hashes_the_definition():
    binding = define_provider_binding(**binding_values())
    definition = ProviderBindingDefinition(**binding_values())
    assert binding.binding_hash == canonical_hash(definition)
    assert binding.schema_version == "provider_binding.v1"
    assert binding.retry_owner == "executor"
    assert binding.provider_internal_retries == 0


def test_forged_binding_hash_is_rejected():
    with pytest.raises(ValidationError, match="hash"):
        ProviderBinding(
            **binding_values(), binding_hash="sha256:" + "0" * 64
        )


def test_retry_ownership_cannot_be_reassigned():
    with pytest.raises(ValidationError):
        define_provider_binding(**binding_values(), retry_owner="adapter")
    with pytest.raises(ValidationError):
        define_provider_binding(**binding_values(), provider_internal_retries=1)


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "accepted_upstream_models",
            ("claude-sonnet-5-20250929", "anthropic/claude-sonnet-5"),
        ),
        (
            "accepted_upstream_models",
            ("anthropic/claude-sonnet-5", "anthropic/claude-sonnet-5"),
        ),
        ("required_capabilities", ("usage.tokens", "usage.cost")),
        ("required_capabilities", ("usage.cost", "usage.cost")),
        (
            "accepted_gateway_models",
            ("anthropic/claude-sonnet-5", "anthropic/claude-sonnet-5"),
        ),
    ],
)
def test_unsorted_or_duplicate_ordered_tuples_are_rejected(field, value):
    with pytest.raises(ValidationError, match="sorted|unique"):
        define_provider_binding(**binding_values(**{field: value}))


def test_requested_model_must_be_in_accepted_gateway_models():
    with pytest.raises(ValidationError, match="accepted gateway"):
        define_provider_binding(
            **binding_values(accepted_gateway_models=("other/model",))
        )


def test_openrouter_binding_requires_upstream_identity():
    with pytest.raises(ValidationError, match="upstream"):
        define_provider_binding(**binding_values(upstream_provider=None))
    with pytest.raises(ValidationError, match="upstream"):
        define_provider_binding(**binding_values(upstream_endpoint=None))


def test_scripted_binding_may_use_scripted_identity():
    binding = define_provider_binding(
        **binding_values(
            binding_id="turn-interpret-c1-scripted",
            adapter_id="scripted",
            adapter_version="1.0.0",
            gateway_provider="scripted",
            requested_model="scripted-reference",
            accepted_gateway_models=("scripted-reference",),
            upstream_provider="scripted",
            upstream_endpoint="scripted",
            accepted_upstream_models=("scripted-reference",),
        )
    )
    assert binding.gateway_provider == "scripted"
    assert binding.upstream_provider == "scripted"


@pytest.mark.parametrize(
    "field,value",
    [
        ("requested_model", "sk-or-v1-0123456789abcdef"),
        ("requested_model", "Bearer abcdef.ghijkl"),
        ("upstream_provider", "sk-0123456789012345678901234567890123456789"),
        ("upstream_endpoint", "OPENROUTER_API_KEY"),
    ],
)
def test_secret_like_values_are_rejected(field, value):
    with pytest.raises(ValidationError, match="secret"):
        define_provider_binding(**binding_values(**{field: value}))


def test_binding_does_not_accept_arbitrary_provider_options():
    with pytest.raises(ValidationError):
        define_provider_binding(
            **binding_values(), provider_options={"transforms": []}
        )
