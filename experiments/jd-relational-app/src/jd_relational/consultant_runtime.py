"""Process-owned resources for the completed consultant graph."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import httpx
from langgraph.graph.state import CompiledStateGraph

from .consultant_app import build_consultant
from .consultant_model import OPENROUTER_HEADERS, create_consultant_model


@dataclass(repr=False)
class ConsultantRuntime:
    graph: CompiledStateGraph
    http_client: httpx.Client = field(repr=False)
    async_http_client: httpx.AsyncClient = field(repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _close_confirmed: bool = field(default=False, init=False, repr=False)

    def close(self) -> bool:
        """Close only after the App has drained foreground model/tool work."""
        if self._closed:
            return self._close_confirmed
        self._closed = True
        confirmed = True
        try:
            self.http_client.close()
        except Exception:
            confirmed = False
        try:
            asyncio.run(self.async_http_client.aclose())
        except Exception:
            confirmed = False
        self._close_confirmed = confirmed
        return confirmed


def open_consultant_runtime(*, api_key: str) -> ConsultantRuntime:
    """Create the existing consultant once for one local App process."""
    sync_client = httpx.Client(headers=OPENROUTER_HEADERS, follow_redirects=True)
    async_client = httpx.AsyncClient(headers=OPENROUTER_HEADERS, follow_redirects=True)
    try:
        model = create_consultant_model(
            api_key=api_key,
            http_client=sync_client,
            async_http_client=async_client,
        )
        return ConsultantRuntime(build_consultant(model), sync_client, async_client)
    except Exception:
        try:
            sync_client.close()
        except Exception:
            pass
        try:
            asyncio.run(async_client.aclose())
        except Exception:
            pass
        raise
