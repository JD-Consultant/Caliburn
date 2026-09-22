"""SSOT/DTO parity and genuine SDK serialization with offline HTTP responses."""

from copy import deepcopy
import json
from pathlib import Path

import httpx2
from anthropic import Anthropic
from jsonschema import Draft202012Validator
from openai import OpenAI
from pydantic import ValidationError
import pytest

from jd_relational.change_reads import ChangeReadService
from jd_relational.change_transport import change_tool_definition, parse_change_arguments, change_tool_output
from jd_relational.generated.reads import ChangeReadInput, ChangeReadPage
from jd_relational.read_transport import read_failure
from jd_relational.reads import ReadError, read_json
from jd_relational.references import ReferenceCodec
from jd_relational.transport import TransportError
from test_change_reads import DOC, History, material, change_ref, all_pages
from test_provider_wire import offline_environment, mock_transport, MODEL, schema_nodes


def pages(budget=8192):
    codec = ReferenceCodec(b"change-transport-synthetic-key-0000", "dataset")
    return all_pages(ChangeReadService(History(material()), codec, page_bytes=budget), change_ref(codec))[1]


def source_schema(name):
    source = json.loads((Path(__file__).resolve().parents[1] / "contracts/jd-read.schema.json").read_text(encoding="utf-8"))
    return {"$schema": source["$schema"], "$defs": source["$defs"], "$ref": "#/$defs/" + name}


@pytest.mark.parametrize("args,valid", [
    ({"change_ref": "issued", "cursor": None}, True),
    ({"change_ref": "issued", "cursor": "next"}, True),
    ({"change_ref": "issued"}, False),
    ({"change_ref": "issued", "cursor": None, "document_id": "hidden"}, False),
    ({"change_ref": None, "cursor": None}, False),
    ({"change_ref": 1, "cursor": None}, False),
    ({"change_ref": "x" * 4097, "cursor": None}, False),
])
def test_two_parameter_input_is_closed_and_source_generated_dto_agree(args, valid):
    generated = ChangeReadInput.model_json_schema(mode="validation")
    assert Draft202012Validator(source_schema("ChangeReadInput")).is_valid(args) == valid
    assert Draft202012Validator(generated).is_valid(args) == valid
    if valid:
        assert parse_change_arguments(args) == args
        assert parse_change_arguments(json.dumps(args)) == args
    else:
        with pytest.raises(ReadError, match="invalid_input"):
            parse_change_arguments(args)
    assert set(generated["properties"]) == {"change_ref", "cursor"}
    for node in schema_nodes(generated):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])


@pytest.mark.parametrize("raw", [
    '{"change_ref":"a","change_ref":"b","cursor":null}',
    '{"change_ref":NaN,"cursor":null}',
    '{"change_ref":"a","cursor":"\\ud800"}',
    "[" * 2000,
    " " * 16385,
])
def test_invalid_json_is_a_fixed_input_failure(raw):
    with pytest.raises(ReadError, match="invalid_input") as error:
        parse_change_arguments(raw)
    assert error.value.__suppress_context__


def test_page_source_schema_dto_and_transport_preserve_exact_full_records():
    for page in pages():
        assert Draft202012Validator(source_schema("ChangeReadPage")).is_valid(page)
        assert Draft202012Validator(ChangeReadPage.model_json_schema()).is_valid(page)
        assert ChangeReadPage.model_validate(page, strict=True).model_dump(mode="json") == page
    page = pages()[0]
    for key, value in (("format_version", True), ("start_index", False)):
        bad = {**page, key: value}
        assert not Draft202012Validator(source_schema("ChangeReadPage")).is_valid(bad)
        with pytest.raises(ValidationError):
            ChangeReadPage.model_validate(bad, strict=True)


@pytest.mark.parametrize("mutate", [
    lambda p: p.update(format_version=True),
    lambda p: p.update(access="current"),
    lambda p: p.update(has_more=True, next_cursor=None),
    lambda p: p.update(total_records=0),
    lambda p: p.update(total_changes=0),
    lambda p: p.update(oversized_unit=True),
    lambda p: p["records"][0].update(raw_row={"task_id": "internal"}),
    lambda p: p["records"][0].update(change_index=p["total_changes"]),
    lambda p: p["records"][0].update(before_exists=False),
    lambda p: p.update(records=[]),
])
def test_malformed_or_internally_inconsistent_result_is_not_sent(mutate):
    page = pages()[0]
    mutate(page)
    with pytest.raises(TransportError, match="invalid_result"):
        change_tool_output("openai", "call", page)


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
def test_unchanged_shared_error_whitelist_and_actual_inner_bytes(provider):
    failure = read_failure("invalid_input")
    assert failure["message"] == "讀取參數不符；請依該工具說明提供必要參數。"
    for error in (failure, read_failure("read_failed"), read_failure("invalid_ref")):
        block = change_tool_output(provider, "call", error)
        assert json.loads(block["output" if provider == "openai" else "content"]) == error
    with pytest.raises(TransportError, match="invalid_result"):
        change_tool_output(provider, "call", {**failure, "message": "private driver detail"})
    for page in pages(4096):
        block = change_tool_output(provider, "call", page)
        encoded = block["output" if provider == "openai" else "content"]
        assert encoded == read_json(page)
        assert len(encoded.encode("utf-8")) <= 4096 or page["oversized_unit"] and len(page["records"]) == 1


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("failed", [False, True])
def test_sdk_tool_and_result_serialization_with_synthetic_response(provider, failed):
    args = {"change_ref": "issued-change", "cursor": None}
    result = read_failure("read_failed") if failed else pages()[0]
    definition = change_tool_definition(provider)
    transport, captured = mock_transport(provider, "jd_change_read", args)
    with httpx2.Client(transport=transport, trust_env=False) as http_client:
        if provider == "openai":
            with OpenAI(api_key="fake-offline-key", base_url="https://offline.invalid", max_retries=0, http_client=http_client) as client:
                response = client.responses.create(model=MODEL, input=[{"role": "user", "content": "查看這次修改"}], tools=[definition], store=False)
                call = response.output[0]
                assert parse_change_arguments(call.arguments) == args
                block = change_tool_output(provider, call.call_id, result)
                client.responses.create(model=MODEL, tools=[definition], store=False,
                    input=[call.model_dump(mode="json", exclude_none=True), block])
            echoed = captured[1]["input"][-1]
            assert echoed["call_id"] == call.call_id and json.loads(echoed["output"]) == result
        else:
            with Anthropic(api_key="fake-offline-key", base_url="https://offline.invalid", max_retries=0, http_client=http_client) as client:
                response = client.messages.create(model=MODEL, max_tokens=256, tools=[definition], messages=[{"role": "user", "content": "查看這次修改"}])
                call = response.content[0]
                assert parse_change_arguments(call.input) == args
                block = change_tool_output(provider, call.id, result)
                client.messages.create(model=MODEL, max_tokens=256, tools=[definition], messages=[
                    {"role": "assistant", "content": [call.model_dump(mode="json", exclude_none=True)]},
                    {"role": "user", "content": [block]}])
            echoed = captured[1]["messages"][-1]["content"][0]
            assert echoed["tool_use_id"] == call.id and echoed["is_error"] == failed and json.loads(echoed["content"]) == result
    assert len(captured) == 2 and all(body["tools"] == [definition] for body in captured)
