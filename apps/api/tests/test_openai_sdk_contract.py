"""Pinned SDK surface required by the vNext eval-only Responses adapter."""

from importlib.metadata import version
from inspect import signature

from openai import AsyncOpenAI


async def test_pinned_openai_sdk_exposes_required_responses_surface() -> None:
    client = AsyncOpenAI(api_key="test-only-not-a-real-key")
    try:
        assert version("openai") == "2.46.0"

        create_parameters = signature(client.responses.create).parameters
        assert {
            "input",
            "model",
            "reasoning",
            "store",
            "text",
            "truncation",
            "timeout",
        } <= create_parameters.keys()

        parse_parameters = signature(client.responses.parse).parameters
        assert "text_format" in parse_parameters
        assert {
            "input",
            "model",
            "reasoning",
            "store",
            "truncation",
            "timeout",
        } <= parse_parameters.keys()
    finally:
        await client.close()
