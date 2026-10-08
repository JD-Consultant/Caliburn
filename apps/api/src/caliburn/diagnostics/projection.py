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
    """依原請求身分合併觀察；只有已保存請求時也保留，不推定已外送。"""
    steps: dict[tuple[str, str], dict[str, Any]] = {}
    for record in records:
        if record["thread_id"].endswith(":initial_context"):
            continue
        values = record["values"]
        response = values.get("response_snapshot")
        request = values.get("request_snapshot")
        request_id = values.get("request_id")
        if not request and not response:
            continue
        if response and (not isinstance(response, dict) or not isinstance(response.get("id"), str)):
            raise ValueError("Invalid saved response snapshot")
        # 舊診斷輸入未帶 request_id 時沿用 response ID；不拿相同正文猜請求身分。
        identity = (
            f"request:{request_id}"
            if request_id is not None
            else f"response:{response['id']}"
            if response
            else f"checkpoint:{record['checkpoint_id']}"
        )
        key = (record["thread_id"], identity)
        if key not in steps:
            steps[key] = {
                **{key: value for key, value in record.items() if key != "values"},
                "request_id": request_id,
                "request": deepcopy(request),
                "response": None,
                "response_state": "request_only",
                "tool_results": {},
            }
        step = steps[key]
        if not response:
            continue
        if step["response"] is None:
            step.update(
                response=deepcopy(response),
                response_state="recorded",
                response_checkpoint_id=record["checkpoint_id"],
                response_checkpoint_time=record["checkpoint_time"],
                response_source=record["source"],
            )
        elif step["response"] != response:
            raise ValueError("Conflicting saved responses for one request")
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


def collect_initial_context(records: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """只查當時捕捉的綁定；可讀版本不代表工具實際讀過正文。"""
    captured = None
    for record in records:
        if not record["thread_id"].endswith(":job_consultant:initial_context"):
            continue
        values = record["values"]
        binding = values.get("binding")
        request = values.get("request_snapshot")
        if not binding or not request:
            continue
        if not isinstance(binding, dict) or not isinstance(request, dict):
            raise ValueError("Invalid saved initial context")
        tool_configuration = (
            {"jd_read_max_result_characters": values["jd_read_max_result_characters"]}
            if "jd_read_max_result_characters" in values
            else None
        )
        if captured is not None:
            if (
                captured["binding"] != binding
                or captured["request"] != request
                or captured["tool_configuration"] != tool_configuration
            ):
                raise ValueError("Conflicting saved initial contexts")
            continue
        captured = {
            **{key: value for key, value in record.items() if key != "values"},
            "binding": deepcopy(binding),
            "request": deepcopy(request),
            "tool_configuration": deepcopy(tool_configuration),
        }
    return {key: redact(value) for key, value in captured.items()} if captured else None
