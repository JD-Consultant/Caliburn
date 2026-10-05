"""Research guardrails: reject raw-history leakage and corrupted replay order."""

import importlib.util
import sys
from pathlib import Path

import pytest


def load_support():
    path = Path(__file__).with_name("support.py")
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("long_memory_support", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def require_support():
    support = load_support()
    assert support is not None, "Missing experiment context isolation and replay guards"
    return support


def test_replay_keeps_employee_wording_and_genuine_roles():
    support = require_support()
    messages = support.replay_messages(
        [
            {
                "turn": 1,
                "status": "completed",
                "employee": "第一段\n原話",
                "consultant": "釐清？",
            },
            {
                "turn": 2,
                "status": "completed",
                "employee": "更正。",
                "consultant": "完成。",
            },
        ]
    )
    assert [
        (m["interview_sequence"], m["speaker"], m["text"]) for m in messages[1:]
    ] == [
        (2, "employee", "第一段\n原話"),
        (3, "consultant", "釐清？"),
        (4, "employee", "更正。"),
        (5, "consultant", "完成。"),
    ]


def test_replay_rejects_cancelled_and_nonconsecutive_turns():
    support = require_support()
    for turns in [
        [{"turn": 1, "status": "cancelled", "employee": "不保留", "consultant": ""}],
        [
            {
                "turn": 2,
                "status": "completed",
                "employee": "漏第一段",
                "consultant": "答覆",
            }
        ],
    ]:
        with pytest.raises(ValueError):
            support.replay_messages(turns)


def test_hierarchical_start_has_maps_and_recent_only():
    support = require_support()
    messages = [
        {"interview_sequence": n, "speaker": "employee", "text": f"原話{n}"}
        for n in range(1, 92)
    ]
    context = support.recall_context(
        "hierarchical_memory", messages, {"work_situation_map": {"items": []}}, "問題"
    )
    import json

    data = json.loads(context[0]["content"])
    assert [
        m["interview_sequence"] for m in data["historical_interview"]["messages"]
    ] == [89, 90, 91]
    assert '原話2"' not in context[0]["content"]
    assert all(item["role"] == "user" for item in context)
    support.assert_isolated_recall_context(context)


@pytest.mark.parametrize(
    "item",
    [
        {"type": "compaction", "encrypted_content": "opaque"},
        {"type": "reasoning", "encrypted_content": "opaque"},
        {"type": "function_call_output", "call_id": "old", "output": "舊觀察"},
        {
            "role": "user",
            "content": '{"historical_interview":{"messages":[{"interview_sequence":2,"text":"早期原話"}]}}',
        },
    ],
)
def test_initial_recall_rejects_old_native_history_and_raw_sequences(item):
    support = require_support()
    with pytest.raises(ValueError):
        support.assert_isolated_recall_context([item])


def test_memory_read_tools_do_not_expose_raw_archive_for_primary_recall():
    support = require_support()
    names = [item["name"] for item in support.recall_read_definitions()]
    assert names == [
        "read_work_situation_map",
        "read_work_situation",
        "read_work_understanding_map",
        "read_work_understanding",
    ]


def test_probe_question_projection_does_not_send_gold_facts():
    support = require_support()
    question = support.probe_question(
        [
            {
                "case_id": "q",
                "question": "期限？",
                "facts": ["GOLD_DO_NOT_SEND"],
                "support_sequences": [2],
            }
        ]
    )
    assert "期限？" in question
    assert "GOLD_DO_NOT_SEND" not in question
    assert "support_sequences" not in question
