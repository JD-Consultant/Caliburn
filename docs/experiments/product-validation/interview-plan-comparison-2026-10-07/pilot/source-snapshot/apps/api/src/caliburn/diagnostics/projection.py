"""Project native JSON checkpoints for inspection, not for replay or business decisions.

Any is limited to the native serialization boundary. These objects never enter domain code.
"""

import json
import re
from collections.abc import Iterable
from copy import deepcopy
from typing import Any
from uuid import UUID

ROLES = {"job_consultant", "work_situation_analyst", "work_understanding_analyst"}
SENSITIVE_FIELDS = {"encrypted_content", "api_key", "openai_api_key", "authorization", "password"}


def role_for_thread(thread_id: str, prefix: str) -> str | None:
    if not thread_id.startswith(prefix):
        return None
    parts = thread_id[len(prefix) :].split(":")
    if len(parts) not in (2, 5) or parts[0] not in ROLES or parts[1] != "completed_work":
        return None
    if len(parts) == 5:
        if parts[2] != "stage":
            return None
        try:
            UUID(parts[3])
            UUID(parts[4])
        except ValueError:
            return None
    return parts[0]


def redact(value: Any) -> Any:
    """Mask known sensitive fields, including JSON tool strings; not a PII anonymizer."""
    if isinstance(value, dict):
        return {
            key: "[redacted]" if key.lower() in SENSITIVE_FIELDS else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, str):
        if value.lstrip().startswith(("{", "[")):
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                pass
            else:
                cleaned = redact(decoded)
                if cleaned != decoded:
                    return json.dumps(cleaned, ensure_ascii=False)
        return re.sub(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}", "[redacted]", value)
    return value


def collect_steps(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Consume chronological checkpoint/pending-write observations, preserving first input."""
    steps: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        values = record["values"]
        response = values.get("response_snapshot")
        if not response:
            continue
        if not isinstance(response, dict) or not isinstance(response.get("id"), str):
            raise ValueError("Invalid saved response snapshot")
        key = (record["thread_id"], response["id"])
        if key not in steps:
            steps[key] = {
                **{key: value for key, value in record.items() if key != "values"},
                "request": deepcopy(values.get("request_snapshot")),
                "response": deepcopy(response),
                "tool_results": {},
            }
        step = steps[key]
        calls = {
            item["call_id"] for item in response["output"] if item.get("type") == "function_call"
        }
        for result in values.get("tool_results", []):
            call_id = result["call_id"]
            if call_id not in calls:
                continue
            if (
                call_id in step["tool_results"]
                and step["tool_results"][call_id] != result["output"]
            ):
                raise ValueError("Conflicting saved tool results")
            step["tool_results"][call_id] = deepcopy(result["output"])
    return [redact(step) for step in steps.values()]
