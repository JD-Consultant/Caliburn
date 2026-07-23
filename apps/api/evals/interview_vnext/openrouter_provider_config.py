"""Compatibility aliases for the production OpenRouter profile."""

from app.interview_vnext.providers.openrouter_config import (
    DISABLED_PLUGINS,
    OPENROUTER_ADAPTER_ID,
    OPENROUTER_ADAPTER_VERSION,
    OPENROUTER_BASE_URL,
    ConfigConstructionError,
    OpenRouterChatConfig,
    OpenRouterProbeInputs,
    OpenRouterReasoningEffort,
    build_openrouter_binding,
    build_openrouter_config,
)

OpenRouterChatEvalConfig = OpenRouterChatConfig


def build_openrouter_eval_config(*args, **kwargs):
    return build_openrouter_config(*args, **kwargs)


def build_openrouter_eval_binding(
    config,
    *,
    operation_name="turn.interpret",
    binding_id="turn-interpret-c1-openrouter-attribution-strict",
    quality_profile="turn-interpret-c1-high-precision",
    reasoning_policy="medium-excluded",
):
    return build_openrouter_binding(
        config,
        operation_name=operation_name,
        binding_id=binding_id,
        quality_profile=quality_profile,
        reasoning_policy=reasoning_policy,
    )


__all__ = [
    "DISABLED_PLUGINS",
    "OPENROUTER_ADAPTER_ID",
    "OPENROUTER_ADAPTER_VERSION",
    "OPENROUTER_BASE_URL",
    "ConfigConstructionError",
    "OpenRouterChatEvalConfig",
    "OpenRouterProbeInputs",
    "OpenRouterReasoningEffort",
    "build_openrouter_eval_binding",
    "build_openrouter_eval_config",
]
