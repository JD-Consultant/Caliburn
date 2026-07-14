"""select_schema 接線(port/stub/payload 建構;真模型驗收在 scripts/)。
T12 後 schema 來源=v3 書記(scribe_schema);v1 turn_output 已退場。"""
import pytest

from app.adapters.llm_openrouter import model_for_role, schema_response_format
from app.adapters.stubs import StubLlm
from app.core.ports import LlmPort
from app.interview.scribe_schema import ScribeOutput, scribe_schema


def _schema():
    return scribe_schema(slot_paths=["ocs_content.ocu_units.u1.tasks.t1.details.frequency"],
                         pools={}, task_keys=["ocs_content.ocu_units.u1.tasks.t1"],
                         unit_keys=["ocs_content.ocu_units.u1"])


def test_schema_response_format_shape():
    schema = _schema()
    rf = schema_response_format("scribe_output", schema)
    assert rf["type"] == "json_schema"
    assert rf["json_schema"]["strict"] is True
    assert rf["json_schema"]["name"] == "scribe_output"
    assert rf["json_schema"]["schema"] is schema


def test_model_for_role_select_dedicated():
    assert model_for_role("select") != ""            # 有專用受限解碼模型
    assert model_for_role("select") != model_for_role("cheap")


@pytest.mark.asyncio
async def test_stub_llm_satisfies_port_and_records_calls():
    stub = StubLlm(select_result={"records": [
        {"type": "set_slot", "path": "ocs_content.ocu_units.u1.tasks.t1.details.frequency",
         "value": "每雙週", "quote": "每兩週跑一次"}]})
    assert isinstance(stub, LlmPort)                 # runtime_checkable protocol
    out = await stub.select_schema("問題", _schema())
    parsed = ScribeOutput.model_validate(out)
    assert parsed.records[0].type == "set_slot"
    assert stub.calls[0]["kind"] == "select" and stub.calls[0]["schema_name"] == "output"


@pytest.mark.asyncio
async def test_stub_llm_callable_select():
    stub = StubLlm(select_result=lambda prompt, schema: {"records": [{"type": "none"}]})
    out = await stub.select_schema("x", {})
    assert out["records"][0]["type"] == "none"
