"""Current Work Model 的 Task Analysis slice(§9.1)。

本模組只涵蓋 Task／open issue／excluded signal;角色假說、coverage、current focus、
active question、conversation 與 Product Proposal 由後續垂直切片定義(§9 前言)。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from .base import DomainModel, Identifier, NonEmptyText, TaskId
from .sources import SourceAnchor, SourceRef
from .task import Task


class OpenIssueKind(StrEnum):
    RESPONSIBILITY_UNCLEAR = "責任邊界不明"
    INSUFFICIENT_EVIDENCE = "證據不足"
    UNRESOLVED_CONTRADICTION = "矛盾未解"
    TASK_BOUNDARY_UNCERTAIN = "task_boundary_uncertain"


class OpksGapAxis(StrEnum):
    """OPKS 缺口所在的軸(ADR 0054 決定 19)。

    **刻意不重用 `OpksEntityKind`** —— 那個 enum 含 `attitude`,而態度掛文件、
    不由 per-Task specialist 產生缺口(ADR 0048 決定 5)。重用會讓「不含態度」
    這條變成呼叫端要記得的約定,而不是型別本身擋得住的事。
    """

    OUTPUT = "output"
    INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"


class OpenIssueTerminalResolutionKind(StrEnum):
    """員工對這個缺口給出的終端回答(ADR 0054 決定 22、24)。

    **兩個值都是員工的回答。** Task 被刪除／撤回／合併／拆分時員工並沒有回答任何
    事,不得借用它們把「這筆 gap 不該再存在」寫成一筆假的員工回答——那條路徑是
    直接移除(計畫 T13)。
    """

    EMPLOYEE_UNKNOWN = "employee_unknown"
    NOT_APPLICABLE = "not_applicable"


class OpenIssueTerminalResolution(DomainModel):
    """終結一筆 gap 的回答與其來源。

    決定 19:kind 與 source_ref **合併為單一物件**,兩個平行 optional 欄位遲早失步
    (一個有值一個沒有時,`is_active` 要信哪一個沒有答案)。
    """

    kind: OpenIssueTerminalResolutionKind
    source_ref: SourceRef


class ExclusionReason(StrEnum):
    OTHER_PERSON_WORK = "他人工作"
    PAST_WORK = "過去工作"
    ONE_OFF_SUPPORT = "一次性支援"
    ENABLER_OR_STEP = "工具或步驟"
    EMPLOYEE_DENIED = "員工否認"


class OpenIssue(DomainModel):
    id: Identifier
    kind: OpenIssueKind
    summary: NonEmptyText
    source_anchors: tuple[SourceAnchor, ...]
    last_asked_turn_id: Identifier | None = None
    reconciliation_task_id: TaskId | None = None

    subject_task_id: TaskId | None = None
    """這筆 OPKS 缺口在問哪一個 Task(決定 19)。

    **不得挪用 `reconciliation_task_id`** —— 那個欄位表達的是「員工直接新增的
    Task 還沒被分析對齊」,與「已成立的 Task 缺某一軸的依據」是兩件事,合用會讓
    reconciliation 流程把 gap 當成待對齊 Task 處理。
    """

    opks_axis: OpksGapAxis | None = None
    terminal_resolution: OpenIssueTerminalResolution | None = None

    @property
    def is_active(self) -> bool:
        """決定 20:active issue ≡ `terminal_resolution is None`。

        只有 active issue 能進 agenda、取得 ordinal、被 `issue_resolutions[]` 指向、
        阻擋 OPKS pre-gate。判斷 active **一律走這個 property**,不要在呼叫端各自
        寫 `terminal_resolution is None`。
        """

        return self.terminal_resolution is None

    @model_validator(mode="after")
    def opks_axis_requires_a_subject_task(self):
        if self.opks_axis is not None and self.subject_task_id is None:
            raise ValueError("opks_axis requires subject_task_id")
        return self

    @model_validator(mode="after")
    def anchor_count_matches_kind(self):
        """§9.5:每筆 open issue ≥1 anchor;`矛盾未解` ≥2(矛盾至少要有兩邊)。"""
        if not self.source_anchors:
            raise ValueError("open issue requires at least one source anchor")
        if (
            self.kind is OpenIssueKind.UNRESOLVED_CONTRADICTION
            and len(self.source_anchors) < 2
        ):
            raise ValueError("矛盾未解 requires at least two source anchors")
        return self


class ExcludedSignal(DomainModel):
    id: Identifier
    reason: ExclusionReason
    summary: NonEmptyText
    source_anchors: tuple[SourceAnchor, ...]

    @model_validator(mode="after")
    def requires_one_anchor(self):
        if not self.source_anchors:
            raise ValueError("excluded signal requires at least one source anchor")
        return self


class CurrentWorkModel(DomainModel):
    tasks: tuple[Task, ...] = ()
    open_issues: tuple[OpenIssue, ...] = ()
    excluded_signals: tuple[ExcludedSignal, ...] = ()

    def task_by_id(self, task_id: str) -> Task | None:
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    @model_validator(mode="after")
    def identifiers_are_unique(self):
        for label, values in (
            ("task", [task.task_id for task in self.tasks]),
            ("open issue", [issue.id for issue in self.open_issues]),
            ("excluded signal", [signal.id for signal in self.excluded_signals]),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"duplicate {label} id")
        return self

    @model_validator(mode="after")
    def lineage_targets_exist_and_do_not_cycle(self):
        """§9.5:``merged_into``／``split_from`` 目標必須存在且不得成 cycle。

        兩個欄位合起來就是 lineage 圖的邊(merge 指向存續者、split 指向母 Task),
        環出現在哪一種邊上都一樣讓 reconcile 無限繞,所以一起走訪。
        """
        known = {task.task_id for task in self.tasks}
        edges: dict[str, set[str]] = {}
        for task in self.tasks:
            targets = {
                target
                for target in (task.merged_into, task.split_from)
                if target is not None
            }
            for target in targets:
                if target not in known:
                    raise ValueError(f"lineage target {target!r} does not exist")
            edges[task.task_id] = targets

        visiting: set[str] = set()
        settled: set[str] = set()

        def walk(node: str) -> None:
            if node in settled:
                return
            if node in visiting:
                raise ValueError(f"lineage cycle through {node!r}")
            visiting.add(node)
            for target in edges.get(node, ()):
                walk(target)
            visiting.discard(node)
            settled.add(node)

        for task_id in edges:
            walk(task_id)
        return self
