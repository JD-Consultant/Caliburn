"""R1 public contract tests; no provider, network, DB, or legacy runtime."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.professional_consultant.contracts import (
    ClaimCertainty,
    ClaimKind,
    OwnershipScope,
    Polarity,
    SourceClaim,
    EmployeeMessage,
    SourceSpan,
    TaskDiscoveryOutput,
    TimeScope,
    TurnUnderstandOutput,
    Typicality,
)


def _object_schemas(schema: object) -> list[dict[str, object]]:
    if isinstance(schema, dict):
        current = [schema] if "properties" in schema else []
        for value in schema.values():
            current.extend(_object_schemas(value))
        return current
    if isinstance(schema, list):
        objects: list[dict[str, object]] = []
        for value in schema:
            objects.extend(_object_schemas(value))
        return objects
    return []


def test_source_contracts_are_strict_frozen_and_json_compatible() -> None:
    message = EmployeeMessage.model_validate_json(
        '{"message_id":"message-1","text":"我每週整理門市資料。"}'
    )
    span = SourceSpan.model_validate_json(
        '{"message_id":"message-1","start":2,"end":4,"quote":"每週"}'
    )

    assert message.text == "我每週整理門市資料。"
    assert (span.start, span.end, span.quote) == (2, 4, "每週")

    with pytest.raises(ValidationError):
        SourceSpan(message_id="message-1", start="2", end=4, quote="每週")
    with pytest.raises(ValidationError):
        EmployeeMessage(message_id="message-1", text="內容", unknown="forbidden")
    with pytest.raises(ValidationError):
        message.text = "不得修改"


def test_operation_contracts_allow_empty_task_results_without_coercion() -> None:
    output = TaskDiscoveryOutput.model_validate_json(
        """{
          "schema_version":"task_discovery_output.v1",
          "claims":[],
          "unmapped_signals":[],
          "stories":[],
          "work_units":[],
          "decisions":[],
          "task_candidates":[],
          "next_question":{
            "action":"broaden",
            "text":"除了這次協助之外，你平常固定負責哪些工作？",
            "target_gap":"尚未找到穩定的本人責任",
            "claim_ids":[]
          }
        }"""
    )

    assert output.task_candidates == ()
    assert output.next_question.action == "broaden"
    with pytest.raises(ValidationError):
        TurnUnderstandOutput(
            schema_version="turn_understand_output.v1",
            claims=[],
            unmapped_signals=(),
        )


def test_correction_claim_requires_an_existing_target_key_shape() -> None:
    common = {
        "claim_id": "claim-correction",
        "kind": ClaimKind.CORRECTION,
        "statement": "正式部署是維運負責",
        "ownership": OwnershipScope.OTHER_RESPONSIBLE,
        "time_scope": TimeScope.CURRENT,
        "typicality": Typicality.ROUTINE,
        "polarity": Polarity.AFFIRMED,
        "certainty": ClaimCertainty.EXPLICIT,
        "action": "部署",
        "object": "正式版本",
        "recipient": None,
        "outcome": None,
        "tool_or_method": None,
        "condition": None,
        "anchors": (
            SourceSpan(
                message_id="message-2", start=6, end=14, quote="正式部署是維運負責"
            ),
        ),
    }

    with pytest.raises(ValidationError):
        SourceClaim(**common, correction_target_claim_id=None)
    claim = SourceClaim(**common, correction_target_claim_id="claim-old-deploy")
    assert claim.correction_target_claim_id == "claim-old-deploy"


def test_task_discovery_schema_keeps_every_object_closed_and_explicit() -> None:
    schema = TaskDiscoveryOutput.model_json_schema()

    assert set(schema["required"]) == {
        "schema_version",
        "claims",
        "unmapped_signals",
        "stories",
        "work_units",
        "decisions",
        "task_candidates",
        "next_question",
    }
    object_schemas = _object_schemas(schema)
    assert object_schemas
    assert all(item.get("additionalProperties") is False for item in object_schemas)
    assert all("default" not in item for item in object_schemas)
