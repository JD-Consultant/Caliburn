"""Deterministic verifier for `TaskAnalysisResult.v1`(§9.5、§12.3)。

純函式,不呼叫模型、不碰 DB。輸入是模型輸出 ＋ 該輪 Context Packet 的 **ordinal 檢視**
(`VerificationContext`);輸出是一份 `VerificationReport`,由 application(T6)決定
怎麼處置。

**邊界(哪些規則不在這裡)**

- Task／Proposal 的形狀不變量已經寫在 domain 型別層(T1):`withdrawn` 必有 reason、
  `merged` 必有 `merged_into`、`active` 必有有效 SupportLink、lineage 不成環、
  §10.5 的 `edited_jd_after` 四條硬規則(`domain.validate_edited_jd_after`)。
  非法狀態根本無法被建構,不需要在這裡再檢一次。
- **語意判斷一律不在這裡**(§9.5 末段):purpose 是否相同、該不該 merge／split、
  outcome 是否可理解、enabler 分類是否正確,全歸 rubric 與員工審核。
- **不做全文 UUID 形狀掃描**(§12.3):輸出契約沒有任何可填 ID 的欄位,而員工原話可能
  合法含有 request／correlation UUID,掃描只會誤殺。只驗 ordinal 與結構欄位。

**兩條由 §12.2 mapping 推出、文件未逐字列出的規則**,標記在各自的檢查點:
`change` 的 target 數量必須讓 §12.2 的 mapping 成為全函式(add 0／revise 1／
withdraw 1／merge ≥2／split 1),以及 add／revise／merge 必須帶 `task_fields`
——沒有語意欄位,application 連一個 Task 都建不出來。兩者都是機械規則,不是語意裁決。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from app.job_analysis.domain import DomainModel, Identifier, NonEmptyText, TaskId
from app.job_analysis.llm import (
    IdentityRelation,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    WorkSignal,
)
from app.job_analysis.llm.result import NextQuestionTargetKind
from app.job_analysis.domain.work_model import OpenIssueKind


# ── Context Packet 的 ordinal 檢視(§11.2:mapping 存在該輪呼叫紀錄側)──────


class TurnSpeaker(StrEnum):
    EMPLOYEE = "employee"
    CONSULTANT = "consultant"


class PacketTurn(DomainModel):
    ordinal: int
    speaker: TurnSpeaker
    turn_id: Identifier
    text: NonEmptyText


class PacketSupportLink(DomainModel):
    """Task-local support ordinal ＋ 目前是否仍有效(§11.4)。"""

    ordinal: int
    is_effective: bool


class PacketTask(DomainModel):
    ordinal: int
    task_id: TaskId
    support_links: tuple[PacketSupportLink, ...] = ()


class PacketRetiredTask(DomainModel):
    """`retired_tasks[]` 是 read-only 的防重提資訊(§11.4)。"""

    ordinal: int
    task_id: TaskId


class PacketOpenIssue(DomainModel):
    ordinal: int
    issue_id: Identifier


class VerificationContext(DomainModel):
    """該輪 packet 投影出的 ordinal namespace。

    `retired_tasks[]` 依 §11.4 用**另一組編號**,而且這裡要求它與 active 的編號
    **不相交**:兩組若共用同一個整數,「retired ordinal 不得出現在任何 target」就不可
    判定——`target_task_ordinals: [2]` 會永遠先被解讀成 active #2,規則等於不存在。
    不相交是「另一組編號」的一種合法實作,也是唯一能讓這條規則真的擋得住的實作。
    """

    turns: tuple[PacketTurn, ...] = ()
    current_turn_ordinal: int
    tasks: tuple[PacketTask, ...] = ()
    retired_tasks: tuple[PacketRetiredTask, ...] = ()
    open_issues: tuple[PacketOpenIssue, ...] = ()

    @model_validator(mode="after")
    def ordinals_are_unique_within_each_namespace(self):
        for label, ordinals in (
            ("turn", [turn.ordinal for turn in self.turns]),
            ("task", [task.ordinal for task in self.tasks]),
            ("retired task", [task.ordinal for task in self.retired_tasks]),
            ("open issue", [issue.ordinal for issue in self.open_issues]),
        ):
            if len(set(ordinals)) != len(ordinals):
                raise ValueError(f"duplicate {label} ordinal")
        for task in self.tasks:
            link_ordinals = [link.ordinal for link in task.support_links]
            if len(set(link_ordinals)) != len(link_ordinals):
                raise ValueError("duplicate support link ordinal")
        return self

    @model_validator(mode="after")
    def retired_task_ordinals_do_not_collide_with_active_ones(self):
        collisions = {task.ordinal for task in self.tasks} & {
            task.ordinal for task in self.retired_tasks
        }
        if collisions:
            raise ValueError(
                f"retired task ordinals must not collide with active ones: "
                f"{sorted(collisions)}"
            )
        return self

    @model_validator(mode="after")
    def current_turn_is_an_employee_turn_in_the_packet(self):
        turn = self.turn(self.current_turn_ordinal)
        if turn is None or turn.speaker is not TurnSpeaker.EMPLOYEE:
            raise ValueError("current turn must be an employee turn in the packet")
        return self

    def turn(self, ordinal: int) -> PacketTurn | None:
        for turn in self.turns:
            if turn.ordinal == ordinal:
                return turn
        return None

    def task(self, ordinal: int) -> PacketTask | None:
        for task in self.tasks:
            if task.ordinal == ordinal:
                return task
        return None

    @property
    def retired_task_ordinals(self) -> frozenset[int]:
        return frozenset(task.ordinal for task in self.retired_tasks)

    @property
    def open_issue_ordinals(self) -> frozenset[int]:
        return frozenset(issue.ordinal for issue in self.open_issues)


# ── 違規 ────────────────────────────────────────────────────────────────────


class ViolationCode(StrEnum):
    ANCHOR_MISSING = "anchor_missing"
    ANCHOR_TURN_UNKNOWN = "anchor_turn_unknown"
    ANCHOR_TURN_NOT_EMPLOYEE = "anchor_turn_not_employee"
    QUOTE_NOT_VERBATIM = "quote_not_verbatim"
    TARGET_ORDINAL_UNKNOWN = "target_ordinal_unknown"
    TARGET_ORDINAL_RETIRED = "target_ordinal_retired"
    TARGET_ORDINAL_REPEATED = "target_ordinal_repeated"
    IDENTITY_TARGETS_NOT_EMPTY = "identity_targets_not_empty"
    IDENTITY_TARGETS_MISSING = "identity_targets_missing"
    PAYLOAD_DOES_NOT_MATCH_DISPOSITION = "payload_does_not_match_disposition"
    TASK_CHANGE_TARGET_COUNT = "task_change_target_count"
    TASK_FIELDS_REQUIRED = "task_fields_required"
    TASK_FIELDS_FORBIDDEN = "task_fields_forbidden"
    SPLIT_CHILDREN_INSUFFICIENT = "split_children_insufficient"
    OPEN_ISSUE_ANCHORS_INSUFFICIENT = "open_issue_anchors_insufficient"
    NEXT_QUESTION_TARGET_INVALID = "next_question_target_invalid"
    SUPERSESSION_UNKNOWN = "supersession_unknown"
    SUPERSESSION_ALREADY_SUPERSEDED = "supersession_already_superseded"
    SUPERSESSION_TASK_NOT_TARGETED = "supersession_task_not_targeted"
    SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR = "supersession_missing_current_turn_anchor"
    DUPLICATE_TASK_CHANGE_TARGET = "duplicate_task_change_target"


class Violation(DomainModel):
    code: ViolationCode
    detail: NonEmptyText
    signal_index: int | None = None
    """None 表示整份結果層級的違規(例如 `next_question`)。"""


class VerificationReport(DomainModel):
    violations: tuple[Violation, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.violations

    @property
    def codes(self) -> tuple[ViolationCode, ...]:
        return tuple(violation.code for violation in self.violations)

    @property
    def rejected_signal_indexes(self) -> frozenset[int]:
        return frozenset(
            violation.signal_index
            for violation in self.violations
            if violation.signal_index is not None
        )


# ── 檢查 ────────────────────────────────────────────────────────────────────


def verify_task_analysis_result(
    result: TaskAnalysisResult, context: VerificationContext
) -> VerificationReport:
    violations: list[Violation] = []
    for index, signal in enumerate(result.work_signals):
        _verify_signal(index, signal, context, violations)
    _verify_task_change_targets_are_claimed_once(result, violations)
    _verify_next_question(result, context, violations)
    return VerificationReport(violations=tuple(violations))


def _add(
    violations: list[Violation],
    code: ViolationCode,
    detail: str,
    signal_index: int | None = None,
) -> None:
    violations.append(Violation(code=code, detail=detail, signal_index=signal_index))


def _verify_signal(
    index: int,
    signal: WorkSignal,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    _verify_anchors(index, signal, context, violations)
    _verify_identity(index, signal, context, violations)
    _verify_payload_matches_disposition(index, signal, violations)
    _verify_task_change(index, signal, context, violations)
    _verify_open_issue(index, signal, violations)
    _verify_supersessions(index, signal, context, violations)


def _verify_anchors(
    index: int,
    signal: WorkSignal,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """§12.3:anchors ≥1;quote 必須是該回合原文的逐字子字串,且該回合必須是員工回合。"""
    if not signal.anchors:
        _add(violations, ViolationCode.ANCHOR_MISSING, "signal has no anchor", index)
    for anchor in signal.anchors:
        turn = context.turn(anchor.turn_ordinal)
        if turn is None:
            _add(
                violations,
                ViolationCode.ANCHOR_TURN_UNKNOWN,
                f"turn ordinal {anchor.turn_ordinal} is outside the packet",
                index,
            )
            continue
        if turn.speaker is not TurnSpeaker.EMPLOYEE:
            _add(
                violations,
                ViolationCode.ANCHOR_TURN_NOT_EMPLOYEE,
                f"turn ordinal {anchor.turn_ordinal} is a {turn.speaker.value} turn",
                index,
            )
            continue
        if anchor.quote not in turn.text:
            _add(
                violations,
                ViolationCode.QUOTE_NOT_VERBATIM,
                f"quote is not a verbatim substring of turn {anchor.turn_ordinal}",
                index,
            )


def _verify_target_ordinals(
    index: int,
    ordinals: tuple[int, ...],
    field: str,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """§12.3:target 必須在 packet 的 active 範圍內;retired 的編號不得被指涉(§11.4)。

    重複也拒:`[1, 1]` 會讓「merge 需 ≥2 target」被一個 Task 冒充,而去重會靜默改變
    模型的意思——ADR 0040 決定 25 把陣列語意的收斂交給 verifier,這裡選擇明確拒絕。
    """
    seen: set[int] = set()
    for ordinal in ordinals:
        if ordinal in seen:
            _add(
                violations,
                ViolationCode.TARGET_ORDINAL_REPEATED,
                f"{field} repeats task ordinal {ordinal}",
                index,
            )
            continue
        seen.add(ordinal)
        if context.task(ordinal) is not None:
            continue
        if ordinal in context.retired_task_ordinals:
            _add(
                violations,
                ViolationCode.TARGET_ORDINAL_RETIRED,
                f"{field} references retired task ordinal {ordinal}",
                index,
            )
        else:
            _add(
                violations,
                ViolationCode.TARGET_ORDINAL_UNKNOWN,
                f"{field} references unknown task ordinal {ordinal}",
                index,
            )


def _verify_identity(
    index: int,
    signal: WorkSignal,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """§12.3:`no_match` 時 target 必須為空;`duplicate`／`overlap` 時 ≥1。"""
    targets = signal.identity.target_task_ordinals
    _verify_target_ordinals(index, targets, "identity", context, violations)
    relation = signal.identity.relation
    if relation is IdentityRelation.NO_MATCH and targets:
        _add(
            violations,
            ViolationCode.IDENTITY_TARGETS_NOT_EMPTY,
            "no_match must not reference any task ordinal",
            index,
        )
    if (
        relation in {IdentityRelation.DUPLICATE, IdentityRelation.OVERLAP}
        and not targets
    ):
        _add(
            violations,
            ViolationCode.IDENTITY_TARGETS_MISSING,
            f"{relation.value} requires at least one task ordinal",
            index,
        )


_PAYLOAD_FIELD_BY_DISPOSITION = {
    SignalDisposition.TASK_CHANGE: "task_change",
    SignalDisposition.EXCLUDE: "exclude",
    SignalDisposition.OPEN_ISSUE: "open_issue",
    SignalDisposition.SUPPORT_ONLY: None,
}


def _verify_payload_matches_disposition(
    index: int, signal: WorkSignal, violations: list[Violation]
) -> None:
    """§12.1:payload 依 disposition 擇一;`support_only` 不帶 payload。"""
    expected = _PAYLOAD_FIELD_BY_DISPOSITION[signal.disposition]
    for field in ("task_change", "exclude", "open_issue"):
        present = getattr(signal, field) is not None
        if present and field != expected:
            _add(
                violations,
                ViolationCode.PAYLOAD_DOES_NOT_MATCH_DISPOSITION,
                f"{signal.disposition.value} must not carry a {field} payload",
                index,
            )
        elif not present and field == expected:
            _add(
                violations,
                ViolationCode.PAYLOAD_DOES_NOT_MATCH_DISPOSITION,
                f"{signal.disposition.value} requires a {field} payload",
                index,
            )


#: §12.2 mapping 的 target 數量;寫成表格,讓「哪個 change 收幾個 target」只有一處權威。
_TARGET_COUNT_BY_CHANGE: dict[TaskChangeKind, tuple[int, int | None]] = {
    TaskChangeKind.ADD: (0, 0),
    TaskChangeKind.REVISE: (1, 1),
    TaskChangeKind.WITHDRAW: (1, 1),
    TaskChangeKind.MERGE: (2, None),
    TaskChangeKind.SPLIT: (1, 1),
}


def _verify_task_change(
    index: int,
    signal: WorkSignal,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    change = signal.task_change
    if change is None:
        return
    targets = change.target_task_ordinals
    _verify_target_ordinals(index, targets, "task_change", context, violations)

    minimum, maximum = _TARGET_COUNT_BY_CHANGE[change.change]
    if len(targets) < minimum or (maximum is not None and len(targets) > maximum):
        expected = f"{minimum}" if minimum == maximum else f"at least {minimum}"
        _add(
            violations,
            ViolationCode.TASK_CHANGE_TARGET_COUNT,
            f"{change.change.value} expects {expected} target ordinal(s), "
            f"got {len(targets)}",
            index,
        )

    if change.change is TaskChangeKind.WITHDRAW:
        # §12.3:withdraw 不得帶 task_fields——撤回不是改寫。
        if change.task_fields is not None:
            _add(
                violations,
                ViolationCode.TASK_FIELDS_FORBIDDEN,
                "withdraw must not carry task_fields",
                index,
            )
    elif change.change is not TaskChangeKind.SPLIT and change.task_fields is None:
        # merge 由 §12.3 明文要求;add／revise 由 §12.2 推出——沒有語意欄位,
        # application 連一個 Task 都建不出來(domain 的 statement／action／object 必填)。
        _add(
            violations,
            ViolationCode.TASK_FIELDS_REQUIRED,
            f"{change.change.value} requires task_fields",
            index,
        )

    if change.change is TaskChangeKind.SPLIT and len(change.split_children) < 2:
        _add(
            violations,
            ViolationCode.SPLIT_CHILDREN_INSUFFICIENT,
            f"split requires at least two children, got {len(change.split_children)}",
            index,
        )


def _verify_open_issue(
    index: int, signal: WorkSignal, violations: list[Violation]
) -> None:
    """§12.3:`矛盾未解` 需要 ≥2 anchors(矛盾至少要有兩邊)。"""
    issue = signal.open_issue
    if issue is None:
        return
    if (
        issue.kind is OpenIssueKind.UNRESOLVED_CONTRADICTION
        and len(signal.anchors) < 2
    ):
        _add(
            violations,
            ViolationCode.OPEN_ISSUE_ANCHORS_INSUFFICIENT,
            "矛盾未解 requires at least two anchors",
            index,
        )


def _verify_supersessions(
    index: int,
    signal: WorkSignal,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """§12.3:被取代的依據必須存在、目前仍有效,且屬於同一筆 signal 的 target Task。

    另外(§12.3 末段):新來源第一版一律是本次正在處理的 employee turn,因此該 turn
    必須出現在同一筆 signal 的 anchors 中——否則 application 無從決定 `superseded_by`
    要寫誰,而契約刻意不給模型指定的欄位。
    """
    references = signal.supersedes_support_ordinals
    if not references:
        return

    targeted = set(signal.identity.target_task_ordinals)
    if signal.task_change is not None:
        targeted |= set(signal.task_change.target_task_ordinals)

    for reference in references:
        if reference.task_ordinal not in targeted:
            _add(
                violations,
                ViolationCode.SUPERSESSION_TASK_NOT_TARGETED,
                f"task ordinal {reference.task_ordinal} is not targeted by this signal",
                index,
            )
        task = context.task(reference.task_ordinal)
        if task is None:
            _add(
                violations,
                ViolationCode.SUPERSESSION_UNKNOWN,
                f"task ordinal {reference.task_ordinal} is not an active packet task",
                index,
            )
            continue
        link = next(
            (
                candidate
                for candidate in task.support_links
                if candidate.ordinal == reference.support_ordinal
            ),
            None,
        )
        if link is None:
            _add(
                violations,
                ViolationCode.SUPERSESSION_UNKNOWN,
                f"support ordinal {reference.support_ordinal} does not exist on task "
                f"ordinal {reference.task_ordinal}",
                index,
            )
        elif not link.is_effective:
            _add(
                violations,
                ViolationCode.SUPERSESSION_ALREADY_SUPERSEDED,
                f"support ordinal {reference.support_ordinal} on task ordinal "
                f"{reference.task_ordinal} is already superseded",
                index,
            )

    if all(
        anchor.turn_ordinal != context.current_turn_ordinal for anchor in signal.anchors
    ):
        _add(
            violations,
            ViolationCode.SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR,
            "supersession requires the current employee turn among the anchors",
            index,
        )


def _verify_task_change_targets_are_claimed_once(
    result: TaskAnalysisResult, violations: list[Violation]
) -> None:
    """§12.3:同一個 target Task 被兩筆 `task_change` 指涉 → **兩筆都拒**,不任選贏家。"""
    claims: dict[int, list[int]] = {}
    for index, signal in enumerate(result.work_signals):
        if signal.task_change is None:
            continue
        for ordinal in set(signal.task_change.target_task_ordinals):
            claims.setdefault(ordinal, []).append(index)

    for ordinal, indexes in sorted(claims.items()):
        if len(indexes) < 2:
            continue
        for index in indexes:
            _add(
                violations,
                ViolationCode.DUPLICATE_TASK_CHANGE_TARGET,
                f"task ordinal {ordinal} is claimed by task_change signals "
                f"{indexes}",
                index,
            )


def _verify_next_question(
    result: TaskAnalysisResult,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """§12.3:`next_question.target` 必須指向存在的 packet ordinal 或本次輸出的合法 index。"""
    target = result.next_question.target
    if target is None:
        return
    if target.kind is NextQuestionTargetKind.EXISTING_OPEN_ISSUE:
        if target.index is not None:
            _add(
                violations,
                ViolationCode.NEXT_QUESTION_TARGET_INVALID,
                "existing_open_issue target must not carry a signal index",
            )
        if target.ordinal is None or target.ordinal not in context.open_issue_ordinals:
            _add(
                violations,
                ViolationCode.NEXT_QUESTION_TARGET_INVALID,
                f"unknown open issue ordinal {target.ordinal}",
            )
        return

    if target.ordinal is not None:
        _add(
            violations,
            ViolationCode.NEXT_QUESTION_TARGET_INVALID,
            "new_signal target must not carry a packet ordinal",
        )
    if target.index is None or not 0 <= target.index < len(result.work_signals):
        _add(
            violations,
            ViolationCode.NEXT_QUESTION_TARGET_INVALID,
            f"signal index {target.index} is outside this result",
        )
