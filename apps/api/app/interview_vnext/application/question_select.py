"""Projection, semantic verification, and command materialization for question.select."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID, uuid5

from app.interview_vnext.domain.commands import (
    AppendConsultantQuestionCommand,
    OpenEpisodeCommand,
    TransitionGapCommand,
)
from app.interview_vnext.domain.episode import GapDimension, GapStatus
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.question_frame import (
    QuestionMode,
    QuestionSlotKind,
    QuestionSourceKind,
    QuestionSourceRef,
    build_question_frame_definition,
    build_slot_target,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.llm.context import (
    INJECTION_BOUNDARY,
    QuestionSelectContextPacket,
)
from app.interview_vnext.llm.question_select import (
    QuestionSelectAction,
    QuestionSelectInput,
    QuestionSelectInputCandidate,
    QuestionSelectInputEpisode,
    QuestionSelectInputEvidence,
    QuestionSelectInputJobDigest,
    QuestionSelectInputTask,
    QuestionSelectInputTurn,
    QuestionSelectOutput,
    QuestionSelectRejectCode,
    QuestionSelectVerificationReport,
)


@dataclass(frozen=True)
class QuestionSelectProjection:
    input: QuestionSelectInput
    candidate_keys: tuple[str, ...]
    candidate_existing_gap_ids: tuple[UUID | None, ...]
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class QuestionSelectionPlan:
    """Existing domain commands in their required sequential reducer order."""

    display_text: str
    verification_report: QuestionSelectVerificationReport
    append_question: AppendConsultantQuestionCommand
    transition_gap: TransitionGapCommand | None = None
    open_episode: OpenEpisodeCommand | None = None

    @property
    def commands(self) -> tuple:
        tail = tuple(
            item
            for item in (self.transition_gap, self.open_episode)
            if item is not None
        )
        return (self.append_question, *tail)


class QuestionSelectionRejected(ValueError):
    def __init__(self, report: QuestionSelectVerificationReport) -> None:
        super().__init__(
            "question.select output failed semantic verification: "
            + ",".join(item.value for item in report.reason_codes)
        )
        self.report = report


def question_select_projection(
    context: QuestionSelectContextPacket,
) -> QuestionSelectProjection:
    context = QuestionSelectContextPacket.model_validate(context.model_dump())
    evidence_ordinals = {
        item.evidence.evidence_id: ordinal
        for ordinal, item in enumerate(context.supporting_evidence, 1)
    }
    digest = context.job_state_digest
    payload = QuestionSelectInput(
        input_boundary=INJECTION_BOUNDARY,
        latest_employee_turn=(
            QuestionSelectInputTurn(
                sequence=context.latest_employee_turn.sequence,
                locale=context.latest_employee_turn.locale,
                text=context.latest_employee_turn.text,
            )
            if context.latest_employee_turn is not None
            else None
        ),
        recent_consultant_question=(
            context.recent_consultant_question.text
            if context.recent_consultant_question is not None
            else None
        ),
        active_episode=(
            QuestionSelectInputEpisode(
                target=context.active_episode.target,
                status=context.active_episode.status,
            )
            if context.active_episode is not None
            else None
        ),
        candidates=tuple(
            QuestionSelectInputCandidate(
                ordinal=item.ordinal,
                dimension=item.dimension,
                question_goal=item.question_goal,
                supporting_evidence_ordinals=tuple(
                    sorted(
                        evidence_ordinals[evidence_id]
                        for evidence_id in item.supporting_evidence_ids
                    )
                ),
                existing_gap=item.existing_gap_id is not None,
            )
            for item in context.agenda_candidates
        ),
        supporting_evidence=tuple(
            QuestionSelectInputEvidence(
                ordinal=ordinal,
                kind=item.evidence.kind,
                claim=item.evidence.claim,
            )
            for ordinal, item in enumerate(context.supporting_evidence, 1)
        ),
        job_state=QuestionSelectInputJobDigest(
            job_title=digest.job_title,
            tasks=tuple(
                QuestionSelectInputTask(
                    ordinal=item.ordinal,
                    statement_excerpt=item.statement_excerpt,
                    output_excerpts=item.output_excerpts,
                )
                for item in digest.tasks
            ),
            omitted_task_count=digest.omitted_task_count,
            pending_proposal_count=digest.pending_proposal_count,
            stale_proposal_count=digest.stale_proposal_count,
        ),
        allow_broaden_coverage=context.dialogue_limits.allow_broaden_coverage,
        allow_offer_finish=context.dialogue_limits.allow_offer_finish,
        remaining_high_value_questions=(
            context.dialogue_limits.remaining_high_value_questions
        ),
    )
    return QuestionSelectProjection(
        input=payload,
        candidate_keys=tuple(
            item.stable_key for item in context.agenda_candidates
        ),
        candidate_existing_gap_ids=tuple(
            item.existing_gap_id for item in context.agenda_candidates
        ),
        evidence_ids=tuple(
            item.evidence.evidence_id for item in context.supporting_evidence
        ),
    )


def _comparison_text(value: str) -> str:
    """Normalize for repetition detection only; persisted text stays verbatim."""

    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(
        char
        for char in normalized
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def verify_question_select_output(
    *,
    output: QuestionSelectOutput,
    context: QuestionSelectContextPacket,
) -> QuestionSelectVerificationReport:
    output = QuestionSelectOutput.model_validate(output.model_dump())
    context = QuestionSelectContextPacket.model_validate(context.model_dump())
    reasons: set[QuestionSelectRejectCode] = set()

    if output.action == QuestionSelectAction.ASK_GAP:
        ordinal = output.selected_gap_ordinal
        if ordinal is None or ordinal > len(context.agenda_candidates):
            reasons.add(QuestionSelectRejectCode.GAP_ORDINAL_OUT_OF_RANGE)
    elif output.action == QuestionSelectAction.BROADEN_COVERAGE:
        if not context.dialogue_limits.allow_broaden_coverage:
            reasons.add(QuestionSelectRejectCode.ACTION_NOT_ALLOWED)
    elif not context.dialogue_limits.allow_offer_finish:
        reasons.add(QuestionSelectRejectCode.ACTION_NOT_ALLOWED)

    if context.recent_consultant_question is not None:
        previous = _comparison_text(context.recent_consultant_question.text)
        current = _comparison_text(output.question_text)
        if current == previous or (current and current in previous):
            reasons.add(QuestionSelectRejectCode.DUPLICATE_RECENT_QUESTION)
    if sum(output.question_text.count(mark) for mark in ("?", "？")) > 1:
        reasons.add(QuestionSelectRejectCode.QUESTION_LOOKS_COMPOUND)

    ordered = tuple(
        code for code in QuestionSelectRejectCode if code in reasons
    )
    return QuestionSelectVerificationReport(
        accepted=not ordered,
        action=output.action,
        selected_gap_ordinal=output.selected_gap_ordinal,
        reason_codes=ordered,
    )


def _source_refs(evidence: tuple[Evidence, ...]) -> tuple[QuestionSourceRef, ...]:
    return tuple(
        sorted(
            (
                QuestionSourceRef(
                    source_kind=QuestionSourceKind.EMPLOYEE_EVIDENCE,
                    source_ref=str(item.evidence_id),
                    source_hash=canonical_hash(item),
                )
                for item in evidence
            ),
            key=lambda item: (
                item.source_kind.value,
                item.source_ref,
                item.source_hash,
            ),
        )
    )


def _slot_frame(
    *,
    dimension: GapDimension,
    question_text: str,
    supporting_evidence: tuple[Evidence, ...],
):
    actions = tuple(
        item for item in supporting_evidence if item.kind == EvidenceKind.ACTION
    )
    outputs = tuple(
        item for item in supporting_evidence if item.kind == EvidenceKind.OUTPUT
    )
    base = (actions or outputs or supporting_evidence)
    if not base:
        return build_question_frame_definition(
            mode=QuestionMode.OPEN_NARRATIVE,
            question_text=question_text,
            targets=(),
        )
    anchor = base[0]
    refs = _source_refs(supporting_evidence)
    contextual_qualifiers = EvidenceQualifiers(
        time_scope=anchor.qualifiers.time_scope,
        polarity=anchor.qualifiers.polarity,
    )

    if dimension == GapDimension.OUTPUT_RECIPIENT:
        if outputs:
            target = build_slot_target(
                target_ordinal=1,
                slot_kind=QuestionSlotKind.RECIPIENT,
                subject=outputs[0].subject,
                evidence_kind=EvidenceKind.RECIPIENT,
                base_claim=outputs[0].claim,
                claim_template=f"{outputs[0].claim}，提供給{{value}}",
                base_qualifiers=contextual_qualifiers,
                source_refs=refs,
            )
        else:
            target = build_slot_target(
                target_ordinal=1,
                slot_kind=QuestionSlotKind.OUTPUT,
                subject=anchor.subject,
                evidence_kind=EvidenceKind.OUTPUT,
                base_claim=anchor.claim,
                claim_template="{value}",
                base_qualifiers=contextual_qualifiers,
                source_refs=refs,
            )
    elif dimension == GapDimension.PURPOSE:
        target = build_slot_target(
            target_ordinal=1,
            slot_kind=QuestionSlotKind.PURPOSE,
            subject=anchor.subject,
            evidence_kind=EvidenceKind.PURPOSE,
            base_claim=anchor.claim,
            claim_template=f"{anchor.claim}，目的是{{value}}",
            base_qualifiers=contextual_qualifiers,
            source_refs=refs,
        )
    elif dimension == GapDimension.STANDARD_RESULT:
        target = build_slot_target(
            target_ordinal=1,
            slot_kind=QuestionSlotKind.STANDARD,
            subject=anchor.subject,
            evidence_kind=EvidenceKind.STANDARD,
            base_claim=anchor.claim,
            claim_template=f"{anchor.claim}，完成標準是{{value}}",
            base_qualifiers=contextual_qualifiers,
            source_refs=refs,
        )
    else:
        return build_question_frame_definition(
            mode=QuestionMode.OPEN_NARRATIVE,
            question_text=question_text,
            targets=(),
        )
    return build_question_frame_definition(
        mode=QuestionMode.SLOT_REQUEST,
        question_text=question_text,
        targets=(target,),
    )


def materialize_question_selection(
    *,
    state: InterviewState,
    context: QuestionSelectContextPacket,
    output: QuestionSelectOutput,
    operation_id: UUID,
    occurred_at: datetime,
) -> QuestionSelectionPlan:
    """Turn a verified model choice into existing domain commands, without I/O."""

    state = InterviewState.model_validate(state.model_dump())
    context = QuestionSelectContextPacket.model_validate(context.model_dump())
    output = QuestionSelectOutput.model_validate(output.model_dump())
    if context.operation_id != operation_id:
        raise ValueError("operation_id does not match question context")
    if (
        context.state_version != state.session.state_version
        or context.state_hash != canonical_hash(state)
    ):
        raise ValueError("question context is stale")
    report = verify_question_select_output(output=output, context=context)
    if not report.accepted:
        raise QuestionSelectionRejected(report)

    display_text = (
        f"{output.acknowledgement.rstrip()}\n\n{output.question_text}"
        if output.acknowledgement.strip()
        else output.question_text
    )
    selected = (
        context.agenda_candidates[output.selected_gap_ordinal - 1]
        if output.action == QuestionSelectAction.ASK_GAP
        and output.selected_gap_ordinal is not None
        else None
    )
    evidence_by_id = {item.evidence_id: item for item in state.evidence}
    supporting_evidence = (
        tuple(
            evidence_by_id[evidence_id]
            for evidence_id in selected.supporting_evidence_ids
        )
        if selected is not None
        else ()
    )
    definition = (
        _slot_frame(
            dimension=selected.dimension,
            question_text=display_text,
            supporting_evidence=supporting_evidence,
        )
        if selected is not None
        else build_question_frame_definition(
            mode=QuestionMode.OPEN_NARRATIVE,
            question_text=display_text,
            targets=(),
        )
    )

    turn_id = uuid5(operation_id, "question.select/consultant-turn")
    append = AppendConsultantQuestionCommand(
        command_id=uuid5(operation_id, "question.select/append-question"),
        expected_state_version=state.session.state_version,
        occurred_at=occurred_at,
        turn=TranscriptTurn(
            turn_id=turn_id,
            session_id=state.session.session_id,
            client_turn_id=f"question-select/{operation_id}",
            sequence=len(state.turns) + 1,
            role=TranscriptRole.CONSULTANT,
            text=display_text,
            previous_turn_id=state.turns[-1].turn_id if state.turns else None,
            occurred_at=occurred_at,
            received_at=occurred_at,
        ),
        frame_definition=definition,
    )

    transition_gap = None
    if selected is not None and selected.existing_gap_id is not None:
        gap = next(
            (
                item
                for item in state.gaps
                if item.gap_id == selected.existing_gap_id
            ),
            None,
        )
        if gap is None or gap.status not in {GapStatus.OPEN, GapStatus.DEFERRED}:
            raise ValueError("selected existing gap is no longer askable")
        transition_gap = TransitionGapCommand(
            command_id=uuid5(operation_id, "question.select/mark-gap-asked"),
            expected_state_version=state.session.state_version + 1,
            occurred_at=occurred_at,
            gap_id=gap.gap_id,
            target_status=GapStatus.ASKED,
            source_turn_id=turn_id,
        )

    open_episode = None
    if (
        output.action == QuestionSelectAction.BROADEN_COVERAGE
        and state.session.active_episode_id is None
    ):
        open_episode = OpenEpisodeCommand(
            command_id=uuid5(operation_id, "question.select/open-episode"),
            expected_state_version=state.session.state_version + 1,
            occurred_at=occurred_at,
            episode_id=uuid5(operation_id, "question.select/episode"),
            target="下一項主要工作",
            opened_turn_id=turn_id,
        )

    return QuestionSelectionPlan(
        display_text=display_text,
        verification_report=report,
        append_question=append,
        transition_gap=transition_gap,
        open_episode=open_episode,
    )
