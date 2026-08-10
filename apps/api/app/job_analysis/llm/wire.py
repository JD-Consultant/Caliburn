"""`task_analysis_result.v2`:送給模型的**精簡輸出契約**。

domain 的 `TaskAnalysisResult`(`result.py`)是內部真相,這一份是**送出去的形狀**。
兩者分開的理由記在
`docs/specs/2026-07-31-context-engineering-model-facing-contract-research.md`:

1. Pydantic 直出會把開發者註解、內部規格章節號與自動生成的 `title` 一起送給模型
   ——量到佔 schema 的 27.4%,對模型零資訊量。
2. Anthropic 的 strict grammar 編譯器對 union／巢狀的預算遠小於 schema 的表達力;
   v1 的 17 個 nullable union(其中 8 個來自 `TaskFields` 被 inline 兩次)撞上
   `compiled grammar is too large`。

**這裡沒有任何 nullable union。** 可選以中性值表達:字串 `""`、enum `"none"`、
`resolves_open_issue_ordinal` 用 `0`。還原由 `wire_to_task_analysis_result()` 負責。

三件事刻意**不做**:

- **不做跨欄位驗證。** 「哪個欄位該非空」全部留給 deterministic verifier;
  結構合法但語意違規的輸出必須 parse 得出來,才可能被拒得出理由。
- **不寫 class docstring。** Pydantic 會把它變成 schema 的 `description` 送給模型;
  給開發者的說明一律用 `#` 註解,`description` 只承載中性值約定。
- **不放 `limitations`／`next_question.purpose`／三個 hint 欄位。** 前兩者全 repo
  零消費者;三個 hint 的唯一消費者是下一回合的 packet 自己。domain 欄位保留,
  OPKS 開工時再設計它自己的取得路徑。

名稱用 `task_analysis_result_v3`:模型看到的仍是「Task 分析結果」這個語意,
版號說明送出去的形狀換了一版;domain 契約沒有跟著改版。

v3 相對 v2 只加一件事:與 `work_signals` 平行的 `issue_resolutions[]`(ADR 0054
決定 22)。**新增一個必填的頂層陣列已經改變模型看到的輸出形狀,所以升版而不是覆寫
v2** ——同一個版本號指向兩種契約,凍結的 golden 就失去意義。

**名稱只能用 `[A-Za-z0-9_-]`。** 這是 provider 的硬限制,不是風格:OpenAI 對
`text.format.name` 就是這條 regex,帶點的 `…​.v2` 會在生成任何 token 之前被 HTTP 400
擋掉(2026-07-31 實測 `openai/gpt-5.6-luna-pro`)。Journal 的 payload schema id 是**另一個
namespace**,那邊的點狀慣例不適用於送給 provider 的 label。`test_job_analysis_wire_schema`
有一條測試守著這件事——別為了對齊檔名慣例把點加回來,那等於把契約鎖回單一 vendor。
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field, ValidationError

from app.core.domain import (
    DomainModel,
    Enabler,
    EnablerKind,
    ExclusionReason,
    OpenIssueKind,
    RetirementReason,
    TaskFields,
)

from app.core.portable_schema import compact_strict_output_schema

from .result import (
    ExcludePayload,
    IdentityAssessment,
    IdentityRelation,
    IssueResolution,
    IssueResolutionKind,
    NextQuestion,
    NextQuestionTarget,
    NextQuestionTargetKind,
    OpenIssuePayload,
    SignalAnchor,
    SignalDisposition,
    SplitChildPayload,
    SupportOrdinalRef,
    TaskAnalysisResult,
    TaskChangeKind,
    TaskChangePayload,
    WorkSignal,
)


TASK_ANALYSIS_WIRE_SCHEMA_NAME = "task_analysis_result_v3"

#: 所有「這一格不適用」的中性值。不得與任何 domain enum 值相同。
NEUTRAL = "none"


# ── enum:domain 值域 ＋ 一個中性值 ────────────────────────────────────────
#
# 值一律照抄 domain,不另立第二套;`tests/test_job_analysis_wire_schema.py`
# 逐一比對,漂開就紅。


class WireTaskChange(StrEnum):
    NONE = NEUTRAL
    ADD = "add"
    REVISE = "revise"
    WITHDRAW = "withdraw"
    MERGE = "merge"
    SPLIT = "split"


class WireWithdrawReason(StrEnum):
    NONE = NEUTRAL
    OTHER_PERSON = "other_person"
    PAST_WORK = "past_work"
    ONE_OFF = "one_off"
    ENABLER_OR_STEP = "enabler_or_step"
    EMPLOYEE_DENIED = "employee_denied"


# exclude 與 open_issue 的 payload 同構(理由 ＋ 摘要),合併成一格;
# `disposition` 決定 mapper 放進哪一個 payload,不由值本身推斷。
class WireRejectionCode(StrEnum):
    NONE = NEUTRAL
    # disposition=exclude 的值域(domain `ExclusionReason`)
    OTHER_PERSON_WORK = "他人工作"
    PAST_WORK = "過去工作"
    ONE_OFF_SUPPORT = "一次性支援"
    ENABLER_OR_STEP = "工具或步驟"
    EMPLOYEE_DENIED = "員工否認"
    # disposition=open_issue 的值域(domain `OpenIssueKind`)
    RESPONSIBILITY_UNCLEAR = "責任邊界不明"
    INSUFFICIENT_EVIDENCE = "證據不足"
    UNRESOLVED_CONTRADICTION = "矛盾未解"
    TASK_BOUNDARY_UNCERTAIN = "task_boundary_uncertain"


class WireNextQuestionTargetKind(StrEnum):
    NONE = NEUTRAL
    EXISTING_OPEN_ISSUE = "existing_open_issue"
    NEW_SIGNAL = "new_signal"


# ── 形狀 ───────────────────────────────────────────────────────────────────
#
# 字串一律 `str` 而非 `NonEmptyText`:`""` 是合法的中性值。非空要求由 mapper
# 建 domain 物件時執行,違反就落 INVALID_OUTPUT。


class WireEnabler(DomainModel):
    kind: EnablerKind
    name: str


class WireAnchor(DomainModel):
    turn_ordinal: int
    quote: str


class WireSupersession(DomainModel):
    task_ordinal: int
    support_ordinal: int


class WireTaskFields(DomainModel):
    statement: str
    action: str
    object: str
    purpose_result: str = Field(default="", description='說不出來就填 ""')
    enablers: tuple[WireEnabler, ...] = ()


# split 的 child 只帶足以成立一句話的語意欄位。v1 在這裡放整份 `TaskFields`,
# 光這一項就吃掉 17 個 union 中的 8 個並多推 2 層巢狀;其餘欄位後續回合以 revise 補。
class WireSplitChild(DomainModel):
    statement: str
    action: str
    object: str
    inherited_support_ordinals: tuple[int, ...] = ()


# v1 的三個 nullable payload 插槽在這裡攤平成同一層欄位,由 `disposition` 與
# `change` 決定哪些格子有內容。
class WireSignal(DomainModel):
    anchors: tuple[WireAnchor, ...] = ()
    relation: IdentityRelation = Field(
        description=(
            "必須與 change 一致:add→no_match、revise／merge→overlap、"
            "純補依據(change 與 rejection 皆 none)→duplicate;"
            "withdraw／split／exclude／open_issue 不限"
        )
    )
    target_task_ordinals: tuple[int, ...] = Field(
        default=(),
        description=(
            "identity 與變更共用同一批,只能指 current_authorities.tasks 的編號。"
            "數量:add 0 個、revise／withdraw／split 各 1 個、merge 至少 2 個"
        ),
    )
    supersedes: tuple[WireSupersession, ...] = Field(
        default=(),
        description=(
            "只在本回合更正了某條既有依據時填;該依據要屬於本訊號的 target Task "
            "且目前標示為有效,而且 anchors 必須包含目前這一輪的員工回合"
        ),
    )
    resolves_open_issue_ordinal: int = Field(
        default=0,
        description=(
            "0 表示不填。指本輪回答已經解掉、可以關閉的 open issue,anchors 必須含這一輪的"
            "員工回合。帶「Current JD Task」那一行的 issue 另有規則:只能用 no_match ＋ add "
            "或 exclude 關閉。不確定性仍在就別關,改輸出新的 open_issue"
        ),
    )
    disposition: SignalDisposition = Field(
        description=(
            "選 task_change 等於宣告四項成立條件都滿足,尤其「是本人目前的責任」;"
            "責任歸屬或 outcome 判不出來就選 open_issue 追問,不先建 Task 再撤回"
        )
    )
    change: WireTaskChange = Field(
        default=WireTaskChange.NONE, description='"none" 表示這個訊號不是 Task 變更'
    )
    withdraw_reason: WireWithdrawReason = Field(
        default=WireWithdrawReason.NONE,
        description='僅 change=withdraw 時填,否則 "none"',
    )
    task: WireTaskFields = Field(
        description='add／revise／merge 必填;withdraw 不得填;其餘各欄填 ""'
    )
    split_children: tuple[WireSplitChild, ...] = Field(
        default=(),
        description=(
            "僅 change=split 時填,至少兩個;inherited_support_ordinals 只能用母 Task "
            "標示為有效的 support 編號"
        ),
    )
    rejection_code: WireRejectionCode = Field(
        default=WireRejectionCode.NONE,
        description='disposition 為 exclude 或 open_issue 時填對應值,否則 "none"',
    )
    rejection_summary: str = Field(
        default="", description='搭配 rejection_code;否則 ""'
    )


class WireNextQuestion(DomainModel):
    text: str
    target_kind: WireNextQuestionTargetKind = Field(
        default=WireNextQuestionTargetKind.NONE, description='"none" 表示不指向任何東西'
    )
    # sentinel 由 `target_kind` 承載而非數值 —— 見下面「1 起算」的理由。
    #
    # **這份契約裡每一個數字都從 1 起算,沒有例外。** v2 剛上線時這一格對
    # `new_signal` 要求 0-based 索引,名字卻叫 ordinal;真模型因此在兩次相同場景下
    # 分別送出 2 與 3 來指同一個訊號(run 20260731T120931Z / 20260731T121651Z),
    # 前者僥倖落在範圍內、後者被 verifier 擋下。改成一致的 1-based 之後,
    # 「ordinal 都從 1 起算」是可學習的規則,不再需要靠 description 講例外。
    # 0-based 的 `NextQuestionTarget.index` 由 mapper 換算,不外洩給模型。
    target_ordinal: int = Field(
        default=0,
        description=(
            "從 1 起算。existing_open_issue 時為 packet 的 open issue ordinal;"
            "new_signal 時為本次 work_signals 的第幾個"
        ),
    )


# 與 work_signals 平行的第三個頂層陣列(ADR 0054 決定 22)。扁平、每 issue 一筆、
# 零 union——結構上不可能夾帶工作副作用。
#
# 什麼時候該用哪一個值住 `TASK_ANALYSIS_INSTRUCTIONS`,不住這裡:schema 的
# `description` 只承載中性值約定(見本檔開頭第 2 點與 wire schema 的描述預算)。
class WireIssueResolution(DomainModel):
    # 欄位名自己說出是哪一組 ordinal(沿用 `resolves_open_issue_ordinal` 的慣例),
    # 因此不必花 description 預算去講一件名字講得完的事。
    open_issue_ordinal: int
    resolution: IssueResolutionKind


class TaskAnalysisWire(DomainModel):
    work_signals: tuple[WireSignal, ...] = ()
    issue_resolutions: tuple[WireIssueResolution, ...] = ()
    next_question: WireNextQuestion


# ── 還原成 domain 契約 ─────────────────────────────────────────────────────


class WireMappingError(ValueError):
    """wire 輸出還原不成 domain 契約。呼叫端當成 `INVALID_OUTPUT`。"""


_EXCLUSION_CODES = {member.value for member in ExclusionReason}
_OPEN_ISSUE_CODES = {member.value for member in OpenIssueKind}


def wire_to_task_analysis_result(wire: TaskAnalysisWire) -> TaskAnalysisResult:
    """純還原:中性值 → `None`,其餘照抄。

    這裡**不做**任何跨欄位判斷。「disposition 與 payload 對不對得上」「withdraw 該不該
    帶 reason」全部是 verifier 的工作(§12.3),在這裡「順手修正」等於讓那些
    violation code 永遠不會觸發。

    唯一會失敗的情形是**模型在沒有 domain 落點的欄位夾帶內容**——例如 `change` 是
    `"none"`(沒有 `TaskChangePayload` 可放)卻填了 `task.statement`。靜默丟棄會讓
    模型真正說出口的東西消失,所以整回合失敗。
    """

    try:
        return TaskAnalysisResult(
            work_signals=tuple(_signal(signal) for signal in wire.work_signals),
            issue_resolutions=tuple(
                IssueResolution(
                    ordinal=resolution.open_issue_ordinal,
                    resolution=resolution.resolution,
                )
                for resolution in wire.issue_resolutions
            ),
            next_question=_next_question(wire.next_question),
        )
    except ValidationError as error:
        raise WireMappingError(
            f"wire output could not be mapped: {error.error_count()} error(s)"
        ) from error


def _signal(signal: WireSignal) -> WorkSignal:
    change = (
        None
        if signal.change is WireTaskChange.NONE
        else TaskChangeKind(signal.change.value)
    )
    if change is None:
        _reject_change_content_without_a_slot(signal)
    if signal.rejection_code is WireRejectionCode.NONE and signal.rejection_summary:
        raise WireMappingError(
            'rejection_summary was filled while rejection_code is "none"'
        )

    return WorkSignal(
        anchors=tuple(
            SignalAnchor(turn_ordinal=anchor.turn_ordinal, quote=anchor.quote)
            for anchor in signal.anchors
        ),
        identity=IdentityAssessment(
            relation=signal.relation,
            target_task_ordinals=signal.target_task_ordinals,
        ),
        supersedes_support_ordinals=tuple(
            SupportOrdinalRef(
                task_ordinal=ref.task_ordinal, support_ordinal=ref.support_ordinal
            )
            for ref in signal.supersedes
        ),
        resolves_open_issue_ordinal=signal.resolves_open_issue_ordinal or None,
        disposition=signal.disposition,
        task_change=None if change is None else _task_change(signal, change),
        exclude=_exclude(signal),
        open_issue=_open_issue(signal),
    )


def _reject_change_content_without_a_slot(signal: WireSignal) -> None:
    if not _is_neutral(signal.task):
        raise WireMappingError('task fields were filled while change is "none"')
    if signal.split_children:
        raise WireMappingError('split_children were filled while change is "none"')
    if signal.withdraw_reason is not WireWithdrawReason.NONE:
        raise WireMappingError('withdraw_reason was filled while change is "none"')


def _is_neutral(task: WireTaskFields) -> bool:
    return not any(
        (task.statement, task.action, task.object, task.purpose_result, task.enablers)
    )


def _task_change(signal: WireSignal, change: TaskChangeKind) -> TaskChangePayload:
    return TaskChangePayload(
        change=change,
        withdraw_reason=(
            None
            if signal.withdraw_reason is WireWithdrawReason.NONE
            else RetirementReason(signal.withdraw_reason.value)
        ),
        target_task_ordinals=signal.target_task_ordinals,
        task_fields=None if _is_neutral(signal.task) else _task_fields(signal.task),
        split_children=tuple(_split_child(child) for child in signal.split_children),
    )


def _task_fields(task: WireTaskFields) -> TaskFields:
    # `context` 不在每回合重寫；既有 domain 值由 revise 的 identity 流程保留。
    return TaskFields(
        statement=task.statement,
        action=task.action,
        object=task.object,
        purpose_result=task.purpose_result or None,
        enablers=tuple(
            Enabler(kind=enabler.kind, name=enabler.name) for enabler in task.enablers
        ),
    )


def _split_child(child: WireSplitChild) -> SplitChildPayload:
    return SplitChildPayload(
        task_fields=TaskFields(
            statement=child.statement, action=child.action, object=child.object
        ),
        inherited_support_ordinals=child.inherited_support_ordinals,
    )


def _exclude(signal: WireSignal) -> ExcludePayload | None:
    # 落點由**值**決定,不由 `disposition` 決定:兩個值域互斥,而讓 disposition 決定
    # 等於在 mapper 裡做語意判斷,並吃掉 `PAYLOAD_DOES_NOT_MATCH_DISPOSITION`。
    if signal.rejection_code.value not in _EXCLUSION_CODES:
        return None
    return ExcludePayload(
        reason=ExclusionReason(signal.rejection_code.value),
        summary=signal.rejection_summary,
    )


def _open_issue(signal: WireSignal) -> OpenIssuePayload | None:
    if signal.rejection_code.value not in _OPEN_ISSUE_CODES:
        return None
    return OpenIssuePayload(
        kind=OpenIssueKind(signal.rejection_code.value),
        summary=signal.rejection_summary,
    )


def _next_question(question: WireNextQuestion) -> NextQuestion:
    kind = question.target_kind
    if kind is WireNextQuestionTargetKind.NONE:
        return NextQuestion(text=question.text, target=None)

    if question.target_ordinal < 1:
        raise WireMappingError(
            f"target_ordinal counts from 1, got {question.target_ordinal}"
        )
    if kind is WireNextQuestionTargetKind.EXISTING_OPEN_ISSUE:
        target = NextQuestionTarget(
            kind=NextQuestionTargetKind.EXISTING_OPEN_ISSUE,
            ordinal=question.target_ordinal,
        )
    else:
        # domain 的 `index` 是 0-based 位置;wire 一律 1-based,換算只發生在這裡。
        target = NextQuestionTarget(
            kind=NextQuestionTargetKind.NEW_SIGNAL, index=question.target_ordinal - 1
        )
    return NextQuestion(text=question.text, target=target)


# ── provider schema 與 golden ──────────────────────────────────────────────


WIRE_SCHEMA_PATH = (
    Path(__file__).parent / "schemas" / f"{TASK_ANALYSIS_WIRE_SCHEMA_NAME}.json"
)


def task_analysis_wire_provider_schema() -> dict[str, Any]:
    return compact_strict_output_schema(TaskAnalysisWire.model_json_schema())


def committed_wire_schema() -> dict[str, Any]:
    return json.loads(WIRE_SCHEMA_PATH.read_text(encoding="utf-8"))


def render_wire_schema_file() -> str:
    """Golden 的唯一渲染方式(換行固定 `\\n`,尾端一個換行)。"""

    return (
        json.dumps(
            task_analysis_wire_provider_schema(),
            ensure_ascii=False,
            indent=2,
            sort_keys=False,
        )
        + "\n"
    )
