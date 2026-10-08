"""The plan tool captures complete text/results before any saved write can execute."""

import json
import re
from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.adapters.body_edits import describe_body_change
from caliburn.adapters.body_matching import BodyMatchPolicy
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.interview_plans.models import (
    PlanEdit,
    PlanEditResult,
    PlanPosition,
    PlanSnapshot,
)
from caliburn.transport.model_tools.interview_plans import (
    InterviewPlanTools,
    interview_plan_definitions,
)

INITIAL_PLAN = """## 目前焦點
釐清盤點中，本人負責的分工與交接。

## 工作方向
- 收貨：日常流程已入稿；特殊條件尚未探索。
- 盤點：本人分工與交接尚未釐清。
  - 哪些情境適用這套處理方式仍未知；員工暫答不出，有新線索再談。
- 新人帶教：已知有這項工作，尚未深入本人範圍。
- 全稿核對：待主要方向整理後，核對遺漏、依據與跨欄一致。"""
UPDATED_PLAN = """## 目前焦點
釐清新人帶教中，本人負責的判斷與交接。

## 工作方向
- 收貨：日常流程已入稿；特殊條件尚未探索。
- 盤點：本人分工與交接已清楚，待整理進 JD 並核對相關職責與目的。
  - 哪些情境適用這套處理方式仍未知；員工暫答不出，有新線索再談。
- 新人帶教：正在深入本人範圍。
- 全稿核對：待主要方向整理後，核對遺漏、依據與跨欄一致。"""
REFOCUS_DIFF = """@@
 ## 目前焦點
-釐清盤點中，本人負責的分工與交接。
+釐清新人帶教中，本人負責的判斷與交接。
@@
-- 盤點：本人分工與交接尚未釐清。
+- 盤點：本人分工與交接已清楚，待整理進 JD 並核對相關職責與目的。
@@
-- 新人帶教：已知有這項工作，尚未深入本人範圍。
+- 新人帶教：正在深入本人範圍。"""


class FakePlanWorkflow:
    def __init__(self, body: str | None) -> None:
        self.scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
        self.snapshot = PlanSnapshot(
            PlanPosition(self.scope.job_file_id, self.scope.execution_id, uuid4()), body
        )
        self.saved: list[PlanEdit] = []

    async def read_current(self, scope: ExecutionScope) -> PlanSnapshot:
        assert scope == self.scope
        return self.snapshot

    async def apply(self, writer: ExecutionWriter, edit: PlanEdit) -> PlanEditResult:
        assert writer.scope == self.scope
        self.saved.append(edit)
        self.snapshot = PlanSnapshot(edit.position, edit.next_plan)
        return PlanEditResult(self.snapshot, edit.result_text)


def tools_for(body: str | None, **options: object) -> tuple[InterviewPlanTools, FakePlanWorkflow]:
    workflow = FakePlanWorkflow(body)
    return InterviewPlanTools(
        workflow, ExecutionWriter(workflow.scope, uuid4()), **options
    ), workflow


async def test_markdown_refocus_keeps_pending_jd_work_and_unrelated_scope_in_roundtrip() -> None:
    tools, workflow = tools_for(INITIAL_PLAN)
    prepared = await tools.prepare(
        "edit_interview_plan", json.dumps({"diff": REFOCUS_DIFF}), uuid4()
    )
    assert isinstance(prepared, dict)
    assert workflow.saved == []
    result = json.loads(await tools.execute(json.loads(json.dumps(prepared))))
    assert result == {
        "status": "updated",
        "diff": describe_body_change(INITIAL_PLAN, UPDATED_PLAN),
    }
    assert json.loads(await tools.invoke("read_interview_plan", "{}")) == {"plan": UPDATED_PLAN}
    assert workflow.snapshot.body is not None
    for original_line in INITIAL_PLAN.splitlines():
        if "收貨：" in original_line or "哪些情境適用" in original_line:
            assert original_line in workflow.snapshot.body.splitlines()


async def test_advertised_examples_create_and_refocus_one_markdown_plan_in_roundtrip() -> None:
    description = next(
        tool["description"]
        for tool in interview_plan_definitions()
        if tool["name"] == "edit_interview_plan"
    )
    examples = re.findall(r"```diff\n(.*?)\n```", description, re.DOTALL)
    assert len(examples) == 2, "Advertise executable creation and partial-replacement examples"

    tools, workflow = tools_for(None)
    created = await tools.prepare("edit_interview_plan", json.dumps({"diff": examples[0]}), uuid4())
    assert isinstance(created, dict)
    await tools.execute(json.loads(json.dumps(created)))
    assert json.loads(await tools.invoke("read_interview_plan", "{}")) == {"plan": INITIAL_PLAN}

    edited = await tools.prepare("edit_interview_plan", json.dumps({"diff": examples[1]}), uuid4())
    assert isinstance(edited, dict)
    await tools.execute(json.loads(json.dumps(edited)))
    assert json.loads(await tools.invoke("read_interview_plan", "{}")) == {"plan": UPDATED_PLAN}
    assert len(workflow.saved) == 2


async def test_pilot_creation_only_needs_eof_prefix_removed_to_preserve_exact_body() -> None:
    """First warehouse P2 pilot call; tool rejection must not repair malformed intent."""
    requested = (
        "@@\n+## 目前焦點\n+釐清收貨數量差異的查核、處理界線與交接。\n+\n+## 工作方向\n"
        "+- 職務基本資料：員工已說明職稱、單位與匯報對象，待整理入稿；工作時間資訊已知，"
        "是否作為全職務條件再視適用範圍核對。\n"
        "+- 收貨驗收：已知會比對採購單、送貨單與實收數量，並拍照通知採購；"
        "差異處理及完成交接方式待釐清。\n"
        "+- 其他工作：已知上架、揀貨補貨、庫存盤點、客戶退貨、供應商退貨及帶新人，"
        "尚未深入本人做法與責任範圍。\n"
        "+- 全稿核對：主要工作整理後核對涵蓋、依據及跨欄一致。\n+*** End of File"
    )
    expected = (
        "## 目前焦點\n釐清收貨數量差異的查核、處理界線與交接。\n\n## 工作方向\n"
        "- 職務基本資料：員工已說明職稱、單位與匯報對象，待整理入稿；工作時間資訊已知，"
        "是否作為全職務條件再視適用範圍核對。\n"
        "- 收貨驗收：已知會比對採購單、送貨單與實收數量，並拍照通知採購；"
        "差異處理及完成交接方式待釐清。\n"
        "- 其他工作：已知上架、揀貨補貨、庫存盤點、客戶退貨、供應商退貨及帶新人，"
        "尚未深入本人做法與責任範圍。\n"
        "- 全稿核對：主要工作整理後核對涵蓋、依據及跨欄一致。"
    )
    tools, workflow = tools_for(None)
    rejected = await tools.prepare("edit_interview_plan", json.dumps({"diff": requested}), uuid4())
    assert isinstance(rejected, str)
    assert json.loads(rejected)["code"] == "invalid_patch"
    assert workflow.saved == []
    assert json.loads(await tools.invoke("read_interview_plan", "{}")) == {"plan": None}

    corrected_diff = requested.removesuffix("+*** End of File") + "*** End of File"
    prepared = await tools.prepare(
        "edit_interview_plan", json.dumps({"diff": corrected_diff}), uuid4()
    )
    assert isinstance(prepared, dict)
    assert prepared["change"]["next_plan"] == expected
    assert json.loads(await tools.execute(json.loads(json.dumps(prepared))))["status"] == "updated"
    assert json.loads(await tools.invoke("read_interview_plan", "{}")) == {"plan": expected}


@pytest.mark.parametrize(
    ("body", "diff", "code", "example_index", "expected"),
    [
        (
            None,
            "@@ -0,0 +1,2 @@\n+待問：A\n+待問：B",
            "invalid_patch",
            0,
            INITIAL_PLAN,
        ),
        (None, "@@\n+待問：A\n*** EOF", "invalid_patch", 0, INITIAL_PLAN),
        (None, "@@\n+待問：A\n+EOF", "invalid_patch", 0, INITIAL_PLAN),
        (None, "@@\n+待問：A\n+*** End of File", "invalid_patch", 0, INITIAL_PLAN),
        (
            INITIAL_PLAN,
            "@@ EOF\n-釐清盤點中，本人負責的分工與交接。\n+轉談帶教。",
            "patch_context_not_found",
            1,
            UPDATED_PLAN,
        ),
    ],
    ids=["numbered_header", "abbreviated_eof", "added_eof", "prefixed_eof", "wrong_anchor"],
)
async def test_format_or_wrong_anchor_feedback_gives_an_executable_correction(
    body: str | None, diff: str, code: str, example_index: int, expected: str
) -> None:
    tools, workflow = tools_for(body)
    rejected = await tools.prepare("edit_interview_plan", json.dumps({"diff": diff}), uuid4())
    assert isinstance(rejected, str)
    feedback = json.loads(rejected)
    assert feedback["code"] == code
    assert workflow.snapshot.body == body
    assert workflow.saved == []
    if "+*** End of File" in diff:
        assert "+*** End of File" in feedback["next_action"]
    examples = re.findall(r"```diff\n(.*?)\n```", feedback["next_action"], re.DOTALL)
    assert len(examples) == 2, "Rejected edits need canonical examples, not only reread advice"

    corrected = await tools.prepare(
        "edit_interview_plan", json.dumps({"diff": examples[example_index]}), uuid4()
    )
    assert isinstance(corrected, dict)
    assert corrected["change"]["next_plan"] == expected


@pytest.mark.parametrize("body", [None, "", " \r\n原文\r\n"])
async def test_read_returns_exact_nullable_body_and_rejects_extra_arguments(
    body: str | None,
) -> None:
    tools, workflow = tools_for(body)
    assert json.loads(await tools.invoke("read_interview_plan", "{}")) == {"plan": body}
    rejected = json.loads(await tools.invoke("read_interview_plan", '{"scope":"invented"}'))
    assert rejected["code"] == "invalid_arguments"
    assert workflow.saved == []


@pytest.mark.parametrize("body", [None, ""])
async def test_empty_eof_noop_keeps_original_nullable_value_and_saves_unchanged(
    body: str | None,
) -> None:
    tools, workflow = tools_for(body)
    operation_id = uuid4()
    prepared = await tools.prepare(
        "edit_interview_plan", json.dumps({"diff": "@@\n+\n*** End of File"}), operation_id
    )
    assert isinstance(prepared, dict)
    assert workflow.saved == []
    change = prepared["change"]
    assert change["operation_id"] == str(operation_id)
    assert change["next_plan"] == body
    assert json.loads(change["result_text"]) == {"status": "unchanged"}
    assert await tools.execute(json.loads(json.dumps(prepared))) == change["result_text"]
    assert workflow.saved[0].next_plan == body


async def test_fuzzy_patch_returns_complete_actual_diff_and_preserves_untouched_context() -> None:
    body = "## 範圍\r\n  本人每月核對訂單與付款紀錄。\r\n待問交付\r\n"
    requested = "@@\n ## 範圍\n-本人每月核對訂單與付欵紀錄。\n+本人每週核對訂單與付款紀錄。"
    tools, workflow = tools_for(body)
    prepared = await tools.prepare("edit_interview_plan", json.dumps({"diff": requested}), uuid4())
    assert isinstance(prepared, dict)
    change = prepared["change"]
    after = "## 範圍\r\n本人每週核對訂單與付款紀錄。\r\n待問交付\r\n"
    assert change["next_plan"] == after
    result = json.loads(change["result_text"])
    assert result == {"status": "updated", "diff": describe_body_change(body, after)}
    assert result["diff"] != requested
    assert workflow.saved == []


@pytest.mark.parametrize(
    ("body", "diff", "expected"),
    [
        (None, "@@\n+筆記\n*** End of File", "筆記"),
        ("筆記", "@@\n-筆記\n*** End of File", ""),
    ],
)
async def test_create_and_deliberate_clear_are_complete_prepared_effects(
    body: str | None, diff: str, expected: str
) -> None:
    tools, _ = tools_for(body)
    prepared = await tools.prepare("edit_interview_plan", json.dumps({"diff": diff}), uuid4())
    assert isinstance(prepared, dict)
    assert prepared["change"]["next_plan"] == expected
    assert json.loads(prepared["change"]["result_text"])["status"] == "updated"


@pytest.mark.parametrize(
    ("diff", "code"),
    [
        ("@@\n-不存在\n+修正", "patch_context_not_found"),
        ("@@\n-重複\n+修正", "ambiguous_patch_context"),
        ("@@\n-原文\n+修正\n*** End Patch\n-垃圾", "invalid_patch"),
    ],
)
async def test_failed_patch_returns_rejection_without_any_write(diff: str, code: str) -> None:
    tools, workflow = tools_for("原文\n重複\n重複\n")
    result = await tools.prepare("edit_interview_plan", json.dumps({"diff": diff}), uuid4())
    assert isinstance(result, str)
    assert json.loads(result)["code"] == code
    assert workflow.saved == []


async def test_capacity_is_checked_on_serialized_result_before_save_without_truncation() -> None:
    tools, workflow = tools_for(None, max_result_characters=1)
    result = await tools.prepare(
        "edit_interview_plan", '{"diff":"@@\\n+筆記\\n*** End of File"}', uuid4()
    )
    assert isinstance(result, str)
    assert json.loads(result)["code"] == "write_result_limit_exceeded"
    assert (
        json.loads(await tools.invoke("read_interview_plan", "{}"))["code"] == "read_limit_exceeded"
    )
    assert workflow.saved == []


async def test_execute_replays_original_serialized_output_with_smaller_current_limits() -> None:
    tools, workflow = tools_for(None)
    prepared = await tools.prepare(
        "edit_interview_plan", '{"diff":"@@\\n+筆記\\n*** End of File"}', uuid4()
    )
    assert isinstance(prepared, dict)
    result = prepared["change"]["result_text"]
    smaller = InterviewPlanTools(
        workflow,
        tools.writer,
        policy=BodyMatchPolicy(max_body_characters=1),
        max_result_characters=1,
    )
    assert await smaller.execute(json.loads(json.dumps(prepared))) == result
    assert workflow.saved[0].next_plan == "筆記"


async def test_saved_null_cannot_be_repaired_from_a_missing_command_field() -> None:
    tools, workflow = tools_for(None)
    prepared = await tools.prepare(
        "edit_interview_plan", '{"diff":"@@\\n+\\n*** End of File"}', uuid4()
    )
    assert isinstance(prepared, dict)
    del prepared["change"]["next_plan"]
    with pytest.raises(ValidationError):
        await tools.execute(prepared)
    assert workflow.saved == []


async def test_saved_command_for_another_execution_is_rejected_before_save() -> None:
    tools, workflow = tools_for(None)
    prepared = await tools.prepare(
        "edit_interview_plan", '{"diff":"@@\\n+筆記\\n*** End of File"}', uuid4()
    )
    assert isinstance(prepared, dict)
    prepared["change"]["position"]["execution_id"] = str(uuid4())
    with pytest.raises(ValueError, match="another execution"):
        await tools.execute(prepared)
    assert workflow.saved == []


@pytest.mark.parametrize("version", [True, 1.0])
async def test_saved_command_does_not_repair_a_non_integer_version(version: object) -> None:
    tools, workflow = tools_for(None)
    prepared = await tools.prepare(
        "edit_interview_plan", '{"diff":"@@\\n+筆記\\n*** End of File"}', uuid4()
    )
    assert isinstance(prepared, dict)
    prepared["version"] = version
    with pytest.raises(ValueError, match="complete original command"):
        await tools.execute(prepared)
    assert workflow.saved == []
