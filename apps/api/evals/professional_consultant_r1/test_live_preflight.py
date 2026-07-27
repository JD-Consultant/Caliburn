"""Segment 4：只測會擋住 live preflight 結論污染的 pure seams。"""

from __future__ import annotations

import pytest

from .assembler import STAGE_FINAL, assemble_stage
from .live_preflight import (
    DISPOSABLE_CASE,
    CatalogBinding,
    LiveModelPort,
    _attest_route,
    parse_chat_payload,
    parse_grader_payload,
    select_catalog_binding,
)
from .matrix import arm_by_id
from .transport import OUTCOME_OK, TokenUsage, WireResult


def test_catalog_binding_pins_alias_canonical_slug_and_exact_endpoint() -> None:
    model = {
        "data": {
            "id": "openai/gpt-5.6-sol-pro",
            "canonical_slug": "openai/gpt-5.6-sol-pro-20260709",
            "supported_parameters": [
                "max_tokens",
                "reasoning",
                "response_format",
                "structured_outputs",
            ],
            "pricing": {"prompt": "0.000005", "completion": "0.00003"},
        }
    }
    endpoints = {
        "data": {
            "endpoints": [
                {
                    "tag": "openai",
                    "provider_name": "OpenAI",
                    "supported_parameters": ["response_format", "structured_outputs"],
                },
                {
                    "tag": "openai/flex",
                    "provider_name": "OpenAI",
                    "supported_parameters": [
                        "max_tokens",
                        "reasoning",
                        "response_format",
                        "structured_outputs",
                    ],
                    "pricing": {"prompt": "0.0000025", "completion": "0.000015"},
                },
            ]
        }
    }

    binding = select_catalog_binding(
        model,
        endpoints,
        requested_model="openai/gpt-5.6-sol-pro",
        endpoint_tag="openai/flex",
        required_parameters={
            "max_tokens",
            "reasoning",
            "response_format",
            "structured_outputs",
        },
    )

    assert binding.canonical_model == "openai/gpt-5.6-sol-pro-20260709"
    assert binding.endpoint_tag == "openai/flex"
    assert binding.provider_name == "OpenAI"
    assert len(binding.snapshot_hash) == 64


def test_chat_parser_returns_only_structured_message_content() -> None:
    payload = parse_chat_payload(
        {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": '{"answer":"ok"}'},
                }
            ]
        }
    )
    assert payload == {"answer": "ok"}

    with pytest.raises(ValueError, match="exactly one choice"):
        parse_chat_payload({"choices": []})


def test_grader_parser_requires_every_label_and_dimension_once() -> None:
    parsed = parse_grader_payload(
        {
            "grades": [
                {
                    "label": "candidate-01",
                    "dimensions": [
                        {
                            "dimension": "meaningful_outcome",
                            "verdict": "pass",
                            "reason": "有結果",
                        }
                    ],
                }
            ]
        },
        expected_labels={"candidate-01"},
        expected_dimensions={"meaningful_outcome"},
    )
    assert parsed == {"candidate-01": {"meaningful_outcome": "pass"}}

    with pytest.raises(ValueError, match="labels"):
        parse_grader_payload(
            {"grades": []},
            expected_labels={"candidate-01"},
            expected_dimensions={"meaningful_outcome"},
        )


@pytest.mark.asyncio
async def test_live_port_routes_arm_by_declared_model_role() -> None:
    class RecordingSession:
        def __init__(self) -> None:
            self.role = None

        async def send_structured(self, **kwargs):
            self.role = kwargs["role"]
            return {}

    session = RecordingSession()
    stage = assemble_stage(DISPOSABLE_CASE, arm_by_id("A1"), STAGE_FINAL)

    await LiveModelPort(session).complete(stage)

    assert session.role == "strongest"


def test_route_attestation_uses_available_not_catalog_total() -> None:
    """Live shape：total 可含被 filter 的 catalog 候選；available 才是實際可路由集合。"""
    binding = CatalogBinding(
        requested_model="openai/gpt-5.6-sol-pro",
        canonical_model="openai/gpt-5.6-sol-pro-20260709",
        endpoint_tag="openai/flex",
        provider_name="OpenAI",
        prompt_price="0.0000025",
        completion_price="0.000015",
        snapshot_hash="a" * 64,
        model_snapshot={},
        endpoint_snapshot={},
    )
    wire = WireResult(
        outcome=OUTCOME_OK,
        status_code=200,
        headers={},
        body={
            "openrouter_metadata": {
                "requested": binding.requested_model,
                "strategy": "direct",
                "attempt": 1,
                "endpoints": {
                    "total": 3,
                    "available": [
                        {
                            "provider": "OpenAI",
                            "model": binding.canonical_model,
                            "selected": True,
                        }
                    ],
                },
            }
        },
        raw_text=None,
        latency_ms=1,
        usage=TokenUsage(cost="0.01"),
    )

    assert _attest_route(wire, binding) == (
        binding.canonical_model,
        binding.provider_name,
    )
