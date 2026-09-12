"""The advertised schema stays strict while omitting unrelated tool definitions."""

import json
from pathlib import Path

from jsonschema import Draft202012Validator
import pytest

from jd_relational.transport import MODELS, tool_definition


def nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from nodes(child)


@pytest.mark.parametrize("name", list(MODELS))
def test_each_published_tool_is_closed_and_contains_only_reachable_definitions(name):
    schema = tool_definition("openai", name)["parameters"]
    Draft202012Validator.check_schema(schema)
    assert schema == tool_definition("anthropic", name)["input_schema"]
    for node in nodes(schema):
        if node.get("type") == "object":
            assert node["additionalProperties"] is False
            assert set(node["required"]) == set(node["properties"])
        assert "default" not in node
    definitions = schema.get("$defs", {})
    referenced = {node["$ref"].removeprefix("#/$defs/") for node in nodes(schema) if "$ref" in node}
    assert referenced == set(definitions)
    assert not set(definitions) & {model.__name__ for model in MODELS.values()}


def test_single_field_tool_does_not_include_other_command_shapes():
    schema = tool_definition("openai", "jd_set_text")["parameters"]
    assert "$defs" not in schema
    assert set(schema["properties"]) == {"target_field_ref", "text", "basis_refs"}


def test_advertisement_does_not_repeat_the_whole_catalog_per_tool():
    path = Path(__file__).resolve().parents[1] / "contracts/jd-work.schema.json"
    catalog = json.loads(path.read_text(encoding="utf-8"))
    before = [{**catalog["$defs"][model.__name__], "$defs": catalog["$defs"]} for model in MODELS.values()]
    after = [tool_definition("openai", name)["parameters"] for name in MODELS]
    size = lambda value: len(json.dumps(value, ensure_ascii=False).encode("utf-8"))
    # This guards only a known catalog duplication, not an invented model token budget.
    assert size(after) < size(before)
