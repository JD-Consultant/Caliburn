"""Formal OpenRouter/Luna model assembly for the App's three LLM roles.

The caller owns the credential and HTTP clients.  This module only creates
role-scoped model objects over the existing shared transport; it does not bind
prompts, tools, document scope, background scheduling, or provider fallback.
"""

from __future__ import annotations

from dataclasses import dataclass

from .background_memory_limits import FORMAL_BACKGROUND_MEMORY_LIMITS
from .consultant_model import (
    CONSULTANT_MODEL,
    REASONING_EFFORT,
    create_consultant_model,
)
from .openrouter_model import ReceiptChatOpenRouter, create_openrouter_model


@dataclass(frozen=True, repr=False)
class RoleModels:
    consultant: ReceiptChatOpenRouter
    case: ReceiptChatOpenRouter
    understanding: ReceiptChatOpenRouter


def create_role_models(*, api_key: str, http_client, async_http_client) -> RoleModels:
    """Create A, B1 and B2 without performing a provider request."""
    shared = {
        "model": CONSULTANT_MODEL,
        "api_key": api_key,
        "http_client": http_client,
        "async_http_client": async_http_client,
        "reasoning_effort": REASONING_EFFORT,
        "max_retries": 0,
    }
    consultant = create_consultant_model(
        api_key=api_key,
        http_client=http_client,
        async_http_client=async_http_client,
    )
    limits = FORMAL_BACKGROUND_MEMORY_LIMITS
    case = create_openrouter_model(
        component="background-case-maintainer",
        request_timeout=limits.request_timeout_seconds,
        max_output_tokens=limits.case_max_output_tokens,
        **shared,
    )
    understanding = create_openrouter_model(
        component="background-understanding-maintainer",
        request_timeout=limits.request_timeout_seconds,
        max_output_tokens=limits.understanding_max_output_tokens,
        **shared,
    )
    return RoleModels(
        consultant=consultant,
        case=case,
        understanding=understanding,
    )
