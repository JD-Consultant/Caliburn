"""Compose the configured manual App before starting an ASGI event loop.

No model is opened here. The caller provides the compiled consultant graph;
manual-only service uses an explicitly unavailable consultant node until the
separately verified interview integration is supplied.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from langgraph.graph import END, START, MessagesState, StateGraph
from starlette.concurrency import run_in_threadpool

from .catalog_api import CatalogServices
from .catalog_service import CatalogService
from .change_reads import ChangeReadService
from .configured_api import create_configured_api
from .configured_host import open_configured_host
from .manual_service import ManualService
from .reads import ReadService
from .storage.history import HistoryReader


class ManagedAppError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def unavailable_consultant():
    def unavailable(state):
        raise ManagedAppError("consultant_unavailable")
    graph = StateGraph(MessagesState)
    graph.add_node("consultant", unavailable)
    graph.add_edge(START, "consultant")
    graph.add_edge("consultant", END)
    return graph.compile()


@dataclass(frozen=True, repr=False)
class ManagedApp:
    app: object
    opened: object

    @property
    def port(self):
        return self.opened.settings.api_port

    def close(self):
        return self.opened.close(timeout=10)


def open_managed_app(file, *, consultant) -> ManagedApp:
    """Dedicated process/main thread only; fixed config before OS/DB/ASGI."""
    opened = open_configured_host(file, consultant=consultant)
    try:
        host, codec = opened.host, opened.codec
        history = HistoryReader(host.engine)
        services = CatalogServices(ReadService(host.runtime.storage, history, codec),
            ChangeReadService(history, codec), ManualService(host.runtime, history, codec),
            CatalogService(host.runtime, opened.settings.dataset_id))

        @asynccontextmanager
        async def resources():
            try:
                try:
                    await run_in_threadpool(host.runtime.finish_startup, timeout=20)
                except Exception:
                    raise ManagedAppError("startup_recovery_failed") from None
                yield services
            finally:
                try:
                    closed = await run_in_threadpool(opened.close, timeout=10)
                except Exception:
                    closed = False
                if not closed:
                    raise ManagedAppError("shutdown_unconfirmed") from None

        app = create_configured_api(resources, allowed_origins=opened.settings.allowed_origins,
            dataset_id=opened.settings.dataset_id)
        return ManagedApp(app, opened)
    except Exception:
        try:
            opened.close(timeout=10)
        except Exception:
            pass
        raise ManagedAppError("app_composition_failed") from None
