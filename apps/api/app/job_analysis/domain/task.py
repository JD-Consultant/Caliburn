"""Task v1 凍結形狀(§9.1)與其推導狀態(§9.2)。"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from .base import DomainModel, NonEmptyText, TaskId
from .sources import SourceRef, SupportLink


class EnablerKind(StrEnum):
    TOOL_SYSTEM = "tool_system"
    METHOD = "method"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    OTHER = "other"


class Enabler(DomainModel):
    kind: EnablerKind
    name: NonEmptyText


class RetirementKind(StrEnum):
    WITHDRAWN = "withdrawn"
    MERGED = "merged"
    SPLIT = "split"


class RetirementReason(StrEnum):
    OTHER_PERSON = "other_person"
    PAST_WORK = "past_work"
    ONE_OFF = "one_off"
    ENABLER_OR_STEP = "enabler_or_step"
    EMPLOYEE_DENIED = "employee_denied"


class Retirement(DomainModel):
    kind: RetirementKind
    reason: RetirementReason | None = None
    source_ref: SourceRef

    @model_validator(mode="after")
    def reason_belongs_to_withdrawn_only(self):
        """§9.1:只有 ``kind == withdrawn`` 才有 reason;§9.5:此時 reason 必填。"""
        if self.kind is RetirementKind.WITHDRAWN:
            if self.reason is None:
                raise ValueError("withdrawn retirement requires a reason")
        elif self.reason is not None:
            raise ValueError(f"{self.kind.value} retirement must not carry a reason")
        return self


class TaskFields(DomainModel):
    """Task 的語意欄位子集。

    這一組就是 §12.1 的 ``task_fields``(模型可提出的欄位)與 §10.4 staged 新 Task 的
    語意欄位;`Task` 繼承它,讓三處共用同一份欄位權威,而不是各抄一份。
    """

    statement: NonEmptyText
    action: NonEmptyText
    object: NonEmptyText
    purpose_result: NonEmptyText | None = None
    context: NonEmptyText | None = None
    enablers: tuple[Enabler, ...] = ()


class TaskState(StrEnum):
    """§9.2 的推導狀態,不存成欄位。"""

    ACTIVE = "active"
    PENDING_RECONCILIATION = "pending_reconciliation"
    RETIRED = "retired"


class Task(TaskFields):
    task_id: TaskId
    support_links: tuple[SupportLink, ...] = ()
    retirement: Retirement | None = None
    merged_into: TaskId | None = None
    split_from: TaskId | None = None
    pending_reconciliation: SourceRef | None = None
    """觸發器與最近原因指標,不是待辦清單(§9.5)。

    三種 ``SourceKind`` 都可能合法,因此 domain 無從再收斂:`proposal_decision` 要再看
    該決定是 ``edited``／``rejected``(``deferred`` 不觸發)才算合法,而那需要 Proposal,
    不在單一 Task 的可見範圍內。
    """

    @property
    def state(self) -> TaskState:
        if self.retirement is not None:
            return TaskState.RETIRED
        if self.pending_reconciliation is not None:
            return TaskState.PENDING_RECONCILIATION
        return TaskState.ACTIVE

    @property
    def effective_support_links(self) -> tuple[SupportLink, ...]:
        return tuple(link for link in self.support_links if link.is_effective)

    @model_validator(mode="after")
    def merged_into_pairs_with_a_merged_retirement(self):
        """§9.5:``retirement.kind == merged`` → ``merged_into`` 必填,且只有它會有。

        反向也要鎖:`active` Task 帶著 `merged_into` 表示「已併入別人卻仍在線上」,
        兩邊都會被當成現況產生提案,員工看到同一件事出現兩次。
        """
        merged = (
            self.retirement is not None
            and self.retirement.kind is RetirementKind.MERGED
        )
        if merged and self.merged_into is None:
            raise ValueError("merged retirement requires merged_into")
        if self.merged_into is not None and not merged:
            raise ValueError("merged_into requires a merged retirement")
        return self

    @model_validator(mode="after")
    def retirement_and_pending_reconciliation_are_exclusive(self):
        """§9.2:兩者並存的 Task 沒有意義。

        `pending_reconciliation` 是「等著和 Current JD 重新對齊」的觸發器,retired 的
        Task 不會再被對齊;放任並存,推導狀態只會顯示 retired,那筆待對齊的來源就靜默
        消失——而它正是員工剛做的編輯或更正。
        """
        if self.retirement is not None and self.pending_reconciliation is not None:
            raise ValueError(
                "a retired task must not also be pending reconciliation"
            )
        return self

    @model_validator(mode="after")
    def lineage_is_not_self_referential(self):
        """§9.5 cycle 規則最短的一種;跨 Task 的環由 `CurrentWorkModel` 檢查。"""
        for field_name in ("merged_into", "split_from"):
            if getattr(self, field_name) == self.task_id:
                raise ValueError(f"{field_name} must not point at the task itself")
        return self

    @model_validator(mode="after")
    def active_task_keeps_one_effective_support(self):
        """§9.5:`active` Task 至少一條 ``superseded_by == null`` 的 SupportLink。

        寫成型別層不變量,「active 但零有效支持」就無法被表示;§9.5 的原子性三出口
        因此變成 application 必須挑一個出口,而不是可以忘記檢查的事後規則。
        """
        if self.state is TaskState.ACTIVE and not self.effective_support_links:
            raise ValueError("active task requires at least one effective support link")
        return self
