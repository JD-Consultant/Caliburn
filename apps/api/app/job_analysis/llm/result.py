"""`TaskAnalysisResult`:一回合分析結果的**內部契約**(§12.1)。

**這不是送出去的形狀。** 模型看到的是 `wire.py` 的 `task_analysis_result.v2`,
還原由 `wire_to_task_analysis_result()` 負責;分開的理由見
`docs/specs/2026-07-31-context-engineering-model-facing-contract-research.md`。
verifier、transition 與下游一律吃這一份,不吃 wire。

兩件事在這裡刻意**不做**:

1. **不做任何跨欄位驗證。** disposition↔payload、ordinal 範圍、`merge` 至少兩個 target、
   `withdraw` 不得帶 `task_fields` 等等,全部屬 deterministic verifier(§12.3、T3)。
   模型送回結構合法但語意違規的輸出時,系統要能 parse 出來、由 verifier 給出明確的
   拒絕理由,而不是在 parse 階段變成一個看不出原因的 schema 失敗。
2. **不設整體 `analysis_decision` 欄位**(§12.1):本輪是提案、澄清還是不變更,由
   `work_signals` 推導。

模型永遠不產生 ID,只用 packet 給的 ordinal 與本次輸出內的位置索引(§12.1)。

四種 payload 在凍結文件裡是「依 disposition 擇一」的 union,這裡落成三個 nullable
兄弟欄位(`support_only` 沒有 payload,三者皆 null 即是它),`next_question.target`
的兩種 kind 同理落成 `ordinal`／`index`。「哪一個欄位該非 null」由 verifier 依
`disposition`／`kind` 檢查,不在這裡把不合的組合變成 parse 失敗。

`limitations` 與 `next_question.purpose` 已移除:全 repo 沒有任何消費者,留著只是每回合
向模型索取一次再丟掉。
"""

from __future__ import annotations

from enum import StrEnum

from app.job_analysis.domain import DomainModel, NonEmptyText
from app.job_analysis.domain.task import RetirementReason, TaskFields
from app.job_analysis.domain.work_model import ExclusionReason, OpenIssueKind


TASK_ANALYSIS_RESULT_SCHEMA_NAME = "task_analysis_result.v1"


class SignalAnchor(DomainModel):
    """指向 packet 中某個回合的逐字引用;application 再把 ordinal 解成 SourceRef。"""

    turn_ordinal: int
    quote: NonEmptyText


class IdentityRelation(StrEnum):
    NO_MATCH = "no_match"
    DUPLICATE = "duplicate"
    OVERLAP = "overlap"
    UNCERTAIN = "uncertain"


class IdentityAssessment(DomainModel):
    relation: IdentityRelation
    target_task_ordinals: tuple[int, ...] = ()


class SupportOrdinalRef(DomainModel):
    """指認被本次更正取代的既有依據(§12.3 末段:這是 `TI-R1-08` 的唯一支撐)。"""

    task_ordinal: int
    support_ordinal: int


class SignalDisposition(StrEnum):
    TASK_CHANGE = "task_change"
    SUPPORT_ONLY = "support_only"
    EXCLUDE = "exclude"
    OPEN_ISSUE = "open_issue"


class TaskChangeKind(StrEnum):
    ADD = "add"
    REVISE = "revise"
    WITHDRAW = "withdraw"
    MERGE = "merge"
    SPLIT = "split"


class SplitChildPayload(DomainModel):
    """Split 子項的語意欄位與要沿用的母 Task 依據。

    ordinal 是母 Task 內的 task-local support ordinal；application 會解析成
    ``SupportLink``。模型不接觸 SourceRef 或內部 ID。
    """

    task_fields: TaskFields
    inherited_support_ordinals: tuple[int, ...] = ()


class TaskChangePayload(DomainModel):
    change: TaskChangeKind
    withdraw_reason: RetirementReason | None = None
    """為什麼撤回;`withdraw` 必填,其他 change 不得帶(由 verifier 檢查)。

    §9.5 要求 `retirement.kind == withdrawn` 一定有 reason,而**只有模型知道是哪一種**:
    「那只是去年代班一次」是 `one_off`,不是 `employee_denied`。既有形狀沒有欄位能表達
    這個區別,application 只能猜——猜錯就把撤回理由寫成假的。沿用 domain 的
    `RetirementReason`,不另立第二套值域。
    """

    target_task_ordinals: tuple[int, ...] = ()
    task_fields: TaskFields | None = None
    split_children: tuple[SplitChildPayload, ...] = ()


class ExcludePayload(DomainModel):
    reason: ExclusionReason
    summary: NonEmptyText


class OpenIssuePayload(DomainModel):
    kind: OpenIssueKind
    summary: NonEmptyText


class WorkSignal(DomainModel):
    anchors: tuple[SignalAnchor, ...] = ()
    identity: IdentityAssessment
    supersedes_support_ordinals: tuple[SupportOrdinalRef, ...] = ()
    resolves_open_issue_ordinal: int | None = None
    disposition: SignalDisposition
    task_change: TaskChangePayload | None = None
    exclude: ExcludePayload | None = None
    open_issue: OpenIssuePayload | None = None


class NextQuestionTargetKind(StrEnum):
    EXISTING_OPEN_ISSUE = "existing_open_issue"
    NEW_SIGNAL = "new_signal"


class NextQuestionTarget(DomainModel):
    kind: NextQuestionTargetKind
    ordinal: int | None = None
    index: int | None = None


class NextQuestion(DomainModel):
    text: NonEmptyText
    target: NextQuestionTarget | None = None


class TaskAnalysisResult(DomainModel):
    work_signals: tuple[WorkSignal, ...] = ()
    next_question: NextQuestion
