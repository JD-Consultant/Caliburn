"""Formal process composition for the completed consultant; no model request."""

from jd_relational.openrouter_model import ReceiptChatOpenRouter
from jd_relational.consultant_runtime import open_consultant_runtime
from jd_relational.memory_context import build_consultant_tools
from langchain_core.utils.function_calling import convert_to_openai_tool


_OPENAI_BASE_FORBIDDEN_SCHEMA_KEYS = frozenset({
    "allOf", "not", "dependentRequired", "dependentSchemas",
    "if", "then", "else", "oneOf",
})


def _schema_issues(schema, path="root"):
    issues = []
    if not isinstance(schema, dict):
        return issues
    for key in _OPENAI_BASE_FORBIDDEN_SCHEMA_KEYS:
        if key in schema:
            issues.append((path, f"unsupported_keyword:{key}"))
    if path == "root" and "anyOf" in schema:
        issues.append((path, "root_anyOf"))
    if schema.get("type") == "object":
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is not False:
            issues.append((path, "additionalProperties_not_false"))
        if set(schema.get("required", [])) != set(properties):
            issues.append((path, "required_does_not_match_properties"))
    for key, value in schema.items():
        if isinstance(value, dict):
            issues.extend(_schema_issues(value, f"{path}.{key}"))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                issues.extend(_schema_issues(child, f"{path}.{key}[{index}]"))
    return issues


def test_runtime_assembles_existing_tools_once_and_closes_owned_clients():
    runtime = open_consultant_runtime(api_key="synthetic-runtime-not-a-key")
    assert isinstance(runtime.role_models.consultant, ReceiptChatOpenRouter)
    assert isinstance(runtime.role_models.case, ReceiptChatOpenRouter)
    assert isinstance(runtime.role_models.understanding, ReceiptChatOpenRouter)
    tools = set(runtime.graph.nodes["tools"].bound.tools_by_name)
    assert {"jd_read", "jd_set_text", "repair_memory",
            "request_memory_consolidation"}.issubset(tools)
    assert any("BackgroundAvailability" in node for node in runtime.graph.nodes)
    assert not runtime.http_client.is_closed and not runtime.async_http_client.is_closed
    assert runtime.close() is True
    assert runtime.http_client.is_closed and runtime.async_http_client.is_closed
    assert runtime.close() is True, "closing the process-owned runtime is idempotent"


def test_consultant_tools_are_strict_and_have_no_root_union():
    definitions = [convert_to_openai_tool(tool, strict=True)
                   for tool in build_consultant_tools()]
    names = [item["function"]["name"] for item in definitions]
    assert len(names) == 20 and len(set(names)) == len(names)
    for definition in definitions:
        function = definition["function"]
        parameters = function["parameters"]
        assert definition["type"] == "function"
        assert function["strict"] is True
        assert parameters["type"] == "object"
        assert _schema_issues(parameters) == []

    request = next(item for item in definitions
                   if item["function"]["name"] == "request_memory_consolidation")
    assert request["function"]["parameters"]["required"] == []


def test_openai_base_subset_audit_rejects_unsupported_composition_only():
    assert ("root", "unsupported_keyword:allOf") in _schema_issues({
        "type": "object", "properties": {}, "required": [],
        "additionalProperties": False, "allOf": [],
    })
    assert ("root", "root_anyOf") in _schema_issues({"anyOf": []})
    assert _schema_issues({
        "type": "object", "properties": {
            "items": {"type": "array", "minItems": 1, "maxItems": 2},
        }, "required": ["items"], "additionalProperties": False,
    }) == []
