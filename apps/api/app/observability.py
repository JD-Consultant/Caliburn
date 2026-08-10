"""Small OpenTelemetry seam for the current local API."""

import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

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
        return _PROVIDER.get_tracer("caliburn")
    return trace.get_tracer("caliburn")
