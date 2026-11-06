"""Memory 拒絕保留可修正原因與位置，不回顯輸入或推斷 union 分支。"""

import asyncio
import json

import pytest

from caliburn.bundles.memory.reads import create_read_tools
from caliburn.bundles.memory.tool_output import model_rejection
from caliburn.bundles.memory.writes import create_write_tools
from caliburn.shared.domain.text_editing.body_edits import EditLimits, apply_body_diff
from caliburn.shared.domain.text_editing.errors import TextEditError


@pytest.fixture(autouse=True)
def isolate_external_tracing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")


def rejected_arguments(name: str, arguments: dict[str, object]) -> dict[str, str]:
    tools = (
        *create_read_tools("consultant", limit=1000),
        *create_write_tools("situation", limit=1000),
        *create_write_tools("understanding", limit=1000),
    )
    tool = next(tool for tool in tools if tool.name == name)

    async def invoke() -> str:
        output = await tool.ainvoke({"runtime": None, **arguments})
        assert isinstance(output, str)
        return output

    output = asyncio.run(invoke(), loop_factory=asyncio.SelectorEventLoop)
    result: dict[str, str] = json.loads(output)
    return result


@pytest.mark.parametrize(
    ("name", "arguments", "location"),
    [
        ("read_work_situation", {}, "target_title"),
        (
            "create_work_situation",
            {
                "title": "盤點",
                "description": "庫存核對",
                "body": "每日核對庫存。",
                "interview_references": [42],
            },
            "interview_references[0]",
        ),
        (
            "update_work_situation",
            {"target_title": "盤點", "changes": [{"field": "body"}]},
            "changes[0]",
        ),
        (
            "update_work_understanding",
            {
                "target_title": "盤點",
                "changes": [{"field": "work_situation_references", "add": [42]}],
            },
            "changes[0]",
        ),
        (
            "update_work_understanding",
            {
                "target_title": "盤點",
                "changes": [
                    {
                        "field": "work_situation_references",
                        "add": ["盤點"],
                        "remove": [42],
                    }
                ],
            },
            "changes[0]",
        ),
        (
            "update_work_situation",
            {"target_title": "盤點", "changes": [{"field": "secret-field-value"}]},
            "changes[0]",
        ),
    ],
)
def test_argument_rejection_locates_the_public_field(
    name: str, arguments: dict[str, object], location: str
) -> None:
    result = rejected_arguments(name, arguments)

    assert set(result) == {"status", "code", "message", "next_action"}
    assert result["status"] == "rejected"
    assert result["code"] == "invalid_arguments"
    assert result["message"].startswith(f"{location} ")
    assert "ChangeBody" not in result["message"]
    assert "ChangeText" not in result["message"]
    assert "secret-field-value" not in json.dumps(result)


@pytest.mark.parametrize(
    ("name", "arguments", "location"),
    [
        (
            "read_work_situation",
            {"target_title": "盤點", "private-property": "private-value"},
            "<extra>",
        ),
        (
            "update_work_situation",
            {
                "target_title": "盤點",
                "changes": [
                    {
                        "field": "body",
                        "diff": "@@\n-原文\n+新文",
                        "private-property": "private-value",
                    }
                ],
            },
            "changes[0]",
        ),
    ],
)
def test_extra_argument_rejection_hides_the_untrusted_key_and_value(
    name: str, arguments: dict[str, object], location: str
) -> None:
    result = rejected_arguments(name, arguments)

    assert result["message"].startswith(f"{location} ")
    assert "private-property" not in json.dumps(result)
    assert "private-value" not in json.dumps(result)
    assert result["code"] == "invalid_arguments"


def test_duplicate_change_fields_keep_the_model_level_correction() -> None:
    result = rejected_arguments(
        "update_work_situation",
        {
            "target_title": "盤點",
            "changes": [
                {"field": "title", "value": "第一次"},
                {"field": "title", "value": "第二次"},
            ],
        },
    )

    assert result["code"] == "invalid_arguments"
    assert "參數" in result["message"]
    assert "每個變更欄位只列一次" in result["next_action"]


@pytest.mark.parametrize(
    ("body", "diff", "code", "reason", "hunk"),
    [
        (
            "內部原文甲\n內部原文乙\n內部原文丙\n",
            "@@\n-內部原文甲\n+新正文甲\n@@\n-內部原文乙\n+新正文乙\n@@\n 內部原文丙\n",
            "invalid_patch",
            "Each hunk needs an edit and source context or an explicit EOF",
            None,
        ),
        (
            "內部原文甲\n內部原文乙\n未知尾段丙\n",
            "@@\n-內部原文甲\n+新正文甲\n 內部原文乙\n*** End of File",
            "patch_context_not_found",
            "No source context qualifies",
            1,
        ),
    ],
    ids=["third-hunk-has-no-edit", "early-section-is-not-eof"],
)
def test_patch_rejection_preserves_safe_reason_and_location(
    body: str, diff: str, code: str, reason: str, hunk: int | None
) -> None:
    with pytest.raises(TextEditError) as rejected:
        apply_body_diff(body, diff, limits=EditLimits(1000, 1000, 10, 100000))
    error = rejected.value
    assert error.code == code
    assert str(error) == reason
    assert error.hunk_number == hunk

    output = str(model_rejection(error))
    result = json.loads(output)

    assert set(result) == {"status", "code", "message", "next_action"}
    assert result["status"] == "rejected"
    assert result["code"] == code
    assert reason in result["message"]
    if hunk is not None:
        assert f"第 {hunk} 段。" in result["message"]
    else:
        assert "第 " not in result["message"]
    assert result["next_action"] == (
        "核對目前正文及完整行，補足唯一定位的上下文或縮小修改範圍。"
    )
    for line in body.splitlines():
        assert line not in output
    assert "新正文甲" not in output
    assert "新正文乙" not in output
