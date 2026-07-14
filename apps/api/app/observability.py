"""tracing 橫切層(ADR 0030 T6;原 authoring/tracing.py 搬家,traced_node 不搬)。

- 廠商中立 OTel:預設不掛 exporter(近 no-op);設 OTEL_EXPORTER_OTLP_ENDPOINT → OTLP;
  測試可注入 InMemorySpanExporter。後端(Langfuse/Grafana…)= 可插拔 OTLP,不綁 SDK。
- 屬性照 OTel GenAI semconv 現行版(仍 Development;實作驗證 2026-07-13):
  `gen_ai.system` 已棄用 → 用 **`gen_ai.provider.name`**;client 層 span 記
  model/input・output tokens/latency;verify 拒收與審閱事件各記一 span。
- 只依賴 otel api/sdk(輕依賴;ADR 0012 禁重依賴進 app 進程不受影響)。
"""
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor

_PROVIDER: TracerProvider | None = None

# semconv 現行慣例(gen_ai.system deprecated;驗證報告 H4)
GEN_AI_PROVIDER_ATTR = "gen_ai.provider.name"


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


def record_verify_rejects(errors) -> None:
    """verify 拒收事件入 trace(每批一 span;errors=VerifyError 列表)。"""
    if not errors:
        return
    with get_tracer().start_as_current_span("interview.verify.reject") as span:
        span.set_attribute("caliburn.verify.rejected_count", len(errors))
        span.set_attribute("caliburn.verify.checks",
                           [e.check for e in errors][:20])


def record_review_events(events: list[dict]) -> None:
    """審閱事件(✓/✗/批量)入 trace(每批一 span)。"""
    if not events:
        return
    with get_tracer().start_as_current_span("interview.review") as span:
        span.set_attribute("caliburn.review.count", len(events))
        span.set_attribute("caliburn.review.decisions",
                           [str(e.get("decision")) for e in events][:20])
