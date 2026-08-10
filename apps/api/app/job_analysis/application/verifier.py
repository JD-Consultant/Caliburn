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

from app.core.domain import DomainModel, Identifier, NonEmptyText, TaskId
from app.core.journal import TurnSpeaker
from app.job_analysis.llm import (
    IdentityRelation,
    IssueResolutionKind,
    SignalDisposition,
    TaskAnalysisResult,
    TaskChangeKind,
    WorkSignal,
)
from app.job_analysis.llm.result import NextQuestionTargetKind
from app.core.domain.work_model import OpenIssueKind


# ── Context Packet 的 ordinal 檢視(§11.2:mapping 存在該輪呼叫紀錄側)──────


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
    reconciliation_task_id: TaskId | None = None
    subject_task_id: TaskId | None = None
    """OPKS 缺口在問哪一個 Task(ADR 0054 決定 19),`answered` 的前提要用它。"""


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

    def open_issue(self, ordinal: int) -> PacketOpenIssue | None:
        for issue in self.open_issues:
            if issue.ordinal == ordinal:
                return issue
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
    RELATION_DOES_NOT_MATCH_MAPPING = "relation_does_not_match_mapping"
    TARGET_ORDINALS_DISAGREE = "target_ordinals_disagree"
    TASK_CHANGE_TARGET_COUNT = "task_change_target_count"
    TASK_FIELDS_REQUIRED = "task_fields_required"
    TASK_FIELDS_FORBIDDEN = "task_fields_forbidden"
    WITHDRAW_REASON_REQUIRED = "withdraw_reason_required"
    WITHDRAW_REASON_FORBIDDEN = "withdraw_reason_forbidden"
    SPLIT_CHILDREN_INSUFFICIENT = "split_children_insufficient"
    SPLIT_SUPPORT_UNKNOWN = "split_support_unknown"
    OPEN_ISSUE_ANCHORS_INSUFFICIENT = "open_issue_anchors_insufficient"
    NEXT_QUESTION_TARGET_INVALID = "next_question_target_invalid"
    ISSUE_RESOLUTION_ORDINAL_UNKNOWN = "issue_resolution_ordinal_unknown"
    ISSUE_RESOLUTION_REPEATED = "issue_resolution_repeated"
    ISSUE_RESOLUTION_ANSWER_NOT_RECORDED = "issue_resolution_answer_not_recorded"
    SUPERSESSION_UNKNOWN = "supersession_unknown"
    SUPERSESSION_ALREADY_SUPERSEDED = "supersession_already_superseded"
    SUPERSESSION_TASK_NOT_TARGETED = "supersession_task_not_targeted"
    SUPERSESSION_MISSING_CURRENT_TURN_ANCHOR = "supersession_missing_current_turn_anchor"
    DUPLICATE_TASK_CHANGE_TARGET = "duplicate_task_change_target"
    DUPLICATE_WORK_SIGNAL = "duplicate_work_signal"
    RESOLUTION_OPEN_ISSUE_UNKNOWN = "resolution_open_issue_unknown"
    RESOLUTION_MISSING_CURRENT_TURN_ANCHOR = (
        "resolution_missing_current_turn_anchor"
    )
    RESOLUTION_MAPPING_INVALID = "resolution_mapping_invalid"
    RESOLUTION_OPEN_ISSUE_REPEATED = "resolution_open_issue_repeated"
    RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION = (
        "resolution_opks_gap_needs_issue_resolution"
    )


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
    _verify_open_issues_are_resolved_once(result, violations)
    _verify_issue_resolutions(result, context, violations)
    _verify_task_change_targets_are_claimed_once(result, violations)
    _verify_work_signals_are_not_exact_duplicates(result, violations)
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
    _verify_mapping_combination(index, signal, violations)
    _verify_task_change(index, signal, context, violations)
    _verify_open_issue(index, signal, violations)
    _verify_open_issue_resolution(index, signal, context, violations)
    _verify_supersessions(index, signal, context, violations)


#: 會把本輪員工依據接到既有 Task 上、且讓那個 Task 繼續存在的兩種處置。
#
# `support_only` 與 `revise` 都會 append SupportLink 到 target Task,因此
# `analysis_input_digest` 一定改變,OPKS 會重新分析。其他處置都不行:
# `add` 建立的是**新** Task(缺口問的那個 Task 沒拿到任何依據);
# `withdraw`／`merge`／`split` 讓 target 退場,那條路是把 gap 移除(T13)不是回答它;
# `exclude`／`open_issue` 根本不碰 Task 的依據。
_EVIDENCE_LEAVING_CHANGES = frozenset({TaskChangeKind.REVISE})


def _leaves_employee_evidence_on(
    signal: WorkSignal,
    task_id: TaskId,
    context: VerificationContext,
) -> bool:
    if not signal.anchors:
        return False
    if signal.disposition is SignalDisposition.SUPPORT_ONLY:
        pass
    elif (
        signal.disposition is SignalDisposition.TASK_CHANGE
        and signal.task_change is not None
        and signal.task_change.change in _EVIDENCE_LEAVING_CHANGES
    ):
        pass
    else:
        return False
    ordinals = {task.ordinal: task.task_id for task in context.tasks}
    return any(
        ordinals.get(ordinal) == task_id
        for ordinal in signal.identity.target_task_ordinals
    )


def _verify_issue_resolutions(
    result: TaskAnalysisResult,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """ADR 0054 決定 22–23 的機械前提。

    `answered` 若沒有同輪留下員工依據,`analysis_input_digest` 不會變,OPKS 不會再
    分析,缺口就被**假關閉**——員工以為答過了,系統卻永遠不會用那個答案。這是跨欄位
    但完全機械可判的條件,所以擋得住。

    擋不住的是「模型把 employee_unknown 當成偷懶出口」:那要判斷員工到底有沒有回答,
    是語意判斷。ADR 後果段已載明只能靠 rubric 與「specialist 下次仍會重提同一 gap」
    的自我修正。
    """

    by_ordinal = {issue.ordinal: issue for issue in context.open_issues}
    seen: set[int] = set()
    for resolution in result.issue_resolutions:
        issue = by_ordinal.get(resolution.ordinal)
        if issue is None:
            # terminal issue 不配發 ordinal(決定 20),指過去就是無效 ordinal。
            _add(
                violations,
                ViolationCode.ISSUE_RESOLUTION_ORDINAL_UNKNOWN,
                f"issue resolution targets unknown open issue ordinal "
                f"{resolution.ordinal}",
            )
            continue
        if resolution.ordinal in seen:
            _add(
                violations,
                ViolationCode.ISSUE_RESOLUTION_REPEATED,
                f"open issue ordinal {resolution.ordinal} is resolved more than once",
            )
            continue
        seen.add(resolution.ordinal)
        if resolution.resolution is not IssueResolutionKind.ANSWERED:
            continue
        if issue.subject_task_id is None:
            continue
        if not any(
            _leaves_employee_evidence_on(signal, issue.subject_task_id, context)
            for signal in result.work_signals
        ):
            _add(
                violations,
                ViolationCode.ISSUE_RESOLUTION_ANSWER_NOT_RECORDED,
                f"open issue ordinal {resolution.ordinal} was marked answered without a "
                "same-turn work signal leaving employee evidence on its subject task",
            )


def _verify_open_issue_resolution(
    index: int,
    signal: WorkSignal,
    context: VerificationContext,
    violations: list[Violation],
) -> None:
    """ADR 0044:只允許 ``no_match + add`` 或 ``exclude`` 關閉 JD-only issue。

    ADR 0047 把適用範圍擴及一般 open issue——那些是模型自己提的待答問題,任何 disposition
    皆可關閉。0044 的 reconciliation 判準原樣保留。

    **OPKS 缺口不在 0047 的範圍內**(見下方 `subject_task_id` 那一段)。
    """

    ordinal = signal.resolves_open_issue_ordinal
    if ordinal is None:
        return
    issue = context.open_issue(ordinal)
    if issue is None:
        _add(
            violations,
            ViolationCode.RESOLUTION_OPEN_ISSUE_UNKNOWN,
            f"open issue ordinal {ordinal} is outside the packet",
            index,
        )
        return

    if issue.subject_task_id is not None:
        # ADR 0054 決定 22:gap resolution **不綁在 `WorkSignal.disposition` 上**,
        # 它有自己的 `issue_resolutions[]` 通道。
        #
        # 0047 的「全部 open issue」指的是**主顧問自己提出**的那些(責任邊界不明／
        # 證據不足／矛盾未解／task_boundary_uncertain),理由是只有它知道自己上一輪
        # 問過什麼。OPKS 缺口由 specialist 提出,而且決定 23 給了它一個機械可判的
        # 前提(同輪必須在該 Task 留下員工依據)。不擋這條路的話,模型送一筆帶當輪
        # anchor 的訊號就能把缺口整筆刪掉、什麼依據都不留——digest 不變、OPKS 不再
        # 分析,缺口被假關閉,而決定 23 的檢查只掛在新通道上,擋不到這裡。
        #
        # 帶依據的訊號也一樣擋:放行等於把決定 23 的前提複製到第二處,兩份遲早失步。
        # `subject_task_id` 就是缺口的標記——domain 保證 `opks_axis` 非空必有它,而
        # 全 repo 只有 `_gap_issues()` 會寫它。
        _add(
            violations,
            ViolationCode.RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION,
            f"open issue ordinal {ordinal} is an OPKS gap and may only be resolved "
            "through issue_resolutions[]",
            index,
        )
        return

    # ADR 0047:關閉既有結論必須錨定**當回合**的答案,不能用舊證據批次清單。
    # 與 supersession 沿用同一條不變量。
    if all(
        anchor.turn_ordinal != context.current_turn_ordinal for anchor in signal.anchors
    ):
        _add(
            violations,
            ViolationCode.RESOLUTION_MISSING_CURRENT_TURN_ANCHOR,
            "resolving an open issue requires the current employee turn among the anchors",
            index,
        )

    if issue.reconciliation_task_id is None:
        # 一般 open issue:模型自己提的問題,它自己知道有沒有被回答(ADR 0047)。
        return

    change = signal.task_change
    is_no_match_add = (
        signal.disposition is SignalDisposition.TASK_CHANGE
        and change is not None
        and change.change is TaskChangeKind.ADD
        and signal.identity.relation is IdentityRelation.NO_MATCH
        and not signal.identity.target_task_ordinals
        and not change.target_task_ordinals
    )
    is_exclusion = (
        signal.disposition is SignalDisposition.EXCLUDE and signal.exclude is not None
    )
    if not (is_no_match_add or is_exclusion):
        _add(
            violations,
            ViolationCode.RESOLUTION_MAPPING_INVALID,
            "a reconciliation issue may only resolve through no_match + add or exclude",
            index,
        )


def _verify_open_issues_are_resolved_once(
    result: TaskAnalysisResult,
    violations: list[Violation],
) -> None:
    seen: set[int] = set()
    for index, signal in enumerate(result.work_signals):
        ordinal = signal.resolves_open_issue_ordinal
        if ordinal is None:
            continue
        if ordinal in seen:
            _add(
                violations,
                ViolationCode.RESOLUTION_OPEN_ISSUE_REPEATED,
                f"open issue ordinal {ordinal} is resolved more than once",
                index,
            )
        seen.add(ordinal)


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


#: §12.2 的 relation × disposition 對照中,relation 被唯一決定的那幾格。
#: `withdraw`／`split`／`exclude`／`open_issue` 在表中寫的是「任一 relation」,不收緊。
_REQUIRED_RELATION_BY_DISPOSITION = {
    SignalDisposition.SUPPORT_ONLY: IdentityRelation.DUPLICATE,
}
_REQUIRED_RELATION_BY_CHANGE = {
    TaskChangeKind.ADD: IdentityRelation.NO_MATCH,
    TaskChangeKind.REVISE: IdentityRelation.OVERLAP,
    TaskChangeKind.MERGE: IdentityRelation.OVERLAP,
}
#: 這兩格的 mapping 明寫「沿用該 task_id」／「merge 候選」,identity 認的是哪些 Task,
#: 改的就必須是那些 Task;兩組 target 不同,application 無從知道該信哪一組。
_CHANGES_SHARING_IDENTITY_TARGETS = frozenset(
    {TaskChangeKind.REVISE, TaskChangeKind.MERGE}
)


def _verify_mapping_combination(
    index: int, signal: WorkSignal, violations: list[Violation]
) -> None:
    """§12.2:relation × disposition 的組合必須落在對照表上。

    三者各自合法不代表組合合法——`duplicate` ＋ `add` 會憑一筆已知 Task 的依據再造一個
    重複 Task,`no_match` ＋ `support_only` 則會把一筆沒有對象的依據掛到空氣上。
    """
    relation = signal.identity.relation
    required = _REQUIRED_RELATION_BY_DISPOSITION.get(signal.disposition)
    if required is not None and relation is not required:
        _add(
            violations,
            ViolationCode.RELATION_DOES_NOT_MATCH_MAPPING,
            f"{signal.disposition.value} requires relation {required.value}, "
            f"got {relation.value}",
            index,
        )

    change = signal.task_change
    if change is None:
        return
    required = _REQUIRED_RELATION_BY_CHANGE.get(change.change)
    if required is not None and relation is not required:
        _add(
            violations,
            ViolationCode.RELATION_DOES_NOT_MATCH_MAPPING,
            f"{change.change.value} requires relation {required.value}, "
            f"got {relation.value}",
            index,
        )
    if change.change in _CHANGES_SHARING_IDENTITY_TARGETS and set(
        change.target_task_ordinals
    ) != set(signal.identity.target_task_ordinals):
        _add(
            violations,
            ViolationCode.TARGET_ORDINALS_DISAGREE,
            f"{change.change.value} targets {sorted(set(change.target_task_ordinals))} "
            f"but identity matched {sorted(set(signal.identity.target_task_ordinals))}",
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
        # §9.5 要求 withdrawn 一定有 reason,而只有模型知道是哪一種;缺了它
        # application 只能猜,猜錯就把撤回理由寫成假的。
        if change.withdraw_reason is None:
            _add(
                violations,
                ViolationCode.WITHDRAW_REASON_REQUIRED,
                "withdraw requires a withdraw_reason",
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

    if change.change is not TaskChangeKind.WITHDRAW and change.withdraw_reason is not None:
        _add(
            violations,
            ViolationCode.WITHDRAW_REASON_FORBIDDEN,
            f"{change.change.value} must not carry a withdraw_reason",
            index,
        )

    if change.change is TaskChangeKind.SPLIT and len(change.split_children) < 2:
        _add(
            violations,
            ViolationCode.SPLIT_CHILDREN_INSUFFICIENT,
            f"split requires at least two children, got {len(change.split_children)}",
            index,
        )
    if change.change is TaskChangeKind.SPLIT and len(targets) == 1:
        parent = context.task(targets[0])
        if parent is not None:
            effective = {
                support.ordinal
                for support in parent.support_links
                if support.is_effective
            }
            for child_index, child in enumerate(change.split_children):
                inherited = child.inherited_support_ordinals
                if len(set(inherited)) != len(inherited):
                    _add(
                        violations,
                        ViolationCode.SPLIT_SUPPORT_UNKNOWN,
                        f"split child {child_index} repeats a parent support ordinal",
                        index,
                    )
                unknown = set(inherited) - effective
                if unknown:
                    _add(
                        violations,
                        ViolationCode.SPLIT_SUPPORT_UNKNOWN,
                        f"split child {child_index} references unknown or superseded "
                        f"parent support ordinal(s): {sorted(unknown)}",
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


def _verify_work_signals_are_not_exact_duplicates(
    result: TaskAnalysisResult, violations: list[Violation]
) -> None:
    """只拒絕逐欄完全相同的 signal；不做文字相似度或語意猜測。"""
    groups: dict[str, list[int]] = {}
    for index, signal in enumerate(result.work_signals):
        groups.setdefault(signal.model_dump_json(), []).append(index)
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            _add(
                violations,
                ViolationCode.DUPLICATE_WORK_SIGNAL,
                f"work signal is an exact duplicate of signal(s) {indexes}",
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
