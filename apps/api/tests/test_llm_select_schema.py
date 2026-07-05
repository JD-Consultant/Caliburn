"""T7:select_schema 接線(port/stub/payload 建構;真模型驗收在 scripts/)。"""
import pytest

from app.adapters.llm_openrouter import model_for_role, schema_response_format
from app.adapters.stubs import StubLlm
from app.core.ports import LlmPort
from app.interview.commands import TurnOutput, turn_output_schema


def test_schema_response_format_shape():
    schema = turn_output_schema(["T1.1"])
    rf = schema_response_format("turn_output", schema)
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["name"] == "turn_output"
    assert rf["json_schema"]["schema"] is schema


def test_model_for_role_select_dedicated():
    assert model_for_role("select") != ""            # 有專用受限解碼模型
    assert model_for_role("select") != model_for_role("cheap")


@pytest.mark.asyncio
async def test_stub_llm_satisfies_port_and_records_calls():
    stub = StubLlm(select_result={"commands": [{"type": "reply", "text": "hi"}],
                                  "saturation": False})
    assert isinstance(stub, LlmPort)                 # runtime_checkable protocol
    out = await stub.select_schema("問題", turn_output_schema(None))
    parsed = TurnOutput.model_validate(out)
    assert parsed.commands[0].type == "reply"
    assert stub.calls[0]["kind"] == "select" and stub.calls[0]["schema_name"] == "output"


@pytest.mark.asyncio
async def test_stub_llm_callable_select():
    stub = StubLlm(select_result=lambda prompt, schema: {
        "commands": [{"type": "advance", "next_focus": "review"}], "saturation": True})
    out = await stub.select_schema("x", {})
    assert out["saturation"] is True
