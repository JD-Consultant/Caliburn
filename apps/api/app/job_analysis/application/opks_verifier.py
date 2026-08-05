"""OPKS v1 的 deterministic verifier 與 proposal candidate mapping。"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from app.job_analysis.domain import (
    DomainModel,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksGapAxis,
    OpksItem,
    OpksProposalAction,
)
from app.job_analysis.llm import OpksDecision, OpksResult, OpksResultItem

from .opks_context import OpksContextPacket


class OpksViolationCode(StrEnum):
    DECISION_PAYLOAD_INVALID = "decision_payload_invalid"
    TARGET_ORDINAL_UNKNOWN = "target_ordinal_unknown"
    TARGET_NOT_RELATED_TO_SELECTED_TASK = "target_not_related_to_selected_task"
    DUPLICATE_TARGET = "duplicate_target"
    DUPLICATE_ADD_CANDIDATE = "duplicate_add_candidate"


class OpksViolation(DomainModel):
    code: OpksViolationCode
    item_index: int
    message: str


class VerifiedOpksChange(DomainModel):
    source_index: int
    action: OpksProposalAction
    entity_id: str
    entity_kind: OpksEntityKind
    before: OpksItem | None = None
    after: OpksItem | None = None


class OpksGap(DomainModel):
    """specialist 說「這一軸的依據不足」(ADR 0054 決定 15)。

    **不帶問句。** 問句在提問當下由主顧問生成——gap 在 T0 寫成、T1 才問出口,中間
    上下文已變;而且這讓「不得把 K/S 問成認領題」(0048 決定 14)只住主顧問 prompt
    一處,不必在兩個地方各維護一次。
    """

    source_index: int
    axis: OpksGapAxis
    summary: str


class OpksVerificationReport(DomainModel):
    violations: tuple[OpksViolation, ...] = ()
    changes: tuple[VerifiedOpksChange, ...] = ()
    gaps: tuple[OpksGap, ...] = ()

    @property
    def is_valid(self) -> bool:
        return not self.violations


def _domain_kind(item: OpksResultItem) -> OpksEntityKind:
    return OpksEntityKind(item.entity_kind.value)


def _payload_is_valid(item: OpksResultItem) -> bool:
    has_target = item.target_ordinal is not None
    has_text = item.text is not None
    return {
        OpksDecision.ADD_NEW: not has_target and has_text,
        OpksDecision.REUSE_EXISTING: (
            item.entity_kind.value in {"knowledge", "skill"}
            and has_target
            and not has_text
        ),
        OpksDecision.REVISE_EXISTING: has_target and has_text,
        OpksDecision.REMOVE_EXISTING: has_target and not has_text,
        # 決定 15:`uncertain` 的 `text` 從強制空字串改為**強制非空的缺口摘要**。
        # 缺口因此在契約層第一次有形狀,不再是被 verifier 丟掉的一個字。
        OpksDecision.UNCERTAIN: not has_target and has_text,
    }[item.decision]


def _employee_evidence(packet: OpksContextPacket) -> tuple[OpksEvidenceLink, ...]:
    return tuple(
        OpksEvidenceLink(
            source_ref=view.support_link.source_ref,
            quote=view.support_link.quote,
            question_turn_id=view.support_link.question_turn_id,
        )
        for view in packet.evidence
    )


def _append_unique(values: tuple[str, ...], value: str) -> tuple[str, ...]:
    return values if value in values else (*values, value)


def _merge_evidence(
    existing: tuple[OpksEvidenceLink, ...],
    incoming: tuple[OpksEvidenceLink, ...],
) -> tuple[OpksEvidenceLink, ...]:
    merged = list(existing)
    for link in incoming:
        if link not in merged:
            merged.append(link)
    return tuple(merged)


def _add_change(
    packet: OpksContextPacket,
    item: OpksResultItem,
    *,
    operation_id: str,
    item_index: int,
    evidence: tuple[OpksEvidenceLink, ...],
) -> VerifiedOpksChange:
    kind = _domain_kind(item)
    prefix = {
        OpksEntityKind.OUTPUT: "o",
        OpksEntityKind.INDICATOR: "p",
        OpksEntityKind.KNOWLEDGE: "k",
        OpksEntityKind.SKILL: "s",
    }[kind]
    entity_id = f"{operation_id}-{prefix}{item_index}"
    candidate = OpksItem(
        entity_id=entity_id,
        entity_kind=kind,
        text=item.text,
        task_refs=(packet.selected_task.task.task_id,),
        indicator_refs=(),
        evidence_links=evidence,
    )
    return VerifiedOpksChange(
        source_index=item_index,
        action=OpksProposalAction.ADD,
        entity_id=entity_id,
        entity_kind=kind,
        after=candidate,
    )


def _reuse_or_revise_change(
    packet: OpksContextPacket,
    item: OpksResultItem,
    before: OpksItem,
    *,
    item_index: int,
    evidence: tuple[OpksEvidenceLink, ...],
) -> VerifiedOpksChange | None:
    after = before.model_copy(
        update={
            "text": item.text if item.text is not None else before.text,
            "task_refs": _append_unique(
                before.task_refs, packet.selected_task.task.task_id
            ),
            "evidence_links": _merge_evidence(before.evidence_links, evidence),
        }
    )
    if after == before:
        return None
    return VerifiedOpksChange(
        source_index=item_index,
        action=OpksProposalAction.REVISE,
        entity_id=before.entity_id,
        entity_kind=before.entity_kind,
        before=before,
        after=after,
    )


def _remove_change(
    packet: OpksContextPacket,
    before: OpksItem,
    *,
    item_index: int,
) -> VerifiedOpksChange:
    if before.entity_kind in {
        OpksEntityKind.OUTPUT,
        OpksEntityKind.INDICATOR,
    }:
        return VerifiedOpksChange(
            source_index=item_index,
            action=OpksProposalAction.REMOVE,
            entity_id=before.entity_id,
            entity_kind=before.entity_kind,
            before=before,
        )

    selected_task_id = packet.selected_task.task.task_id
    selected_indicator_ids = frozenset(
        view.item.entity_id for view in packet.indicators
    )
    after = before.model_copy(
        update={
            "task_refs": tuple(
                ref for ref in before.task_refs if ref != selected_task_id
            ),
            "indicator_refs": tuple(
                ref
                for ref in before.indicator_refs
                if ref not in selected_indicator_ids
            ),
        }
    )
    return VerifiedOpksChange(
        source_index=item_index,
        action=OpksProposalAction.REVISE,
        entity_id=before.entity_id,
        entity_kind=before.entity_kind,
        before=before,
        after=after,
    )


def verify_opks_result(
    packet: OpksContextPacket,
    result: OpksResult,
    *,
    operation_id: str,
) -> OpksVerificationReport:
    """驗證整批結果；任一機械違規即不回傳部分 changes。"""

    violations: list[OpksViolation] = []
    candidates: list[VerifiedOpksChange] = []
    gaps: list[OpksGap] = []
    seen_targets: set[tuple[OpksEntityKind, int]] = set()
    seen_add_candidates = {
        (kind, view.item.text.strip())
        for kind in OpksEntityKind
        for view in packet.items_for(kind)
    }
    selected_task_id = packet.selected_task.task.task_id
    selected_indicator_ids = frozenset(
        view.item.entity_id for view in packet.indicators
    )
    evidence = _employee_evidence(packet)

    for item_index, item in enumerate(result.items):
        if not _payload_is_valid(item):
            violations.append(
                OpksViolation(
                    code=OpksViolationCode.DECISION_PAYLOAD_INVALID,
                    item_index=item_index,
                    message=f"{item.decision.value} payload does not match its mapping",
                )
            )
            continue

        if item.decision is OpksDecision.UNCERTAIN:
            gaps.append(
                OpksGap(
                    source_index=item_index,
                    axis=OpksGapAxis(item.entity_kind.value),
                    summary=cast(str, item.text),
                )
            )
            continue
        if item.decision is OpksDecision.ADD_NEW:
            add_text = cast(str, item.text)  # _payload_is_valid() above proved non-null.
            add_key = (_domain_kind(item), add_text.strip())
            if add_key in seen_add_candidates:
                violations.append(
                    OpksViolation(
                        code=OpksViolationCode.DUPLICATE_ADD_CANDIDATE,
                        item_index=item_index,
                        message=(
                            "the same entity kind and exact add text already "
                            "exists or appears more than once"
                        ),
                    )
                )
                continue
            seen_add_candidates.add(add_key)
            candidates.append(
                _add_change(
                    packet,
                    item,
                    operation_id=operation_id,
                    item_index=item_index,
                    evidence=evidence,
                )
            )
            continue

        kind = _domain_kind(item)
        target_ordinal = item.target_ordinal
        assert target_ordinal is not None
        target_key = (kind, target_ordinal)
        duplicate = target_key in seen_targets
        seen_targets.add(target_key)
        if duplicate:
            violations.append(
                OpksViolation(
                    code=OpksViolationCode.DUPLICATE_TARGET,
                    item_index=item_index,
                    message="the same OPKS target appears more than once",
                )
            )
            continue

        target_view = packet.item_view(kind, target_ordinal)
        if target_view is None:
            violations.append(
                OpksViolation(
                    code=OpksViolationCode.TARGET_ORDINAL_UNKNOWN,
                    item_index=item_index,
                    message="target ordinal does not exist in this entity-kind namespace",
                )
            )
            continue
        before = target_view.item

        if kind in {OpksEntityKind.OUTPUT, OpksEntityKind.INDICATOR} and (
            before.task_refs != (selected_task_id,)
        ):
            violations.append(
                OpksViolation(
                    code=OpksViolationCode.TARGET_NOT_RELATED_TO_SELECTED_TASK,
                    item_index=item_index,
                    message="output or indicator target does not belong to selected task",
                )
            )
            continue

        if item.decision is OpksDecision.REMOVE_EXISTING:
            related = selected_task_id in before.task_refs or bool(
                selected_indicator_ids.intersection(before.indicator_refs)
            )
            if kind in {OpksEntityKind.KNOWLEDGE, OpksEntityKind.SKILL} and not related:
                violations.append(
                    OpksViolation(
                        code=OpksViolationCode.TARGET_NOT_RELATED_TO_SELECTED_TASK,
                        item_index=item_index,
                        message="knowledge or skill target is unrelated to selected task",
                    )
                )
                continue
            candidates.append(_remove_change(packet, before, item_index=item_index))
            continue

        change = _reuse_or_revise_change(
            packet,
            item,
            before,
            item_index=item_index,
            evidence=evidence,
        )
        if change is not None:
            candidates.append(change)

    if violations:
        return OpksVerificationReport(violations=tuple(violations))
    # 決定 18:效力單位是 item。有依據的候選照常提案,同時保留其他軸的缺口——
    # 不做同軸一律扣住,也不做整個 Task 扣住。
    return OpksVerificationReport(changes=tuple(candidates), gaps=tuple(gaps))
