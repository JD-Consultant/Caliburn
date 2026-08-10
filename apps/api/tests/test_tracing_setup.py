from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability import get_tracer, setup_tracing


def test_setup_tracing_exports_spans_to_injected_exporter():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    with get_tracer().start_as_current_span("unit.smoke") as span:
        span.set_attribute("k", "v")
    spans = exp.get_finished_spans()
    assert [s.name for s in spans] == ["unit.smoke"]
    assert spans[0].attributes["k"] == "v"
