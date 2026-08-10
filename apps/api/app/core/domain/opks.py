"""Current JD 的 O/P/K/S/A 值物件（ADR 0048、0049）。"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from .base import DomainModel, Identifier, NonEmptyText, TaskId
from .sources import SourceAnchor, SourceKind


_EVIDENCE_ORIGIN_BY_SOURCE_KIND: dict[
    SourceKind, Literal["employee"]
] = {
    SourceKind.EMPLOYEE_TURN: "employee",
    SourceKind.DIRECT_EDIT: "employee",
}


class OpksEntityKind(StrEnum):
    OUTPUT = "output"
    INDICATOR = "indicator"
    KNOWLEDGE = "knowledge"
    SKILL = "skill"
    ATTITUDE = "attitude"


class OpksEvidenceLink(SourceAnchor):
    """OPKS 的員工 Evidence；Proposal decision 本身不是工作證據。"""

    @model_validator(mode="after")
    def source_is_employee_evidence(self):
        if self.source_ref.kind not in _EVIDENCE_ORIGIN_BY_SOURCE_KIND:
            raise ValueError("OPKS evidence must be employee_turn or direct_edit")
        return self


class OpksItem(DomainModel):
    entity_id: Identifier
    entity_kind: OpksEntityKind
    text: NonEmptyText
    display_order: int = Field(default=0, ge=0)
    task_refs: tuple[TaskId, ...] = ()
    indicator_refs: tuple[Identifier, ...] = ()
    evidence_links: tuple[OpksEvidenceLink, ...]

    @property
    def task_linkage(self) -> Literal["linked", "unlinked"]:
        return "linked" if self.task_refs or self.indicator_refs else "unlinked"

    @property
    def evidence_origins(self) -> frozenset[Literal["employee"]]:
        return frozenset(
            _EVIDENCE_ORIGIN_BY_SOURCE_KIND[link.source_ref.kind]
            for link in self.evidence_links
        )

    @model_validator(mode="after")
    def evidence_is_not_empty(self):
        if not self.evidence_links:
            raise ValueError("OPKS item requires at least one evidence link")
        return self

    @model_validator(mode="after")
    def references_are_unique(self):
        for label, refs in (
            ("task_refs", self.task_refs),
            ("indicator_refs", self.indicator_refs),
        ):
            if len(set(refs)) != len(refs):
                raise ValueError(f"duplicate {label}")
        return self

    @model_validator(mode="after")
    def references_match_entity_kind(self):
        if self.entity_kind in {
            OpksEntityKind.OUTPUT,
            OpksEntityKind.INDICATOR,
        }:
            if len(self.task_refs) != 1:
                raise ValueError(
                    f"{self.entity_kind.value} must reference exactly one task"
                )
            if self.indicator_refs:
                raise ValueError(
                    f"{self.entity_kind.value} must not reference indicators"
                )
        elif self.entity_kind is OpksEntityKind.ATTITUDE and (
            self.task_refs or self.indicator_refs
        ):
            raise ValueError("attitude must not carry references")
        return self


class CurrentJdOpks(DomainModel):
    items: tuple[OpksItem, ...] = ()

    def item_by_id(self, entity_id: str) -> OpksItem | None:
        for item in self.items:
            if item.entity_id == entity_id:
                return item
        return None

    def validate_against_tasks(
        self, current_jd_task_ids: frozenset[TaskId]
    ) -> None:
        unknown = sorted(
            {
                task_id
                for item in self.items
                for task_id in item.task_refs
                if task_id not in current_jd_task_ids
            }
        )
        if unknown:
            raise ValueError(f"unknown Current JD task refs: {unknown}")

    @model_validator(mode="after")
    def entity_ids_are_unique(self):
        ids = [item.entity_id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate OPKS entity id")
        return self

    @model_validator(mode="after")
    def display_orders_are_unique_within_entity_kind(self):
        seen: set[tuple[OpksEntityKind, int]] = set()
        for item in self.items:
            key = (item.entity_kind, item.display_order)
            if key in seen:
                raise ValueError(
                    "duplicate OPKS display order within entity kind"
                )
            seen.add(key)
        return self

    def next_display_order(self, entity_kind: OpksEntityKind) -> int:
        return max(
            (
                item.display_order
                for item in self.items
                if item.entity_kind is entity_kind
            ),
            default=-1,
        ) + 1

    @model_validator(mode="after")
    def indicator_refs_target_indicators(self):
        by_id = {item.entity_id: item for item in self.items}
        for item in self.items:
            for indicator_id in item.indicator_refs:
                target = by_id.get(indicator_id)
                if target is None:
                    raise ValueError(f"unknown indicator ref {indicator_id!r}")
                if target.entity_kind is not OpksEntityKind.INDICATOR:
                    raise ValueError(
                        f"indicator ref {indicator_id!r} must identify an indicator"
                    )
        return self
