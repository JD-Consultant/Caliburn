"""A repeated native history must not multiply distinct tool reads."""

import importlib.util
import json
from pathlib import Path


def test_project_usage_and_unique_reads_with_plain_user_items(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "organization_analysis", Path(__file__).with_name("analyze.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request = {
        "cell": "control-1",
        "event": "request",
        "path": "/v1/responses",
        "payload": {
            "input": [
                {"role": "user", "content": "參考資料"},
                {"type": "function_call_output", "call_id": "r1", "output": "abc"},
            ]
        },
    }
    response = {
        "cell": "control-1",
        "event": "response",
        "path": "/v1/responses",
        "payload": {
            "usage": {
                "input_tokens": 100,
                "output_tokens": 30,
                "input_tokens_details": {"cached_tokens": 40},
                "output_tokens_details": {"reasoning_tokens": 10},
            },
            "output": [
                {
                    "type": "function_call",
                    "call_id": "r1",
                    "name": "read_work_understanding",
                    "arguments": "{}",
                }
            ],
        },
    }
    (tmp_path / "trace.jsonl").write_text(
        "\n".join(json.dumps(item) for item in [response, request, request]),
        encoding="utf-8",
    )
    result = module.summarize(tmp_path)["control-1"]
    assert result["input_tokens"] == 100
    assert result["cached_tokens"] == 40
    assert result["output_tokens"] == 30
    assert result["reasoning_tokens"] == 10
    assert result["tools_by_name"] == {"read_work_understanding": 1}
    assert result["read_output_characters"] == 3


def test_incomplete_response_counts_usage_but_not_partial_tool_execution(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "organization_analysis", Path(__file__).with_name("analyze.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    event = {
        "cell": "candidate-2",
        "event": "response",
        "path": "/v1/responses",
        "payload": {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "usage": {"input_tokens": 100, "output_tokens": 8192},
            "output": [
                {
                    "type": "function_call",
                    "call_id": "x",
                    "name": "create_work_understanding",
                    "arguments": '{"body":"unfinished',
                }
            ],
        },
    }
    (tmp_path / "trace.jsonl").write_text(json.dumps(event), encoding="utf-8")
    result = module.summarize(tmp_path)["candidate-2"]
    assert result["output_tokens"] == 8192
    assert result["tools_by_name"] == {}
    assert result["incomplete_responses"][0]["reason"] == "max_output_tokens"
