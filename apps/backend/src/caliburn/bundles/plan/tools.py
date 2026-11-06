"""模型參數與可修正拒絕；版本及 Workspace 只從可信 Runtime 取得。"""

import asyncio
import json
from typing import Annotated, TypedDict

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool, ToolException
from langgraph.func import task
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from pydantic.v1 import ValidationError as ValidationErrorV1

from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.bundles.plan.state import PlanToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.plan.application.errors import PlanConcurrencyError
from caliburn.modules.plan.application.plans import patch_plan
from caliburn.modules.plan.domain.errors import BodyEditError, InvalidPlanTextError

_DIFF_GUIDANCE = """正文 V4A；輸入與修改後正文各最多 16,000 字元，最多 32 個 hunk。
每個 hunk 以獨立一行 @@ 開始；正文行以 + 新增、- 刪除、一個空白保留上下文。
各 hunk 按原文先後排列，全部對同一份原文定位。
不要數字行號、檔名、檔案 wrapper 或 Markdown 圍欄。刪除行及上下文須對應目前正文；
Markdown 清單的刪除行以 -- 開頭，新增行以 +- 開頭。保留未受影響方向與未知。
以下為解碼後的實際換行；請換成目前計畫的真實內容。
空正文建立（結尾控制行 *** End of File 不帶前綴）：
@@
+## 目前焦點
+釐清盤點中，本人負責的分工與交接。
+
+## 工作方向
+- 收貨：日常流程已入稿；特殊條件尚未探索。
+- 盤點：本人分工與交接尚未釐清。
+- 新人帶教：已知有這項工作，尚未深入本人範圍。
*** End of File
局部修改：
@@
 ## 目前焦點
-釐清盤點中，本人負責的分工與交接。
+釐清新人帶教中，本人負責的判斷與交接。
@@
-- 盤點：本人分工與交接尚未釐清。
+- 盤點：本人分工與交接已清楚，待整理進 JD 並核對相關職責與目的。"""

_PATCH_REPAIRS = {
    "invalid_patch": ("diff 不是有效正文 V4A。", "依 diff 欄位格式修正後重試。"),
    "patch_context_not_found": (
        "找不到指定的正文上下文。",
        "以 read_interview_plan 讀取目前正文，核對真實上下文，"
        "並將各 hunk 按原文先後排列。",
    ),
    "ambiguous_patch_context": (
        "正文有多個可匹配位置。",
        "增加目標附近的真實上下文，直到能唯一定位。",
    ),
    "patch_limit_exceeded": (
        "本次修改超過文字、hunk 或比對容量。",
        "縮小修改範圍與正文，並使用較少且可唯一定位的上下文。",
    ),
}


class _SavedEdit(TypedDict):
    version: int
    content: str


def _rejection(code: str, message: str, next_action: str) -> str:
    return json.dumps(
        {
            "status": "rejected",
            "code": code,
            "message": message,
            "next_action": next_action,
        },
        ensure_ascii=False,
    )


def _result(content: str, *, version: int, call_id: str | None) -> Command[object]:
    assert call_id is not None
    return Command(
        update={
            "plan_version": version,
            "messages": [ToolMessage(content=content, tool_call_id=call_id)],
        }
    )


async def read_interview_plan(
    runtime: ToolRuntime[AgentContext, PlanToolState],
) -> Command[object]:
    """讀取目前完整 Markdown 工作計畫，供補回正文或確認目前內容時使用。

    預載 consultant_interview_plan 的 plan、讀回的 plan 與 edit_interview_plan
    修改的是同一份計畫。回傳 plan 表示這次讀取時的正文；
    null 為尚無正文，空字串為空正文，皆不表示沒有未完工作。
    """
    queries = runtime.context.services.require(PLAN_QUERIES)
    plan = await asyncio.to_thread(
        queries.get_current, workspace_id=runtime.state["workspace_id"]
    )
    assert plan.version is not None
    return _result(
        json.dumps({"plan": plan.body}, ensure_ascii=False),
        version=plan.version,
        call_id=runtime.tool_call_id,
    )


async def edit_interview_plan(
    diff: Annotated[
        str,
        Field(strict=True, min_length=1, max_length=16_000, description=_DIFF_GUIDANCE),
    ],
    runtime: ToolRuntime[AgentContext, PlanToolState],
) -> Command[object]:
    """以正文 V4A diff 修改目前工作計畫；整份修改全成或全拒。

    以已提供的計畫、read_interview_plan 正文及後續成功 diff 為基底；
    null 或空字串可按空正文建立。
    updated 表示本次修改已保存，回傳實際 unified diff（不可原樣作下次 V4A 輸入）；
    unchanged 表示本次正文未變。後續依修改後內容接續並回報，
    需要完整目前正文時呼叫 read_interview_plan。
    """
    expected_version = runtime.state["plan_version"]
    if expected_version is None:
        raise ToolException(
            _rejection(
                "source_not_available",
                "尚未提供可供修改的工作計畫。",
                "先呼叫 read_interview_plan，再依取得的正文修改。",
            )
        )
    uow_factory = runtime.context.services.require(PLAN_UOW_FACTORY)

    @task
    def save_plan() -> _SavedEdit:
        result = patch_plan(
            workspace_id=runtime.state["workspace_id"],
            expected_version=expected_version,
            diff=diff,
            uow_factory=uow_factory,
        )
        assert result.plan.version is not None
        output = (
            {"status": "updated", "diff": result.diff}
            if result.changed
            else {"status": "unchanged"}
        )
        return {
            "version": result.plan.version,
            "content": json.dumps(output, ensure_ascii=False),
        }

    try:
        saved = await save_plan()
    except PlanConcurrencyError as error:
        raise ToolException(
            _rejection(
                "target_stale",
                "工作計畫已變動或本次並行修改遭拒絕。",
                "呼叫 read_interview_plan 重新讀取，再依目前正文決定修改。",
            )
        ) from error
    except BodyEditError as error:
        message, repair = _PATCH_REPAIRS[error.code]
        if error.hunk_number is not None:
            message = f"第 {error.hunk_number} 段：{message}"
        if error.candidates:
            locations = "、".join(
                f"{match.start_line}–{match.end_line}" for match in error.candidates[:3]
            )
            message += f"匹配行位置：{locations}。"
        raise ToolException(_rejection(error.code, message, repair)) from error
    except InvalidPlanTextError as error:
        raise ToolException(
            _rejection(
                "invalid_patch",
                "diff 含無法保存的文字字元。",
                "移除 NUL 或孤立 surrogate，保留正文內容後重試。",
            )
        ) from error
    return _result(
        saved["content"], version=saved["version"], call_id=runtime.tool_call_id
    )


def _validation_error(error: ValidationError | ValidationErrorV1) -> str:
    return _rejection(
        "invalid_arguments",
        "工具參數不符合格式。",
        "read_interview_plan 傳 {}；edit_interview_plan 只傳 diff，"
        "須為 1–16,000 字元的正文 V4A。",
    )


def create_plan_tools() -> tuple[StructuredTool, ...]:
    tools = []
    for handler in (read_interview_plan, edit_interview_plan):
        tool = StructuredTool.from_function(
            coroutine=handler,
            handle_tool_error=True,
            handle_validation_error=_validation_error,
        )
        schema = tool.get_input_schema()
        assert issubclass(schema, BaseModel)
        tool.args_schema = create_model(
            schema.__name__,
            __base__=schema,
            __config__=ConfigDict(extra="forbid"),
        )
        tools.append(tool)
    return tuple(tools)
