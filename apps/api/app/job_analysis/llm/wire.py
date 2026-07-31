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

名稱用 `task_analysis_result.v2`:模型看到的仍是「Task 分析結果」這個語意,
版號說明送出去的形狀換了一版;domain 契約沒有跟著改版。
"""

from __future__ import annotations

import json
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import Field

from app.job_analysis.domain import DomainModel, EnablerKind

from .portable_schema import compact_strict_output_schema
from .result import IdentityRelation, SignalDisposition


TASK_ANALYSIS_WIRE_SCHEMA_NAME = "task_analysis_result.v2"

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
    relation: IdentityRelation
    target_task_ordinals: tuple[int, ...] = Field(
        default=(), description="identity 與變更共用同一批"
    )
    supersedes: tuple[WireSupersession, ...] = ()
    resolves_open_issue_ordinal: int = Field(
        default=0, description="0 表示沒有解決任何 open issue"
    )
    disposition: SignalDisposition
    change: WireTaskChange = Field(
        default=WireTaskChange.NONE, description='"none" 表示這個訊號不是 Task 變更'
    )
    withdraw_reason: WireWithdrawReason = Field(
        default=WireWithdrawReason.NONE,
        description='僅 change=withdraw 時填,否則 "none"',
    )
    task: WireTaskFields = Field(description='非 Task 變更時各欄填 ""')
    split_children: tuple[WireSplitChild, ...] = Field(
        default=(), description="僅 change=split 時填"
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
    # sentinel 由 `target_kind` 承載而非數值:`new_signal` 的索引可以是 0,
    # 用「0 表示無」會把合法值吃掉。
    target_ordinal: int = Field(
        default=0,
        description=(
            "existing_open_issue 時為 packet 的 open issue ordinal;"
            "new_signal 時為本次 work_signals 的索引"
        ),
    )


class TaskAnalysisWire(DomainModel):
    work_signals: tuple[WireSignal, ...] = ()
    next_question: WireNextQuestion


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
