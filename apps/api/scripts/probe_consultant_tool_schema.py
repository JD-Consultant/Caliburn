"""One synthetic count-only call to diagnose a role's complete tool schema.

No inference, no business data, no retries. Explicit invocation only.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path

from openai import APIConnectionError, APIStatusError

from caliburn.adapters.openai_credentials import read_openai_api_key
from caliburn.adapters.openai_responses import (
    ResponseRequest,
    count_response_input,
    create_responses_client,
)
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.memory_analysis import memory_analysis_tool_definitions

ROLE_LAYERS = {
    "work_situation_analyst": MemoryLayer.WORK_SITUATION,
    "work_understanding_analyst": MemoryLayer.WORK_UNDERSTANDING,
}


async def probe(key_file: Path, *, role: str = "consultant") -> None:
    definitions = (
        consultant_tool_definitions()
        if role == "consultant"
        else memory_analysis_tool_definitions(ROLE_LAYERS[role])
    )
    request = ResponseRequest(
        model="gpt-6-luna",
        instructions="Synthetic schema validation only.",
        input_items=[{"role": "user", "content": "Validate the tool schema."}],
        tools=definitions,
        reasoning_effort="medium",
        max_output_tokens=512,
    )
    evidence = {
        "role": role,
        "tool_names": [definition["name"] for definition in definitions],
        "definitions_sha256": hashlib.sha256(
            json.dumps(
                definitions, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode()
        ).hexdigest(),
        "http_requests": 1,
        "generation_requests": 0,
        "retries": 0,
        "timeout_seconds": 30,
    }
    key = read_openai_api_key(key_file)
    async with create_responses_client(api_key=key, timeout_seconds=30) as client:
        try:
            async with asyncio.timeout(30):
                result = await count_response_input(client, request)
        except APIStatusError as error:
            # Only this synthetic probe exposes provider schema diagnostics. Never dump
            # response bodies/headers or reuse this path for employee data.
            body = error.body if isinstance(error.body, dict) else {}
            detail = body.get("error", body)
            message = detail.get("message", "") if isinstance(detail, dict) else ""
            print(
                json.dumps(
                    {
                        **evidence,
                        "accepted": False,
                        "status": error.status_code,
                        "code": error.code,
                        "param": error.param,
                        "schema_message": str(message).replace(key, "[redacted]")[:1500],
                    }
                ).replace(key, "[redacted]")
            )
            raise SystemExit(1) from None
        except (APIConnectionError, TimeoutError) as error:
            print(json.dumps({**evidence, "accepted": False, "error_type": type(error).__name__}))
            raise SystemExit(1) from None
        print(json.dumps({**evidence, "accepted": True, "input_tokens": result.input_tokens}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--role", choices=("consultant", *ROLE_LAYERS), default="consultant")
    args = parser.parse_args()
    asyncio.run(probe(args.key_file, role=args.role))
