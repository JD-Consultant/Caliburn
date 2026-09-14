"""Compose local JD and chat services before starting an ASGI event loop.

No provider is opened here. The caller provides the compiled consultant graph;
manual-only service retains the real Agent layout with execution disabled so
startup can inspect and close interrupted turns without model/tool replay.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass

from starlette.concurrency import run_in_threadpool

from .ai_runtime import AiRuntime
from .ai_checkpoints import AiRunCheckpoints
from .chat_api import ChatServices
from .chat_service import ChatService
from .chat_history import ChatHistoryCodec, ChatHistoryService
from .catalog_service import CatalogService
from .change_reads import ChangeReadService
from .configured_api import create_configured_api
from .configured_host import open_configured_host
from .conversation_sources import ConversationSourceCodec, ConversationSourceService
from .manual_service import ManualService
from .reads import ReadService
from .source_reads import SourceReadService
from .storage.history import HistoryReader


class ManagedAppError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def unavailable_consultant():
    from .inspection_model import build_inspection_consultant_node
    return build_inspection_consultant_node()


@dataclass(frozen=True, repr=False)
class ManagedApp:
    app: object
    opened: object
    ai_runtime: AiRuntime

    @property
    def port(self):
        return self.opened.settings.api_port

    def close(self):
        return self.opened.close(timeout=10)


def open_managed_app(file, *, consultant, enable_chat=False) -> ManagedApp:
    """Dedicated process/main thread; trusted caller explicitly enables new turns.

    The ordinary inspection-only entry keeps enable_chat=False. Original-run
    lookup, cancellation/recovery and saved messages remain available.
    """
    opened = open_configured_host(file, consultant=consultant)
    try:
        host, codec = opened.host, opened.codec
        sources = ConversationSourceService(AiRunCheckpoints(host.graph), ConversationSourceCodec(
            opened.settings.signing_key_bytes(), opened.settings.dataset_id))
        ai_runtime = AiRuntime(host.runtime, codec, conversation_sources=sources,
            memory_engine=host.memory_engine, execution_enabled=enable_chat)
        history = HistoryReader(host.engine)
        manual = ManualService(host.runtime, history, codec, source_resolver=sources.resolve)
        chat_history = ChatHistoryService(ai_runtime.checkpoints, ChatHistoryCodec(
            opened.settings.signing_key_bytes(), opened.settings.dataset_id))
        services = ChatServices(ReadService(host.runtime.storage, history, codec),
            ChangeReadService(history, codec), manual,
            CatalogService(host.runtime, opened.settings.dataset_id),
            ChatService(ai_runtime, manual, chat_history), sources=SourceReadService(sources))

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
            dataset_id=opened.settings.dataset_id, with_chat=True)
        return ManagedApp(app, opened, ai_runtime)
    except Exception:
        try:
            opened.close(timeout=10)
        except Exception:
            pass
        raise ManagedAppError("app_composition_failed") from None
