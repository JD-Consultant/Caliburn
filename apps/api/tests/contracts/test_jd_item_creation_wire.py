"""Five create-item kinds use strict generated wire and existing domain field rules."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from caliburn.contracts.generated.tools import create_jd_item_arguments as wire
from caliburn.features.job_description.areas import CreateArea, InvalidAreaChangeError
from caliburn.features.job_description.capabilities import CapabilityKind, CreateCapability
from caliburn.features.job_description.collaborators import CreateCollaborator
from caliburn.features.job_description.conditions import ConditionKind, CreateCondition
from caliburn.features.job_description.sources import MemorySourceLayer
from caliburn.transport.model_tools.jd_item_creation_wire import parse_item_creation
from caliburn.workflows.jd_sources import (
    CurrentInputSourceSelection,
    InterviewSourceSelection,
    MemorySourceSelection,
)


def schema() -> dict:
    return json.loads(
        (
            Path(__file__).parents[2] / "contracts/tools/create-jd-item-arguments.schema.json"
        ).read_text(encoding="utf-8")
    )


def test_five_kinds_keep_their_own_fields_and_do_not_normalize_text() -> None:
    cases = [
        (
            {"kind": "responsibility_area", "title": None, "scope_text": "  網站交付\r\n"},
            CreateArea(None, "  網站交付\r\n"),
        ),
        (
            {"kind": "knowledge", "name": "通訊介面", "description": None},
            CreateCapability(CapabilityKind.KNOWLEDGE, "通訊介面", None),
        ),
        (
            {"kind": "skill", "name": None, "description": "撰寫介面測試"},
            CreateCapability(CapabilityKind.SKILL, None, "撰寫介面測試"),
        ),
        (
            {"kind": "collaborator", "name": "設計師", "scope_text": None},
            CreateCollaborator("設計師", None),
        ),
        *[
            (
                {"kind": "job_wide_condition", "condition_kind": kind.value, "text": "既有條件"},
                CreateCondition(kind, "既有條件"),
            )
            for kind in ConditionKind
        ],
    ]
    validator = Draft202012Validator(schema())
    for item, expected in cases:
        payload = {"item": {**item, "supporting_sources": []}}
        validator.validate(payload)
        assert (
            wire.CreateJdItemArguments.model_validate_json(json.dumps(payload)).model_dump(
                mode="json"
            )
            == payload
        )
        parsed = parse_item_creation(json.dumps(payload))
        assert parsed.item == expected
        assert parsed.sources == ()


def test_all_source_choices_map_without_model_ids_or_qualification_bypass() -> None:
    parsed = parse_item_creation(
        json.dumps(
            {
                "item": {
                    "kind": "responsibility_area",
                    "title": "網站交付",
                    "scope_text": None,
                    "supporting_sources": [
                        {"kind": "current_input"},
                        {"kind": "interview", "interview_sequence": 3},
                        {"kind": "work_situation", "target_title": " 網站頁面交付 "},
                        {"kind": "work_understanding", "target_title": "網站前端交付"},
                    ],
                }
            }
        )
    )
    assert parsed.sources == (
        CurrentInputSourceSelection(),
        InterviewSourceSelection(3),
        MemorySourceSelection(MemorySourceLayer.WORK_SITUATION, " 網站頁面交付 "),
        MemorySourceSelection(MemorySourceLayer.WORK_UNDERSTANDING, "網站前端交付"),
    )


def test_wire_rejects_other_kinds_missing_fields_cross_variant_fields_and_app_identity() -> None:
    item = {
        "kind": "responsibility_area",
        "title": "網站交付",
        "scope_text": None,
        "supporting_sources": [],
    }
    invalid = [
        {},
        {"item": item, "command_id": "not-model-owned"},
        *[{"item": {k: v for k, v in item.items() if k != field}} for field in item],
        *[
            {"item": {**item, "kind": kind}}
            for kind in ("area", "work_task", "outcome", "requirement")
        ],
        *[
            {"item": {**item, field: "forged"}}
            for field in (
                "description",
                "parent_read_ref",
                "item_id",
                "revision_id",
                "job_file_id",
                "position",
            )
        ],
        {"item": {**item, "title": 123}},
        {
            "item": {
                **item,
                "supporting_sources": [{"kind": "current_input", "source_id": "forged"}],
            }
        },
        *[
            {
                "item": {
                    **item,
                    "supporting_sources": [{"kind": "interview", "interview_sequence": sequence}],
                }
            }
            for sequence in (True, "3", 0)
        ],
        {
            "item": {
                **item,
                "supporting_sources": [
                    {"kind": "work_situation", "target_title": "網站", "snapshot_id": "forged"}
                ],
            }
        },
        {
            "item": {
                "kind": "job_wide_condition",
                "condition_kind": "invented",
                "text": "條件",
                "supporting_sources": [],
            }
        },
    ]
    validator = Draft202012Validator(schema())
    for payload in invalid:
        assert not validator.is_valid(payload), payload
        with pytest.raises(ValidationError):
            parse_item_creation(json.dumps(payload))


def test_strict_schema_keeps_nested_variants_and_domain_rejects_empty_area() -> None:
    contract = schema()
    Draft202012Validator.check_schema(contract)
    assert contract["type"] == "object" and "anyOf" not in contract

    def assert_strict(node: object) -> None:
        if isinstance(node, list):
            for value in node:
                assert_strict(value)
        elif isinstance(node, dict):
            if node.get("type") == "object":
                assert node["additionalProperties"] is False
                assert set(node["required"]) == set(node["properties"])
            for value in node.values():
                assert_strict(value)

    assert_strict(contract)
    # Wire shape accepts explicit unknown values; the original domain forbids an empty shell.
    for title in (None, " ", "\x00"):
        with pytest.raises(InvalidAreaChangeError):
            parse_item_creation(
                json.dumps(
                    {
                        "item": {
                            "kind": "responsibility_area",
                            "title": title,
                            "scope_text": None,
                            "supporting_sources": [],
                        }
                    }
                )
            )
