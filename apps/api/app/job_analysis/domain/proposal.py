"""Product Proposal v1 凍結形狀(§10)。

Proposal **只 gate Current JD**;Work Model 何時可直接更新見 §9.6,由 application
(T6)決定,不在本模組。
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import Field, model_validator

from .base import DomainModel, Identifier, NonEmptyText, TaskId
from .task import Retirement, RetirementKind, TaskFields


class ProposalAction(StrEnum):
    ADD = "add"
    REVISE = "revise"
    WITHDRAW = "withdraw"
    MERGE = "merge"
    SPLIT = "split"


class ProposalStatus(StrEnum):
    PENDING = "pending"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    STALE = "stale"


#: §10.1 的狀態機。terminal 狀態沒有出邊——包括 `stale`,它只套用於仍為
#: `pending`／`deferred` 的 Proposal,terminal Proposal 不會被改成 `stale`。
ALLOWED_STATUS_TRANSITIONS: dict[ProposalStatus, frozenset[ProposalStatus]] = {
    ProposalStatus.PENDING: frozenset(
        {
            ProposalStatus.DEFERRED,
            ProposalStatus.ACCEPTED,
            ProposalStatus.EDITED,
            ProposalStatus.REJECTED,
            ProposalStatus.REVISION_REQUESTED,
            ProposalStatus.STALE,
        }
    ),
    ProposalStatus.DEFERRED: frozenset(
        {
            ProposalStatus.ACCEPTED,
            ProposalStatus.EDITED,
            ProposalStatus.REJECTED,
            ProposalStatus.REVISION_REQUESTED,
            ProposalStatus.STALE,
        }
    ),
    ProposalStatus.ACCEPTED: frozenset(),
    ProposalStatus.EDITED: frozenset(),
    ProposalStatus.REJECTED: frozenset(),
    ProposalStatus.REVISION_REQUESTED: frozenset(),
    ProposalStatus.STALE: frozenset(),
}

TERMINAL_STATUSES = frozenset(
    status for status, allowed in ALLOWED_STATUS_TRANSITIONS.items() if not allowed
)


def is_allowed_transition(current: ProposalStatus, target: ProposalStatus) -> bool:
    return target in ALLOWED_STATUS_TRANSITIONS[current]


# ── target(action 內建於 target,兩者不可能對不上)───────────────────────────


class SingleTaskTarget(DomainModel):
    action: Literal[ProposalAction.ADD, ProposalAction.REVISE, ProposalAction.WITHDRAW]
    task_id: TaskId

    @property
    def affected_task_ids(self) -> tuple[TaskId, ...]:
        return (self.task_id,)


class MergeTarget(DomainModel):
    action: Literal[ProposalAction.MERGE] = ProposalAction.MERGE
    new_task_id: TaskId
    member_task_ids: tuple[TaskId, ...]

    @property
    def affected_task_ids(self) -> tuple[TaskId, ...]:
        return (self.new_task_id, *self.member_task_ids)

    @model_validator(mode="after")
    def members_are_at_least_two_and_distinct(self):
        if len(self.member_task_ids) < 2:
            raise ValueError("merge requires at least two member tasks")
        if len(set(self.member_task_ids)) != len(self.member_task_ids):
            raise ValueError("merge members must be distinct")
        if self.new_task_id in self.member_task_ids:
            raise ValueError("merge new task id must differ from its members")
        return self


class SplitTarget(DomainModel):
    action: Literal[ProposalAction.SPLIT] = ProposalAction.SPLIT
    parent_task_id: TaskId
    child_task_ids: tuple[TaskId, ...]

    @property
    def affected_task_ids(self) -> tuple[TaskId, ...]:
        return (self.parent_task_id, *self.child_task_ids)

    @model_validator(mode="after")
    def children_are_at_least_two_and_distinct(self):
        if len(self.child_task_ids) < 2:
            raise ValueError("split requires at least two children")
        if len(set(self.child_task_ids)) != len(self.child_task_ids):
            raise ValueError("split children must be distinct")
        if self.parent_task_id in self.child_task_ids:
            raise ValueError("split parent must not be one of its children")
        return self


ProposalTarget = Annotated[
    SingleTaskTarget | MergeTarget | SplitTarget, Field(discriminator="action")
]


# ── JD before／after(§10.3)──────────────────────────────────────────────────


class JdEntry(DomainModel):
    """Current JD 中某個 Task 的內容;``content is None`` 表示不在 JD。"""

    task_id: TaskId
    content: NonEmptyText | None = None


def jd_map(entries: tuple[JdEntry, ...]) -> dict[TaskId, str | None]:
    return {entry.task_id: entry.content for entry in entries}


def _require_canonical_entries(entries: tuple[JdEntry, ...], label: str) -> None:
    task_ids = [entry.task_id for entry in entries]
    if len(set(task_ids)) != len(task_ids):
        raise ValueError(f"{label} has duplicate task ids")
    if task_ids != sorted(task_ids):
        raise ValueError(f"{label} must be sorted by task id")


def validate_edited_jd_after(
    jd_after: tuple[JdEntry, ...], edited_jd_after: tuple[JdEntry, ...]
) -> None:
    """§10.5:`edited` 是文字修改,不是結構修改。

    四條硬規則:key 集合完全相同、null／非 null 位置完全相同、只能改非 null 的內容、
    不得改 action／target／成員集合或任何 topology。前兩條在這裡機械檢查;第三條由前
    兩條蘊含(null 位置固定,唯一還能動的就是非 null 的字);第四條由型別保證——payload
    只是一份 `{task_id -> content}`,沒有任何欄位可以表示 topology。
    """

    _require_canonical_entries(edited_jd_after, "edited_jd_after")
    original = jd_map(jd_after)
    edited = jd_map(edited_jd_after)
    if set(original) != set(edited):
        raise ValueError("edited_jd_after must cover exactly the jd_after task ids")
    for task_id, content in original.items():
        if (content is None) != (edited[task_id] is None):
            raise ValueError(
                f"edited_jd_after must keep the null position of {task_id!r}"
            )


# ── staged Work Model delta(§10.4)──────────────────────────────────────────


class StagedTaskLineage(DomainModel):
    """既有 Task 在提案被接受時要套用的 lineage 變更。"""

    task_id: TaskId
    retirement: Retirement | None = None
    merged_into: TaskId | None = None
    split_from: TaskId | None = None


class StagedTask(DomainModel):
    """提案建立時就配發 ID 的 staged 新 Task ＋ 其語意欄位。"""

    task_id: TaskId
    fields: TaskFields


class StagedWorkModelDelta(DomainModel):
    lineage_changes: tuple[StagedTaskLineage, ...] = ()
    new_tasks: tuple[StagedTask, ...] = ()

    @model_validator(mode="after")
    def delta_is_not_empty(self):
        if not self.lineage_changes and not self.new_tasks:
            raise ValueError("staged work model delta must not be empty")
        return self


# ── revision request 的解析結果(§10.7)───────────────────────────────────────


class RevisionRequestResolution(DomainModel):
    """兩者互斥;皆空表示仍在等待重建(reload 後可重試)。"""

    replacement_proposal_id: Identifier | None = None
    closed_without_replacement_reason: NonEmptyText | None = None

    @model_validator(mode="after")
    def replacement_and_closure_are_mutually_exclusive(self):
        if (
            self.replacement_proposal_id is not None
            and self.closed_without_replacement_reason is not None
        ):
            raise ValueError(
                "a revision request resolves to a replacement or a closure, not both"
            )
        return self


# ── Proposal ────────────────────────────────────────────────────────────────


class Proposal(DomainModel):
    proposal_id: Identifier
    target: ProposalTarget
    jd_before: tuple[JdEntry, ...]
    jd_after: tuple[JdEntry, ...]
    staged_work_model_delta: StagedWorkModelDelta | None = None
    status: ProposalStatus = ProposalStatus.PENDING
    edited_jd_after: tuple[JdEntry, ...] | None = None
    rejection_reason: NonEmptyText | None = None
    excluded_member_task_ids: tuple[TaskId, ...] = ()
    excluded_child_refs: tuple[TaskId, ...] = ()
    stale_reason: NonEmptyText | None = None
    caused_by_decision_id: Identifier | None = None
    revision_resolution: RevisionRequestResolution | None = None

    @property
    def action(self) -> ProposalAction:
        return self.target.action

    @property
    def affected_task_ids(self) -> tuple[TaskId, ...]:
        return self.target.affected_task_ids

    @model_validator(mode="after")
    def jd_snapshots_cover_affected_tasks(self):
        """§10.3:before／after 都是完整 map,key 就是 `affected_task_ids`。"""
        affected = sorted(self.affected_task_ids)
        for label, entries in (
            ("jd_before", self.jd_before),
            ("jd_after", self.jd_after),
        ):
            _require_canonical_entries(entries, label)
            if [entry.task_id for entry in entries] != affected:
                raise ValueError(f"{label} must cover exactly the affected task ids")
        return self

    @model_validator(mode="after")
    def withdraw_removes_a_task_that_is_in_the_jd(self):
        """§10.2／§10.3:`withdraw` 提案只在該 Task 在 JD 中時建立,結果是移出 JD。

        JD 外的 withdraw 依 §9.6 直接 retire,根本不該走到 Proposal。
        """
        if self.action is not ProposalAction.WITHDRAW:
            return self
        task_id = self.target.task_id
        if jd_map(self.jd_before)[task_id] is None:
            raise ValueError("withdraw proposal requires the task to be in the JD")
        if jd_map(self.jd_after)[task_id] is not None:
            raise ValueError("withdraw proposal must remove the task from the JD")
        return self

    @model_validator(mode="after")
    def staged_delta_matches_the_cross_layer_action(self):
        """§10.4:merge／split／JD 內 withdraw **必須**帶非空 staged delta;其餘不得帶。

        缺了它就能建立「改 JD、Work Model 卻沒有對應變更」的提案:`accepted`／`edited`
        時 §9.6 要求兩層原子套用,但根本沒有第二層可套——JD 少了那條 Task,Work Model
        裡的 Task 卻還 active 且毫髮無傷。非空由 `StagedWorkModelDelta` 自己保證。

        **只保證非空,不保證內容對得上 target**(例如 merge 的 delta 是否真的 retire
        了每個 member、split 的子 Task 是否就是 `child_task_ids`)。那是 action-specific
        correspondence,T6 套用前必須驗,不能只看非空。
        """
        cross_layer = {
            ProposalAction.MERGE,
            ProposalAction.SPLIT,
            ProposalAction.WITHDRAW,
        }
        if self.action in cross_layer:
            if self.staged_work_model_delta is None:
                raise ValueError(
                    f"{self.action.value} proposal requires a staged work model delta"
                )
        elif self.staged_work_model_delta is not None:
            raise ValueError(
                f"{self.action.value} proposal must not carry a staged work model delta"
            )
        return self

    @model_validator(mode="after")
    def staged_delta_corresponds_to_the_target(self):
        """delta 的內容必須真的是這個 action 對這些 target 做的事。

        只檢查非空不夠:一份「merge 提案配上只 retire 了其中一個成員」的 delta,
        接受後兩層仍然會分岔——JD 少了兩條、Work Model 卻還留著一條 active 的孤兒。
        這裡把 §10.4 的對應關係寫成型別層規則,套用端(transition)不必再自行判斷。
        """
        delta = self.staged_work_model_delta
        if delta is None:
            return self
        lineage = {change.task_id: change for change in delta.lineage_changes}
        staged_new = {staged.task_id for staged in delta.new_tasks}

        def require(condition: bool, message: str) -> None:
            if not condition:
                raise ValueError(message)

        if self.action is ProposalAction.WITHDRAW:
            change = lineage.get(self.target.task_id)
            require(
                set(lineage) == {self.target.task_id} and not staged_new,
                "withdraw delta must retire exactly its target",
            )
            require(
                change.retirement is not None
                and change.retirement.kind is RetirementKind.WITHDRAWN,
                "withdraw delta must carry a withdrawn retirement",
            )
        elif self.action is ProposalAction.MERGE:
            require(
                set(lineage) == set(self.target.member_task_ids),
                "merge delta must cover exactly its members",
            )
            require(
                staged_new == {self.target.new_task_id},
                "merge delta must stage exactly the surviving task",
            )
            for change in lineage.values():
                require(
                    change.retirement is not None
                    and change.retirement.kind is RetirementKind.MERGED
                    and change.merged_into == self.target.new_task_id,
                    "every merge member must be merged into the surviving task",
                )
        elif self.action is ProposalAction.SPLIT:
            parent = self.target.parent_task_id
            children = set(self.target.child_task_ids)
            require(
                set(lineage) == {parent} | children,
                "split delta must cover the parent and every child",
            )
            require(staged_new == children, "split delta must stage exactly its children")
            parent_change = lineage[parent]
            require(
                parent_change.retirement is not None
                and parent_change.retirement.kind is RetirementKind.SPLIT,
                "split delta must retire the parent as split",
            )
            for child in children:
                require(
                    lineage[child].split_from == parent,
                    "every split child must record its parent",
                )
        return self

    @model_validator(mode="after")
    def payload_matches_status(self):
        """§10.1:每個 payload 只屬於它的狀態。"""
        if self.edited_jd_after is not None:
            if self.status is not ProposalStatus.EDITED:
                raise ValueError("edited_jd_after belongs to the edited status only")
            validate_edited_jd_after(self.jd_after, self.edited_jd_after)
        elif self.status is ProposalStatus.EDITED:
            raise ValueError("edited status requires edited_jd_after")

        if self.rejection_reason is not None and self.status is not ProposalStatus.REJECTED:
            raise ValueError("rejection reason belongs to the rejected status only")

        if self.status is ProposalStatus.STALE:
            if self.stale_reason is None:
                raise ValueError("stale status requires an employee-visible reason")
        elif self.stale_reason is not None:
            raise ValueError("stale reason belongs to the stale status only")

        if self.revision_resolution is not None and (
            self.status is not ProposalStatus.REVISION_REQUESTED
        ):
            raise ValueError(
                "revision resolution belongs to the revision_requested status only"
            )
        return self

    @model_validator(mode="after")
    def revision_request_excludes_members_or_children(self):
        """§10.1／§10.2:排除清單依 action 二選一,至少一項,且必須是提案內的成員。

        命名:`source` 已專指 provenance,排除清單只能叫 member／child。
        """
        excluded_any = bool(self.excluded_member_task_ids or self.excluded_child_refs)
        if self.status is not ProposalStatus.REVISION_REQUESTED:
            if excluded_any:
                raise ValueError(
                    "exclusion lists belong to the revision_requested status only"
                )
            return self
        if not excluded_any:
            raise ValueError("revision_requested requires at least one exclusion")

        if self.excluded_member_task_ids:
            if self.action is not ProposalAction.MERGE:
                raise ValueError("excluded members apply to merge proposals only")
            unknown = set(self.excluded_member_task_ids) - set(
                self.target.member_task_ids
            )
            if unknown:
                raise ValueError(f"unknown excluded members: {sorted(unknown)}")
        if self.excluded_child_refs:
            if self.action is not ProposalAction.SPLIT:
                raise ValueError("excluded children apply to split proposals only")
            unknown = set(self.excluded_child_refs) - set(self.target.child_task_ids)
            if unknown:
                raise ValueError(f"unknown excluded children: {sorted(unknown)}")
        return self
