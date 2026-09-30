"""The canonical manual/source wire never lets a model select private coordinates."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.transport.model_tools.jd_changes import jd_changes_definitions
from caliburn.transport.model_tools.jd_changes_wire import parse_jd_changes
from caliburn.workflows.jd_changes import ManualChangeQuery, SourceChangeQuery


def test_definition_sends_authoritative_schema_without_ref_sibling_keywords() -> None:
    expected = json.loads(
        (
            Path(__file__).parents[2] / "contracts/tools/read-jd-changes-arguments.schema.json"
        ).read_text(encoding="utf-8")
    )
    expected.pop("$schema")
    parameters = jd_changes_definitions()[0]["parameters"]
    assert parameters == expected

    def check(node: object) -> None:
        if isinstance(node, list):
            for value in node:
                check(value)
        elif isinstance(node, dict):
            if "$ref" in node:
                assert set(node) == {"$ref"}, node
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                check(value)

    check(parameters)


def test_canonical_variants_are_strict_and_definitions_need_no_binding() -> None:
    schema = json.loads(
        (
            Path(__file__).parents[2] / "contracts/tools/read-jd-changes-arguments.schema.json"
        ).read_text(encoding="utf-8")
    )
    validator = Draft202012Validator(schema)
    Draft202012Validator.check_schema(schema)
    assert schema["type"] == "object" and "anyOf" not in schema
    definition = jd_changes_definitions()[0]
    assert definition["name"] == "read_jd_changes" and definition["strict"] is True
    manual = [
        {"kind": "all"},
        {"kind": "item", "read_ref": "task_known"},
        {"kind": "profile_field", "field": "purpose"},
        *[
            {"kind": "area", "view": view}
            for view in (
                "profile",
                "responsibility_areas",
                "unassigned_work_tasks",
                "required_knowledge",
                "required_skills",
                "main_collaborators",
                "job_wide_conditions",
            )
        ],
    ]
    for scope in manual:
        payload = {"query": {"kind": "manual", "scope": scope}}
        validator.validate(payload)
        assert isinstance(parse_jd_changes(json.dumps(payload)), ManualChangeQuery)
    payload = {"query": {"kind": "source", "citation_ref": "citation_known"}}
    validator.validate(payload)
    assert parse_jd_changes(json.dumps(payload)) == SourceChangeQuery("citation_known")


def test_cross_variant_null_unknown_and_version_arguments_never_fall_back_to_all() -> None:
    invalid = [
        {},
        {"query": None},
        {"query": {"kind": "manual"}},
        {"query": {"kind": "source", "citation_ref": "citation_known", "scope": {"kind": "all"}}},
        {"query": {"kind": "manual", "scope": {"kind": "all"}, "citation_ref": None}},
        *[
            {"query": {"kind": "manual", "scope": {"kind": "area", "view": view}}}
            for view in ("full", "map", "work_tasks", "item")
        ],
        *[
            {"query": {"kind": "source", "citation_ref": "citation_known", key: "forged"}}
            for key in ("revision_id", "snapshot_id", "job_file_id", "object_id", "cursor")
        ],
        {"query": {"kind": "manual", "scope": {"kind": "profile_field", "field": "invented"}}},
        {"query": {"kind": "source", "citation_ref": 1}},
    ]
    for payload in invalid:
        with pytest.raises(ValidationError):
            parse_jd_changes(json.dumps(payload))
    for query in (
        {"kind": "source", "citation_ref": " "},
        {"kind": "manual", "scope": {"kind": "item", "read_ref": " "}},
    ):
        with pytest.raises(ValueError):
            parse_jd_changes(json.dumps({"query": query}))
