"""Pure deterministic checks for normalized R1 Task Discovery results."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from .contracts import (
    ClaimKind,
    ConsultantContract,
    Identifier,
    OwnershipScope,
    Polarity,
    ShortText,
    SourceSpan,
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
    TimeScope,
    TranscriptRole,
    Typicality,
    TurnUnderstandInput,
    TurnUnderstandOutput,
)


class VerificationIssueCode(StrEnum):
    SOURCE_MESSAGE_MISSING = "source_message_missing"
    SPAN_OUT_OF_BOUNDS = "span_out_of_bounds"
    SPAN_QUOTE_MISMATCH = "span_quote_mismatch"
    REFERENCE_MISSING = "reference_missing"
    CORRECTION_TARGET_MISSING = "correction_target_missing"
    SUPERSEDED_CLAIM_SUPPORT = "superseded_claim_support"
    DISQUALIFIED_TASK_SUPPORT = "disqualified_task_support"
    DUPLICATE_ID = "duplicate_id"
    DUPLICATE_RELATION = "duplicate_relation"
    REPEATED_QUESTION = "repeated_question"


class VerificationIssue(ConsultantContract):
    code: VerificationIssueCode
    path: ShortText
    entity_id: Identifier | None
    message: ShortText


class VerificationReport(ConsultantContract):
    schema_version: Literal["task_discovery_verification_report.v1"]
    issues: tuple[VerificationIssue, ...]

    @property
    def passed(self) -> bool:
        return not self.issues


def _issue(
    code: VerificationIssueCode,
    path: str,
    entity_id: str | None,
    message: str,
) -> VerificationIssue:
    return VerificationIssue(
        code=code, path=path, entity_id=entity_id, message=message
    )


def _verify_span(
    span: SourceSpan,
    *,
    path: str,
    entity_id: str,
    messages: dict[str, str],
) -> list[VerificationIssue]:
    text = messages.get(span.message_id)
    if text is None:
        return [
            _issue(
                VerificationIssueCode.SOURCE_MESSAGE_MISSING,
                path,
                entity_id,
                "source span references an unknown employee message",
            )
        ]
    if span.end > len(text):
        return [
            _issue(
                VerificationIssueCode.SPAN_OUT_OF_BOUNDS,
                path,
                entity_id,
                "source span is outside the employee message",
            )
        ]
    if text[span.start : span.end] != span.quote:
        return [
            _issue(
                VerificationIssueCode.SPAN_QUOTE_MISMATCH,
                path,
                entity_id,
                "source span quote does not match the employee message",
            )
        ]
    return []


def _has_duplicates(values: tuple[str, ...]) -> bool:
    return len(set(values)) != len(values)


def _check_unique_ids(
    values: tuple[str, ...], *, path: str
) -> list[VerificationIssue]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return [
        _issue(
            VerificationIssueCode.DUPLICATE_ID,
            path,
            value,
            "entity identifier appears more than once in its collection",
        )
        for value in sorted(duplicates)
    ]


def _check_references(
    values: tuple[str, ...],
    *,
    known: set[str],
    path: str,
    entity_id: str | None,
    relation: str,
) -> list[VerificationIssue]:
    return [
        _issue(
            VerificationIssueCode.REFERENCE_MISSING,
            path,
            entity_id,
            f"{relation} references unknown entity {value}",
        )
        for value in values
        if value not in known
    ]


def _normalized_question(value: str) -> str:
    compact = "".join(value.split()).casefold()
    return compact.rstrip("?？。.!！")


def _report(issues: list[VerificationIssue]) -> VerificationReport:
    ordered = tuple(
        sorted(
            issues,
            key=lambda item: (item.code.value, item.path, item.entity_id or ""),
        )
    )
    return VerificationReport(
        schema_version="task_discovery_verification_report.v1", issues=ordered
    )


def verify_turn_understand(
    source: TurnUnderstandInput, result: TurnUnderstandOutput
) -> VerificationReport:
    """Verify a stage-one result before it can enter reconciliation."""

    messages = {source.employee_message.message_id: source.employee_message.text}
    messages.update(
        {
            turn.turn_id: turn.text
            for turn in source.recent_transcript
            if turn.role is TranscriptRole.EMPLOYEE
        }
    )
    all_claims = (*source.prior_claims, *result.claims)
    claim_ids = {claim.claim_id for claim in all_claims}
    issues = _check_unique_ids(
        tuple(claim.claim_id for claim in all_claims), path="claims"
    )
    issues.extend(
        _check_unique_ids(
            tuple(signal.signal_id for signal in result.unmapped_signals),
            path="unmapped_signals",
        )
    )
    for claim in result.claims:
        for index, span in enumerate(claim.anchors):
            issues.extend(
                _verify_span(
                    span,
                    path=f"claims/{claim.claim_id}/anchors/{index}",
                    entity_id=claim.claim_id,
                    messages=messages,
                )
            )
        if (
            claim.kind is ClaimKind.CORRECTION
            and claim.correction_target_claim_id not in claim_ids
        ):
            issues.append(
                _issue(
                    VerificationIssueCode.CORRECTION_TARGET_MISSING,
                    f"claims/{claim.claim_id}/correction_target_claim_id",
                    claim.claim_id,
                    "correction references an unknown claim",
                )
            )
    for signal in result.unmapped_signals:
        for index, span in enumerate(signal.anchors):
            issues.extend(
                _verify_span(
                    span,
                    path=f"unmapped_signals/{signal.signal_id}/anchors/{index}",
                    entity_id=signal.signal_id,
                    messages=messages,
                )
            )
    return _report(issues)


def verify_task_discovery(
    source: TaskDiscoveryInput, result: TaskDiscoveryOutput
) -> VerificationReport:
    """Verify cross-object facts that Pydantic shape validation cannot see."""

    messages = {source.employee_message.message_id: source.employee_message.text}
    messages.update(
        {
            turn.turn_id: turn.text
            for turn in source.recent_transcript
            if turn.role is TranscriptRole.EMPLOYEE
        }
    )
    issues: list[VerificationIssue] = []
    all_claims = (*source.prior_claims, *result.claims)
    all_stories = (*source.prior_stories, *result.stories)
    all_work_units = (*source.prior_work_units, *result.work_units)
    all_tasks = (*source.existing_task_candidates, *result.task_candidates)
    claim_ids = {claim.claim_id for claim in all_claims}
    story_ids = {story.story_id for story in all_stories}
    work_unit_ids = {work.work_unit_id for work in all_work_units}
    task_ids = {task.candidate_id for task in all_tasks}
    claim_by_id = {claim.claim_id: claim for claim in all_claims}
    superseded_claim_ids: set[str] = set()

    issues.extend(
        _check_unique_ids(
            tuple(claim.claim_id for claim in all_claims), path="claims"
        )
    )
    issues.extend(
        _check_unique_ids(
            tuple(signal.signal_id for signal in result.unmapped_signals),
            path="unmapped_signals",
        )
    )
    issues.extend(
        _check_unique_ids(
            tuple(story.story_id for story in all_stories), path="stories"
        )
    )
    issues.extend(
        _check_unique_ids(
            tuple(work.work_unit_id for work in all_work_units), path="work_units"
        )
    )
    issues.extend(
        _check_unique_ids(
            tuple(task.candidate_id for task in all_tasks), path="task_candidates"
        )
    )
    issues.extend(
        _check_unique_ids(
            tuple(decision.decision_id for decision in result.decisions),
            path="decisions",
        )
    )

    # Historical claims are already accepted state and their source turns may be
    # outside this bounded packet. Only newly returned anchors can be checked here.
    for claim in result.claims:
        for index, span in enumerate(claim.anchors):
            issues.extend(
                _verify_span(
                    span,
                    path=f"claims/{claim.claim_id}/anchors/{index}",
                    entity_id=claim.claim_id,
                    messages=messages,
                )
            )
    for claim in all_claims:
        if claim.kind is ClaimKind.CORRECTION:
            target = claim.correction_target_claim_id
            if target not in claim_ids and claim in result.claims:
                issues.append(
                    _issue(
                        VerificationIssueCode.CORRECTION_TARGET_MISSING,
                        f"claims/{claim.claim_id}/correction_target_claim_id",
                        claim.claim_id,
                        "correction references an unknown claim",
                    )
                )
            elif target is not None:
                superseded_claim_ids.add(target)
    for signal in result.unmapped_signals:
        for index, span in enumerate(signal.anchors):
            issues.extend(
                _verify_span(
                    span,
                    path=f"unmapped_signals/{signal.signal_id}/anchors/{index}",
                    entity_id=signal.signal_id,
                    messages=messages,
                )
            )
    for story in result.stories:
        if _has_duplicates(story.claim_ids):
            issues.append(
                _issue(
                    VerificationIssueCode.DUPLICATE_RELATION,
                    f"stories/{story.story_id}/claim_ids",
                    story.story_id,
                    "relation contains a duplicate reference",
                )
            )
        issues.extend(
            _check_references(
                story.claim_ids,
                known=claim_ids,
                path=f"stories/{story.story_id}/claim_ids",
                entity_id=story.story_id,
                relation="story",
            )
        )

    for work in result.work_units:
        relations = {
            "claim_ids": work.claim_ids,
            "story_ids": work.story_ids,
            "support_claim_ids": work.support_claim_ids,
            "counter_claim_ids": work.counter_claim_ids,
        }
        for name, values in relations.items():
            if _has_duplicates(values):
                issues.append(
                    _issue(
                        VerificationIssueCode.DUPLICATE_RELATION,
                        f"work_units/{work.work_unit_id}/{name}",
                        work.work_unit_id,
                        "relation contains a duplicate reference",
                    )
                )
        for name in ("claim_ids", "support_claim_ids", "counter_claim_ids"):
            issues.extend(
                _check_references(
                    relations[name],
                    known=claim_ids,
                    path=f"work_units/{work.work_unit_id}/{name}",
                    entity_id=work.work_unit_id,
                    relation="work unit",
                )
            )
        issues.extend(
            _check_references(
                work.story_ids,
                known=story_ids,
                path=f"work_units/{work.work_unit_id}/story_ids",
                entity_id=work.work_unit_id,
                relation="work unit",
            )
        )

    for task in result.task_candidates:
        relations = {
            "work_unit_ids": task.work_unit_ids,
            "support_claim_ids": task.support_claim_ids,
            "counter_claim_ids": task.counter_claim_ids,
        }
        for name, values in relations.items():
            if _has_duplicates(values):
                issues.append(
                    _issue(
                        VerificationIssueCode.DUPLICATE_RELATION,
                        f"task_candidates/{task.candidate_id}/{name}",
                        task.candidate_id,
                        "relation contains a duplicate reference",
                    )
                )
        issues.extend(
            _check_references(
                task.work_unit_ids,
                known=work_unit_ids,
                path=f"task_candidates/{task.candidate_id}/work_unit_ids",
                entity_id=task.candidate_id,
                relation="task candidate",
            )
        )
        for name in ("support_claim_ids", "counter_claim_ids"):
            issues.extend(
                _check_references(
                    relations[name],
                    known=claim_ids,
                    path=f"task_candidates/{task.candidate_id}/{name}",
                    entity_id=task.candidate_id,
                    relation="task candidate",
                )
            )
        if any(
            claim_id in superseded_claim_ids for claim_id in task.support_claim_ids
        ):
            issues.append(
                _issue(
                    VerificationIssueCode.SUPERSEDED_CLAIM_SUPPORT,
                    f"task_candidates/{task.candidate_id}/support_claim_ids",
                    task.candidate_id,
                    "task candidate relies on a superseded claim",
                )
            )
        supports = [
            claim_by_id[claim_id]
            for claim_id in task.support_claim_ids
            if claim_id in claim_by_id
            and claim_id not in superseded_claim_ids
        ]
        eligible = [
            claim
            for claim in supports
            if claim.time_scope is TimeScope.CURRENT
            and claim.ownership
            in {
                OwnershipScope.EMPLOYEE_RESPONSIBLE,
                OwnershipScope.SHARED_RESPONSIBILITY,
                OwnershipScope.FORMAL_SUPPORT,
            }
            and claim.typicality is not Typicality.ONE_OFF
            and claim.polarity is Polarity.AFFIRMED
            and claim.kind not in {ClaimKind.TOOL_OR_METHOD, ClaimKind.STEP}
        ]
        if supports and not eligible:
            issues.append(
                _issue(
                    VerificationIssueCode.DISQUALIFIED_TASK_SUPPORT,
                    f"task_candidates/{task.candidate_id}/support_claim_ids",
                    task.candidate_id,
                    "task candidate has only disqualified positive support",
                )
            )

    for decision in result.decisions:
        if _has_duplicates(decision.existing_candidate_ids):
            issues.append(
                _issue(
                    VerificationIssueCode.DUPLICATE_RELATION,
                    f"decisions/{decision.decision_id}/existing_candidate_ids",
                    decision.decision_id,
                    "relation contains a duplicate reference",
                )
            )
        if _has_duplicates(decision.work_unit_ids):
            issues.append(
                _issue(
                    VerificationIssueCode.DUPLICATE_RELATION,
                    f"decisions/{decision.decision_id}/work_unit_ids",
                    decision.decision_id,
                    "relation contains a duplicate reference",
                )
            )
        decision_task_ids = decision.existing_candidate_ids
        if decision.candidate_id is not None:
            decision_task_ids = (*decision_task_ids, decision.candidate_id)
        issues.extend(
            _check_references(
                decision_task_ids,
                known=task_ids,
                path=f"decisions/{decision.decision_id}/candidate_ids",
                entity_id=decision.decision_id,
                relation="reconciliation decision",
            )
        )
        issues.extend(
            _check_references(
                decision.work_unit_ids,
                known=work_unit_ids,
                path=f"decisions/{decision.decision_id}/work_unit_ids",
                entity_id=decision.decision_id,
                relation="reconciliation decision",
            )
        )

    issues.extend(
        _check_references(
            result.next_question.claim_ids,
            known=claim_ids,
            path="next_question/claim_ids",
            entity_id=None,
            relation="next question",
        )
    )

    normalized = _normalized_question(result.next_question.text)
    previous_questions = source.recent_questions
    if source.question_context is not None:
        previous_questions = (
            *previous_questions,
            source.question_context.question_text,
        )
    if normalized in {_normalized_question(text) for text in previous_questions}:
        issues.append(
            _issue(
                VerificationIssueCode.REPEATED_QUESTION,
                "next_question/text",
                None,
                "next question exactly repeats a recent question",
            )
        )

    return _report(issues)
