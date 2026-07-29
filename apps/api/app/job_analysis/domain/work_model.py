"""Current Work Model 的 Task Analysis slice(§9.1)。

本模組只涵蓋 Task／open issue／excluded signal;角色假說、coverage、current focus、
active question、conversation 與 Product Proposal 由後續垂直切片定義(§9 前言)。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import model_validator

from .base import DomainModel, Identifier, NonEmptyText
from .sources import SourceAnchor
from .task import Task


class OpenIssueKind(StrEnum):
    RESPONSIBILITY_UNCLEAR = "責任邊界不明"
    INSUFFICIENT_EVIDENCE = "證據不足"
    UNRESOLVED_CONTRADICTION = "矛盾未解"
    TASK_BOUNDARY_UNCERTAIN = "task_boundary_uncertain"


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
