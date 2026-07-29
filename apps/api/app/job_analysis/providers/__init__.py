"""Provider adapters:目前只有 OpenRouter,而且刻意不做 registry(T5)。"""

from .openrouter import (
    CHAT_COMPLETIONS_URL,
    ChatTransport,
    OpenRouterAdapter,
    OpenRouterConfig,
    ProviderFailure,
    ProviderFailureKind,
    ProviderOutcome,
    ProviderRefusal,
    ProviderText,
    TransportResponse,
    httpx_chat_transport,
)

__all__ = [
    "CHAT_COMPLETIONS_URL",
    "ChatTransport",
    "OpenRouterAdapter",
    "OpenRouterConfig",
    "ProviderFailure",
    "ProviderFailureKind",
    "ProviderOutcome",
    "ProviderRefusal",
    "ProviderText",
    "TransportResponse",
    "httpx_chat_transport",
]
