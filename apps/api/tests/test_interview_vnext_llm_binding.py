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
    RuntimeBindingMismatch,
    define_provider_binding,
    require_runtime_binding,
)
from app.interview_vnext.llm.operation import ContractIdentity
from app.interview_vnext.llm.result import FailureKind


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


# ---- R3-C1 runtime adapter/binding preflight(修正計畫 §5.1/§6.1)----------


def runtime_identity(binding: ProviderBinding) -> dict:
    """The exact runtime facts an adapter must present before any HTTP call."""

    return dict(
        adapter_id=binding.adapter_id,
        adapter_version=binding.adapter_version,
        gateway_provider=binding.gateway_provider,
        provider_config_hash=binding.provider_config_hash,
    )


class TestRequireRuntimeBinding:
    def test_exact_runtime_identity_passes(self):
        binding = define_provider_binding(**binding_values())
        assert require_runtime_binding(binding, **runtime_identity(binding)) is None

    @pytest.mark.parametrize(
        "field,value,match",
        [
            ("adapter_id", "openai.responses", "adapter id"),
            ("adapter_version", "1.9.0", "adapter version"),
            ("gateway_provider", "openai", "gateway provider"),
            ("provider_config_hash", "sha256:" + "9" * 64, "config hash"),
        ],
    )
    def test_any_runtime_identity_mismatch_fails_closed(self, field, value, match):
        binding = define_provider_binding(**binding_values())
        identity = runtime_identity(binding)
        identity[field] = value
        with pytest.raises(RuntimeBindingMismatch, match=match):
            require_runtime_binding(binding, **identity)

    def test_config_hash_mismatch_alone_rejects_even_with_same_model(self):
        """§7.1.7:requested model 相同、只有 config hash 不同仍拒絕。"""

        binding = define_provider_binding(**binding_values())
        drifted = runtime_identity(binding)
        drifted["provider_config_hash"] = "sha256:" + "a" * 64
        with pytest.raises(RuntimeBindingMismatch):
            require_runtime_binding(binding, **drifted)

    def test_mismatch_is_a_value_error_and_names_no_secret(self):
        binding = define_provider_binding(**binding_values())
        identity = runtime_identity(binding)
        identity["provider_config_hash"] = "sha256:" + "9" * 64
        with pytest.raises(RuntimeBindingMismatch) as excinfo:
            require_runtime_binding(binding, **identity)
        assert isinstance(excinfo.value, ValueError)
        # 訊息可含 hash,但不得含 config 值或 key 樣式字串(§5.1)。
        assert "sk-" not in str(excinfo.value)
        assert "Bearer" not in str(excinfo.value)

    def test_runtime_binding_mismatch_failure_kind_is_published(self):
        """§6.1:neutral failure kind,active v2 corrective enum addition。"""

        assert FailureKind.RUNTIME_BINDING_MISMATCH.value == "runtime_binding_mismatch"
