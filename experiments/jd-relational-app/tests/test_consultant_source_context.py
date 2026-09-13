"""Actual native request projection; synthetic messages, no provider/DB."""
from dataclasses import replace
import json

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
import pytest

from jd_relational.consultant_context import ConsultantContextError
from test_consultant_context import FixedModel, graph, setup


def test_source_metadata_reaches_request_without_copying_original_into_system():
    context, reply = setup()
    original = HumanMessage(id=context.run_id, content="每月做報表\r\n只處理我的客戶。")
    captured = []
    metadata = {"type": "conversation_source_notice", "source_ref": "owner-issued-synthetic-ref",
                "messages": [{"message_id": original.id, "role": "user"}],
                "instruction": "來源定位由App提供；仍須核對內容。"}
    def source_notice(messages):
        captured.append([m.model_dump() for m in messages])
        return metadata
    context = replace(context, source_notice=source_notice)
    model = FixedModel(replies=[reply]); root = graph(model, InMemorySaver())
    result = root.invoke({"messages": [original]}, {"configurable": {"thread_id": context.document_id}},
                         context=context, durability="sync")
    assert captured == [[original.model_dump()]]
    blocks = model.requests[0][0].content
    assert json.loads(blocks[-1]["text"]) == metadata
    assert original.content not in json.dumps(blocks, ensure_ascii=False)
    assert model.requests[0][1].model_dump() == original.model_dump()
    assert [m.type for m in result["messages"]] == ["human", "ai"]
    assert result["messages"][0].model_dump() == original.model_dump()


def test_unavailable_source_stops_before_model_without_leaking_exception():
    context, reply = setup()
    def unavailable(messages):
        raise RuntimeError("private-source-body-or-connection")
    context = replace(context, source_notice=unavailable)
    model = FixedModel(replies=[reply]); root = graph(model, InMemorySaver())
    with pytest.raises(ConsultantContextError, match="^source_not_available") as error:
        root.invoke({"messages": [HumanMessage(id=context.run_id, content="合成原話")]},
            {"configurable": {"thread_id": context.document_id}}, context=context, durability="sync")
    assert error.value.__suppress_context__
    assert str(error.value) == error.value.code == "source_not_available"
    assert not model.requests


def test_non_callable_source_projection_rejected_at_context_construction():
    context, _ = setup()
    with pytest.raises(ConsultantContextError, match="^invalid_consultant_context$"):
        replace(context, source_notice={"source_ref": "not-a-source-owner"})
