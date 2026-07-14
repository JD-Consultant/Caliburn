from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.observability import setup_tracing, get_tracer


def test_setup_tracing_exports_spans_to_injected_exporter():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    with get_tracer().start_as_current_span("unit.smoke") as span:
        span.set_attribute("k", "v")
    spans = exp.get_finished_spans()
    assert [s.name for s in spans] == ["unit.smoke"]
    assert spans[0].attributes["k"] == "v"


def test_record_verify_rejects_emits_span_only_when_errors():
    from app.interview.verify import VerifyError
    from app.observability import record_verify_rejects

    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    record_verify_rejects([])                              # 空=不出 span
    assert exp.get_finished_spans() == ()
    record_verify_rejects([VerifyError(op_index=0, check="quote", message="m", hint=None)])
    (span,) = exp.get_finished_spans()
    assert span.name == "interview.verify.reject"
    assert span.attributes["caliburn.verify.rejected_count"] == 1
    assert list(span.attributes["caliburn.verify.checks"]) == ["quote"]


def test_record_review_events_emits_span():
    from app.observability import record_review_events

    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    record_review_events([{"doc_path": "p", "decision": "accepted"},
                          {"doc_path": "q", "decision": "rejected"}])
    (span,) = exp.get_finished_spans()
    assert span.name == "interview.review"
    assert span.attributes["caliburn.review.count"] == 2
    assert list(span.attributes["caliburn.review.decisions"]) == ["accepted", "rejected"]
