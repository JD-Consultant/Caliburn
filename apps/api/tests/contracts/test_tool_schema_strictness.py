"""Every tool a role advertises keeps the stable strict-function rules (offline JDT-01 layer).

This is not provider acceptance; only a bounded request to the model API proves that. It
keeps to rules that do not depend on which keywords a provider version supports: a root
object, every object closed with all properties required, only local non-recursive $ref
nodes without siblings, no oneOf/allOf/not, and ceilings well inside the documented limits.
"""

import re
from typing import Any

import pytest

from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.workflows.memory_analysis.tools import memory_analysis_tool_definitions

# Conservative ceilings under OpenAI's documented structured-output limits (5,000 object
# properties, 10 nesting levels). Verified against the provider in the bounded T16 gate.
MAX_OBJECT_PROPERTIES = 1_000
MAX_OBJECT_DEPTH = 8
UNSUPPORTED_COMBINATORS = ("oneOf", "allOf", "not")
LOCAL_DEFINITION = "#/$defs/"
TYPED_KEYWORDS = ("type", "enum", "const", "anyOf", "$ref")
ROLE_DEFINITIONS = {
    "consultant": consultant_tool_definitions,
    "work_situation": lambda: memory_analysis_tool_definitions(MemoryLayer.WORK_SITUATION),
    "work_understanding": lambda: memory_analysis_tool_definitions(MemoryLayer.WORK_UNDERSTANDING),
}


class SchemaWalk:
    def __init__(self, definitions: dict[str, Any]) -> None:
        self.definitions = definitions
        self.properties = 0
        self.deepest = 0
        self.expanding: list[str] = []

    def visit(self, node: Any, path: str, depth: int = 0) -> None:
        assert isinstance(node, dict), f"{path}: a schema node must be an object"
        for keyword in UNSUPPORTED_COMBINATORS:
            assert keyword not in node, f"{path}: {keyword} is outside the stable strict subset"
        assert any(keyword in node for keyword in TYPED_KEYWORDS), f"{path}: untyped node"
        if "$ref" in node:
            self.visit_reference(node, path, depth)
            return
        if node.get("type") == "object" or "properties" in node:
            depth = self.visit_object(node, path, depth)
        if "items" in node:
            self.visit(node["items"], f"{path}[]", depth)
        for index, branch in enumerate(node.get("anyOf", [])):
            self.visit(branch, f"{path}|{index}", depth)

    def visit_reference(self, node: dict[str, Any], path: str, depth: int) -> None:
        assert set(node) == {"$ref"}, f"{path}: $ref must not carry sibling keywords"
        reference = node["$ref"]
        assert reference.startswith(LOCAL_DEFINITION), f"{path}: only local $defs references"
        name = reference.removeprefix(LOCAL_DEFINITION)
        assert name in self.definitions, f"{path}: dangling reference {reference}"
        assert name not in self.expanding, f"{path}: recursive schema {name}"
        self.expanding.append(name)
        self.visit(self.definitions[name], f"{path}->{name}", depth)
        self.expanding.pop()

    def visit_object(self, node: dict[str, Any], path: str, depth: int) -> int:
        properties = node.get("properties", {})
        assert node.get("additionalProperties") is False, f"{path}: object must be closed"
        assert set(node.get("required", [])) == set(properties), f"{path}: every property required"
        depth += 1
        self.deepest = max(self.deepest, depth)
        self.properties += len(properties)
        for name, child in properties.items():
            self.visit(child, f"{path}.{name}", depth)
        return depth


def all_tools() -> list[tuple[str, dict[str, Any]]]:
    return [
        (f"{role}/{definition['name']}", definition)
        for role, build in ROLE_DEFINITIONS.items()
        for definition in build()
    ]


@pytest.mark.parametrize(("label", "definition"), all_tools(), ids=lambda value: str(value)[:60])
def test_every_advertised_tool_is_a_closed_strict_function_schema(
    label: str, definition: dict[str, Any]
) -> None:
    assert definition["type"] == "function"
    assert definition["strict"] is True
    assert re.fullmatch(r"[A-Za-z0-9_-]{1,64}", definition["name"])
    assert definition["description"].strip(), f"{label}: the model needs a description to choose"
    schema = definition["parameters"]
    assert schema["type"] == "object", f"{label}: the root must be an object"
    assert "anyOf" not in schema, f"{label}: the root must not be a union"
    walk = SchemaWalk(schema.get("$defs", {}))
    walk.visit({key: value for key, value in schema.items() if key != "$defs"}, label)
    assert walk.properties <= MAX_OBJECT_PROPERTIES
    assert walk.deepest <= MAX_OBJECT_DEPTH


@pytest.mark.parametrize("role", list(ROLE_DEFINITIONS))
def test_a_role_never_advertises_the_same_tool_twice(role: str) -> None:
    names = [definition["name"] for definition in ROLE_DEFINITIONS[role]()]
    assert len(names) == len(set(names))


def test_walker_reports_the_violations_it_exists_to_catch() -> None:
    open_object = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    optional = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": [],
        "additionalProperties": False,
    }
    for broken, message in (
        (open_object, "closed"),
        (optional, "required"),
        ({"oneOf": [{"type": "string"}]}, "oneOf"),
        ({"$ref": "#/$defs/missing"}, "dangling"),
        ({"$ref": "#/$defs/a", "description": "sibling"}, "sibling"),
        ({"type": "string", "not": {"const": "x"}}, "not"),
        ({}, "untyped"),
    ):
        with pytest.raises(AssertionError, match=message):
            SchemaWalk({"a": {"type": "string"}}).visit(broken, "probe")
    recursive = SchemaWalk({"a": {"type": "array", "items": {"$ref": "#/$defs/a"}}})
    with pytest.raises(AssertionError, match="recursive"):
        recursive.visit({"$ref": "#/$defs/a"}, "probe")
