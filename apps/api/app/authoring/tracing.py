"""廠商中立 OTel 儀器（D19）。預設不掛 exporter（近 no-op）；設 OTEL_EXPORTER_OTLP_ENDPOINT
→ OTLP；測試可注入 InMemorySpanExporter。"""
import functools
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.trace import Status, StatusCode
from langgraph.errors import GraphBubbleUp

_PROVIDER: TracerProvider | None = None


def setup_tracing(exporter=None, *, force: bool = False) -> TracerProvider:
    global _PROVIDER
    if _PROVIDER is not None and not force:
        return _PROVIDER
    provider = TracerProvider(resource=Resource.create({"service.name": "caliburn"}))
    if exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(exporter))
    elif os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    _PROVIDER = provider
    return provider


def get_tracer():
    if _PROVIDER is not None:
        return _PROVIDER.get_tracer("caliburn.authoring")
    from opentelemetry import trace
    return trace.get_tracer("caliburn.authoring")


def traced_node(name: str):
    """包 async graph node 成一個 span；interrupt（GraphBubbleUp）視為正常控制流不記 error。"""
    def deco(fn):
        @functools.wraps(fn)
        async def wrapper(state, config):
            with get_tracer().start_as_current_span(f"node.{name}") as span:
                span.set_attribute("caliburn.node", name)
                step = state.get("current_step") if isinstance(state, dict) else None
                if step:
                    span.set_attribute("caliburn.current_step", step)
                exc_to_raise = None
                try:
                    return await fn(state, config)
                except GraphBubbleUp as exc:
                    # interrupt / 正常暫停，非錯誤；捕捉但不記 error
                    exc_to_raise = exc
                except Exception as exc:       # noqa: BLE001
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    exc_to_raise = exc
            # 在 span context 外才 raise，避免 span 自動記錄為 error
            if exc_to_raise is not None:
                raise exc_to_raise
        return wrapper
    return deco
