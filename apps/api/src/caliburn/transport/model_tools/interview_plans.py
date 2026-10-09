"""App-bound plan reads and fully prepared V4A writes at the existing Step boundary."""

import json
from typing import TYPE_CHECKING, Literal, TypedDict
from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import ConfigDict, TypeAdapter, ValidationError, with_config

from caliburn.adapters.body_edits import apply_body_diff, describe_body_change
from caliburn.adapters.body_matching import BodyEditError, BodyMatchPolicy
from caliburn.contracts.generated.tools.edit_interview_plan_arguments import (
    EditInterviewPlanArguments,
)
from caliburn.contracts.generated.tools.interview_plan import InterviewPlan
from caliburn.contracts.generated.tools.interview_plan_write_result import (
    InterviewPlanUnchanged,
    InterviewPlanUpdated,
)
from caliburn.contracts.generated.tools.read_interview_plan_arguments import (
    ReadInterviewPlanArguments,
)
from caliburn.contracts.validation import parse_contract
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionStateError,
    ExecutionWriter,
)
from caliburn.features.interview_plans.models import (
    PlanConflictError,
    PlanEdit,
    PlanSnapshot,
    PlanStateError,
    StalePlanPositionError,
)
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call

if TYPE_CHECKING:
    from caliburn.workflows.interview_plans import InterviewPlanWorkflow


@with_config(ConfigDict(strict=True, extra="forbid"))
class _PreparedPlanEdit(TypedDict):
    kind: Literal["interview_plan_edit"]
    version: Literal[1]
    change: PlanEdit


_PREPARED_PLAN_EDIT = TypeAdapter(_PreparedPlanEdit)
_JSON_OBJECT = TypeAdapter(dict[str, object])
_PLAN_POLICY = BodyMatchPolicy(max_body_characters=16_000, max_diff_characters=16_000, max_hunks=32)
_EXPECTED_FAILURES = (ExecutionNotFoundError, ExecutionStateError, PlanStateError)
_BODY_DIFF_GUIDANCE = (
    "\n格式是正文 V4A：正文內容行以 + 新增、- 刪除、一個空白保留原文上下文。"
    "@@ 與 *** End of File 是控制行，不帶任何 +、- 或空白前綴；用單獨一行 @@ 開始 hunk，"
    "空計畫建立以單獨一行 *** End of File 結尾。不要數字行號的 @@ -1,2 +1,2 @@、"
    "檔名或檔案 wrapper；不是 @@ EOF、*** EOF、+EOF 或 +*** End of File。"
    "替換時 - 行及空白行須對應目前正文；Markdown 清單的刪除行以 -- 開頭，新增行以 +- 開頭。"
    "未受影響方向與未知保持原樣。"
    "下方是 diff 欄位解碼後的實際換行範例；傳入 diff 不包含 Markdown 圍欄，"
    "並將示意文字換成目前計畫的真實內容。以下假設已取得收貨、盤點與帶教線索。\n"
    "空計畫建立：\n```diff\n@@\n"
    "+## 目前焦點\n+釐清盤點中，本人負責的分工與交接。\n+\n+## 工作方向\n"
    "+- 收貨：日常流程已入稿；特殊條件尚未探索。\n"
    "+- 盤點：本人分工與交接尚未釐清。\n"
    "+  - 哪些情境適用這套處理方式仍未知；員工暫答不出，有新線索再談。\n"
    "+- 新人帶教：已知有這項工作，尚未深入本人範圍。\n"
    "+- 全稿核對：待主要方向整理後，核對遺漏、依據與跨欄一致。\n*** End of File\n```\n"
    "盤點分工已釐清，轉談帶教；保留待入稿工作、收貨與盤點適用範圍未知：\n```diff\n@@\n"
    " ## 目前焦點\n-釐清盤點中，本人負責的分工與交接。\n"
    "+釐清新人帶教中，本人負責的判斷與交接。\n@@\n"
    "-- 盤點：本人分工與交接尚未釐清。\n"
    "+- 盤點：本人分工與交接已清楚，待整理進 JD 並核對相關職責與目的。\n@@\n"
    "-- 新人帶教：已知有這項工作，尚未深入本人範圍。\n"
    "+- 新人帶教：正在深入本人範圍。\n```"
)


def interview_plan_definitions() -> list[FunctionToolParam]:
    """Advertise only model-owned text parameters; App coordinates remain private."""
    return [
        function_definition(
            "read_interview_plan",
            "按需讀目前完整 Markdown 工作計畫；null 尚未建立，空字串是刻意清空。"
            "已有全文及成功修改效果足以掌握目前範圍時，不必為確認重讀。"
            "內容供同一顧問安排方向、焦點與剩餘訪談／分析／JD 編修核對，不是員工事實或完成判定。",
            "read-interview-plan-arguments",
        ),
        function_definition(
            "edit_interview_plan",
            "有實質變動才用一份 V4A diff 合併相關修改，最多 16,000 字元、32 hunks。"
            "用同份 Markdown 維持目前焦點與工作方向，保留有範圍的進度、重要未完工作及必要線索。"
            "未知釐清後仍需入稿就改為待整理／核對，保住其他方向與精確未知；"
            "移除完成微步驟、過時及重複內容，不抄整份 Memory 或完成流水帳。"
            "空正文用明確 EOF 新增；成功回實際前後差異或 unchanged，差異不是下次 V4A 輸入。"
            "成功只保存本輪候選，不表示整輪採用或分析完成。" + _BODY_DIFF_GUIDANCE,
            "edit-interview-plan-arguments",
        ),
    ]


class InterviewPlanTools:
    read_names = ("read_interview_plan",)
    write_names = ("edit_interview_plan",)
    names = (*read_names, *write_names)

    def __init__(
        self,
        workflow: InterviewPlanWorkflow,
        writer: ExecutionWriter,
        *,
        policy: BodyMatchPolicy = _PLAN_POLICY,
        max_result_characters: int = 64_000,
    ) -> None:
        if writer.scope.kind != ExecutionKind.CONSULTANT_TURN:
            raise ExecutionStateError("Plan tools require a consultant Turn")
        if max_result_characters < 1:
            raise ValueError("Tool result character limit must be positive")
        self.workflow = workflow
        self.writer = writer
        self.policy = policy
        self.max_result_characters = max_result_characters

    def definitions(self) -> list[FunctionToolParam]:
        return interview_plan_definitions()

    async def invoke(self, name: str, arguments: str) -> str:
        if name not in self.read_names:
            return _scope_rejection()
        try:
            parse_contract(ReadInterviewPlanArguments, arguments)
        except ValidationError:
            return _invalid_arguments()
        try:
            snapshot = await self._read_current()
        except _EXPECTED_FAILURES as error:
            return _rejection(error)
        result = InterviewPlan(plan=snapshot.body).model_dump_json()
        if len(result) > self.max_result_characters:
            return reject_tool_call(
                "read_limit_exceeded",
                "完整工作計畫超過工具輸出容量，未回傳截斷內容。",
                "由 App 處理容量；不視為沒有未完工作或 JD 已完整。",
            )
        return result

    async def prepare(
        self, name: str, arguments: str, operation_id: UUID
    ) -> str | dict[str, object]:
        if name not in self.write_names:
            return _scope_rejection()
        try:
            intent = parse_contract(EditInterviewPlanArguments, arguments)
        except ValidationError:
            return _invalid_arguments()
        try:
            snapshot = await self._read_current()
            source = snapshot.body if snapshot.body is not None else ""
            revised = apply_body_diff(
                source, intent.diff, policy=self.policy, allow_blank_body=True
            )
        except BodyEditError as error:
            return _patch_rejection(error)
        except _EXPECTED_FAILURES as error:
            return _rejection(error)
        # A no-text-effect EOF edit must not turn an uncreated nullable plan into empty text.
        next_plan = snapshot.body if revised == source else revised
        if revised == source:
            output = InterviewPlanUnchanged(status="unchanged").model_dump_json()
        else:
            output = InterviewPlanUpdated(
                status="updated", diff=describe_body_change(source, revised)
            ).model_dump_json()
        if len(output) > self.max_result_characters:
            return reject_tool_call(
                "write_result_limit_exceeded",
                "完整效果回傳超過容量，本次未改。",
                "縮小同次修改；若需精簡正文先移除完成微步驟、過時與重複內容，保住主要範圍、"
                "重要未完工作及返回條件。不能截斷效果或先保存再宣稱拒絕。",
            )
        command = PlanEdit(operation_id, snapshot.position, intent.diff, next_plan, output)
        prepared: _PreparedPlanEdit = {
            "kind": "interview_plan_edit",
            "version": 1,
            "change": command,
        }
        return _JSON_OBJECT.validate_python(_PREPARED_PLAN_EDIT.dump_python(prepared, mode="json"))

    async def execute(self, prepared: object) -> str:
        """Apply only the exact saved command; uncertain persistence outcomes propagate."""
        original = json.dumps(prepared, sort_keys=True)
        saved = _PREPARED_PLAN_EDIT.validate_json(original, strict=True)
        restored = _PREPARED_PLAN_EDIT.dump_python(saved, mode="json")
        # JSON type equality is stricter than Python dict equality (True == 1 == 1.0).
        if json.dumps(restored, sort_keys=True) != original:
            raise ValueError("A saved plan edit must preserve its complete original command")
        change = saved["change"]
        if (change.position.job_file_id, change.position.execution_id) != (
            self.writer.scope.job_file_id,
            self.writer.scope.execution_id,
        ):
            raise ValueError("A saved plan edit belongs to another execution")
        try:
            result = await self.workflow.apply(self.writer, change)
        except _EXPECTED_FAILURES as error:
            return _rejection(error)
        # Reconciliation returns the original serialized result, including older output limits.
        return result.result_text

    async def _read_current(self) -> PlanSnapshot:
        snapshot = await self.workflow.read_current(self.writer.scope)
        if snapshot is None:
            raise PlanStateError("This bound Turn has no initialized plan candidate")
        if (snapshot.position.job_file_id, snapshot.position.execution_id) != (
            self.writer.scope.job_file_id,
            self.writer.scope.execution_id,
        ):
            raise PlanStateError("The candidate belongs to another execution")
        return snapshot


def _invalid_arguments() -> str:
    return reject_tool_call(
        "invalid_arguments",
        "工作計畫參數不合法，本次未讀寫。",
        "read 使用 {}；edit 只填非空、有界的 diff，不提供範圍、版本或保存結果。",
    )


def _scope_rejection() -> str:
    return reject_tool_call(
        "scope_not_allowed",
        "目前執行或角色不允許此工作計畫操作。",
        "使用 App 提供的工具與有效工作，不猜執行範圍。",
    )


def _rejection(error: Exception) -> str:
    if isinstance(error, ExecutionNotFoundError | ExecutionStateError):
        return _scope_rejection()
    if isinstance(error, PlanConflictError | StalePlanPositionError):
        return reject_tool_call(
            "target_stale",
            "原工作計畫位置或操作意圖已失效，本次未改。",
            "由 App 接續原操作或有效候選，不重送過時操作。",
        )
    return reject_tool_call(
        "source_not_available",
        "本輪工作計畫的保存資料無法完整使用。",
        "由 App 處理保存；不能把讀取失敗當成 null、空計畫或已完成。",
    )


def _patch_rejection(error: BodyEditError) -> str:
    message = str(error)
    if error.hunk_number is not None:
        message = f"Hunk {error.hunk_number}: {message}"
    for candidate in error.candidates:
        message += f"\n候選行 {candidate.start_line}–{candidate.end_line}:\n{candidate.excerpt}"
    next_action = (
        "重新讀目前全文並用真實完整行與足夠上下文；多處匹配不自動選取，超量請縮小修改。"
        "需精簡時先移除完成微步驟、過時與重複內容，保住主要範圍、重要未完工作及返回條件，"
        "不為容量捏造完成。"
    )
    if error.code in {"invalid_patch", "patch_context_not_found"}:
        next_action = (
            "依下方正文 V4A 範例更正 diff 並對應目前正文；已知全文時不必為格式重讀，"
            "來源不符時再讀。" + _BODY_DIFF_GUIDANCE
        )
    return reject_tool_call(
        error.code,
        message + "\n本次正文未改。",
        next_action,
    )
