"""Generated read DTO and actual provider SDK serialization, with no network."""

from copy import deepcopy
import json
from pathlib import Path
from uuid import UUID
import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
import httpx2
from openai import OpenAI
from anthropic import Anthropic

from test_provider_wire import offline_environment, mock_transport, MODEL, schema_nodes
from test_reads import CurrentReader, all_pages
from test_snapshots import uid, complete_domain
from jd_relational.snapshots import empty_domain
from jd_relational.references import ReferenceCodec
from jd_relational.reads import ReadService, ReadError
from jd_relational.generated.reads import ReadInput, ReadPage, SectionRecord, ItemRecord
from jd_relational.read_transport import (
    parse_read_arguments,
    read_tool_definition,
    read_tool_output,
    read_failure,
)
from jd_relational.transport import TransportError


def result_page():
    codec = ReferenceCodec(b"public-synthetic-read-test-key-0000", "dataset")
    return ReadService(CurrentReader(empty_domain("document-a", uid(901))), None, codec).read(
        "document-a", {"view": "current", "target_ref": None, "cursor": None}
    )


def test_read_v2_requires_stable_section_and_item_keys_and_rejects_v1():
    codec = ReferenceCodec(b"public-synthetic-read-test-key-0000", "dataset")
    service = ReadService(CurrentReader(complete_domain()), None, codec)
    records, pages = all_pages(service, "document-a")
    assert all(page["format_version"] == 2 for page in pages)
    schema = json.loads((Path(__file__).resolve().parents[1] / "contracts/jd-read.schema.json").read_text(encoding="utf-8"))
    source = {"$defs": schema["$defs"], "$ref": "#/$defs/ReadPage"}
    for page in pages:
        assert Draft202012Validator(source).is_valid(page)
        assert not Draft202012Validator(source).is_valid({**page, "format_version": 1})
        with pytest.raises(ValidationError):
            ReadPage.model_validate({**page, "format_version": 1}, strict=True)
    for record in records:
        if record["type"] == "section":
            assert record["section_key"] in {"profile", "purpose", "duties_tasks", "knowledge", "skills", "conditions"}
        elif record["type"] == "item":
            assert str(UUID(record["item_id"])) == record["item_id"]


@pytest.mark.parametrize("kind,key,bad", [
    ("section", "section_key", "missing"),
    ("section", "section_key", "custom"),
    ("section", "section_key", 1),
    ("item", "item_id", "missing"),
    ("item", "item_id", "not-a-uuid"),
    ("item", "item_id", "ABCDEFAB-0000-0000-0000-000000000001"),
    ("item", "item_id", 1),
])
def test_display_identity_source_and_generated_schema_reject_invalid_metadata(kind, key, bad):
    codec = ReferenceCodec(b"public-synthetic-read-test-key-0000", "dataset")
    records, _ = all_pages(ReadService(CurrentReader(complete_domain()), None, codec), "document-a")
    record = next(r for r in records if r["type"] == kind)
    dto = SectionRecord if kind == "section" else ItemRecord
    schema = json.loads((Path(__file__).resolve().parents[1] / "contracts/jd-read.schema.json").read_text(encoding="utf-8"))
    original = {"$defs": schema["$defs"], "$ref": f"#/$defs/{dto.__name__}"}
    assert Draft202012Validator(original).is_valid(record)
    if bad == "missing":
        record.pop(key)
    else:
        record[key] = bad
    assert not Draft202012Validator(original).is_valid(record)
    assert not Draft202012Validator(dto.model_json_schema()).is_valid(record)
    with pytest.raises(ValidationError):
        dto.model_validate(record, strict=True)


@pytest.mark.parametrize(
    "arguments",
    [
        {"view": "current", "target_ref": None, "cursor": None},
        {"view": "history", "target_ref": None, "cursor": None},
        {"view": "item", "target_ref": "issued", "cursor": "next"},
        {"view": "section", "target_ref": "issued", "cursor": None},
    ],
)
def test_input_schema_parity_and_no_hidden_context_parameters(arguments):
    schema = json.loads(
        (Path(__file__).resolve().parents[1] / "contracts/jd-read.schema.json").read_text()
    )
    original = {**schema, "$ref": "#/$defs/ReadInput"}
    for key in ("type", "properties", "required", "additionalProperties"):
        original.pop(key, None)
    assert Draft202012Validator(original).is_valid(arguments)
    generated = ReadInput.model_json_schema(mode="validation")
    assert Draft202012Validator(generated).is_valid(arguments)
    assert parse_read_arguments(json.dumps(arguments)) == arguments
    for node in schema_nodes(generated):
        if node.get("type") == "object":
            assert (
                set(node["required"]) == set(node["properties"])
                and node["additionalProperties"] is False
            )
    assert set(generated["properties"]) == {"view", "target_ref", "cursor"}


@pytest.mark.parametrize(
    "bad",
    [
        '{"view":"current","view":"history","target_ref":null,"cursor":null}',
        '{"view":"current","target_ref":NaN,"cursor":null}',
        {"view": "current", "target_ref": None},
        {"view": "current", "target_ref": None, "cursor": None, "document_id": "from-model"},
        {"view": "current", "target_ref": None, "cursor": "x" * 4097},
    ],
)
def test_invalid_read_arguments_never_escape_as_raw_exception(bad):
    with pytest.raises(ReadError, match="invalid_input") as error:
        parse_read_arguments(bad)
    assert error.value.__suppress_context__


@pytest.mark.parametrize(
    "mutate",
    [
        lambda p: p.update(format_version=True),
        lambda p: p.update(has_more=True, next_cursor=None),
        lambda p: p.update(total_records=0),
        lambda p: p.update(oversized_unit=True),
        lambda p: p["records"][0].update(private_content="unexpected"),
    ],
)
def test_malformed_read_output_is_not_sent_to_model(mutate):
    page = result_page()
    mutate(page)
    with pytest.raises(TransportError, match="invalid_result"):
        read_tool_output("openai", "call", page)


def test_fixed_error_and_generated_version_do_not_accept_bool_or_raw_error_text():
    page = result_page()
    with pytest.raises(ValidationError):
        ReadPage.model_validate({**page, "format_version": True}, strict=True)
    failure = read_failure("stale_view")
    with pytest.raises(TransportError):
        read_tool_output("anthropic", "call", {**failure, "message": "private driver values"})


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("budget", [8192, 32768])
def test_final_model_content_keeps_the_measured_page_budget(provider, budget):
    codec = ReferenceCodec(b"public-synthetic-read-test-key-0000", "dataset")
    service = ReadService(CurrentReader(complete_domain()), None, codec, page_bytes=budget)
    _, pages = all_pages(service, "document-a")
    for page in pages:
        assert not page["oversized_unit"]
        block = read_tool_output(provider, "call", page)
        content = block["output" if provider == "openai" else "content"]
        assert len(content.encode("utf-8")) <= budget


@pytest.mark.parametrize("provider", ["openai", "anthropic"])
@pytest.mark.parametrize("failed", [False, True])
def test_read_sdk_tool_request_and_real_read_result_roundtrip(provider, failed):
    args = {"view": "current", "target_ref": None, "cursor": None}
    result = read_failure("stale_view") if failed else result_page()
    definition = read_tool_definition(provider)
    transport, captured = mock_transport(provider, "jd_read", args)
    with httpx2.Client(transport=transport, trust_env=False) as http_client:
        if provider == "openai":
            with OpenAI(
                api_key="fake-offline-key",
                base_url="https://offline.invalid",
                max_retries=0,
                http_client=http_client,
            ) as client:
                response = client.responses.create(
                    model=MODEL,
                    input=[{"role": "user", "content": "查看目前工作"}],
                    tools=[definition],
                    store=False,
                )
                call = response.output[0]
                assert parse_read_arguments(call.arguments) == args
                block = read_tool_output(provider, call.call_id, result)
                client.responses.create(
                    model=MODEL,
                    tools=[definition],
                    store=False,
                    input=[call.model_dump(mode="json", exclude_none=True), block],
                )
            echoed = captured[1]["input"][-1]
            assert echoed["call_id"] == call.call_id and json.loads(echoed["output"]) == result
        else:
            with Anthropic(
                api_key="fake-offline-key",
                base_url="https://offline.invalid",
                max_retries=0,
                http_client=http_client,
            ) as client:
                response = client.messages.create(
                    model=MODEL,
                    max_tokens=256,
                    tools=[definition],
                    messages=[{"role": "user", "content": "查看目前工作"}],
                )
                call = response.content[0]
                assert parse_read_arguments(call.input) == args
                block = read_tool_output(provider, call.id, result)
                client.messages.create(
                    model=MODEL,
                    max_tokens=256,
                    tools=[definition],
                    messages=[
                        {
                            "role": "assistant",
                            "content": [call.model_dump(mode="json", exclude_none=True)],
                        },
                        {"role": "user", "content": [block]},
                    ],
                )
            echoed = captured[1]["messages"][-1]["content"][0]
            assert (
                echoed["tool_use_id"] == call.id
                and echoed["is_error"] == failed
                and json.loads(echoed["content"]) == result
            )
    assert len(captured) == 2
    assert all(body["tools"] == [definition] for body in captured)
