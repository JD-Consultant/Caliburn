"""Qdrant client factory.

Centralizes auth, timeouts, and url normalization so other modules don't need
to know about the env layout.

`QdrantClient(url=...)` defaults to port 6333 when the URL has no explicit
port — but hosted/proxied deployments typically only expose 443 (HTTPS) or
80 (HTTP). We parse the URL and pass host/port/https/prefix explicitly so any
URL form works without forcing the operator to write a port in `.env`.
"""

from __future__ import annotations

from urllib.parse import urlparse

from qdrant_client import QdrantClient


def make_client(
    *,
    url: str,
    api_key: str | None,
    timeout: float = 60.0,
) -> QdrantClient:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "http").lower()
    https = scheme == "https"
    host = parsed.hostname or url
    port = parsed.port or (443 if https else 6333)
    prefix = parsed.path.rstrip("/") or None

    return QdrantClient(
        host=host,
        port=port,
        https=https,
        prefix=prefix,
        api_key=api_key,
        timeout=timeout,
        prefer_grpc=False,
    )
