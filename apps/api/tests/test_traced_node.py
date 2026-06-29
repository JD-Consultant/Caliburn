import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from langgraph.errors import GraphInterrupt

from app.authoring.tracing import setup_tracing, traced_node


def _exporter():
    exp = InMemorySpanExporter()
    setup_tracing(exp, force=True)
    return exp


@pytest.mark.asyncio
async def test_traced_node_records_normal_span():
    exp = _exporter()

    @traced_node("demo")
    async def node(state, config):
        return {"ok": True}

    out = await node({"current_step": "deep"}, {})
    assert out == {"ok": True}
    s = exp.get_finished_spans()[0]
    assert s.name == "node.demo"
    assert s.attributes["caliburn.node"] == "demo"
    assert s.attributes["caliburn.current_step"] == "deep"
    assert s.status.status_code != StatusCode.ERROR


@pytest.mark.asyncio
async def test_traced_node_interrupt_not_error():
    exp = _exporter()

    @traced_node("ask")
    async def node(state, config):
        raise GraphInterrupt("pause")   # interrupt() 內部即丟此類

    with pytest.raises(GraphInterrupt):
        await node({}, {})
    s = exp.get_finished_spans()[0]
    assert s.status.status_code != StatusCode.ERROR   # interrupt 非錯誤


@pytest.mark.asyncio
async def test_traced_node_real_error_marks_error():
    exp = _exporter()

    @traced_node("boom")
    async def node(state, config):
        raise ValueError("real bug")

    with pytest.raises(ValueError):
        await node({}, {})
    s = exp.get_finished_spans()[0]
    assert s.status.status_code == StatusCode.ERROR
