from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest

from app.interview_vnext.application.agenda import build_question_agenda
from app.interview_vnext.application.context_builder import ContextBuilder
from app.interview_vnext.application.question_select import (
    QuestionSelectionRejected,
    materialize_question_selection,
    question_select_projection,
    verify_question_select_output,
)
from app.interview_vnext.domain.episode import (
    EpisodeState,
    Gap,
    GapDimension,
    GapPriorityFeatures,
    ValueLevel,
)
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceSubject,
    Polarity,
    TimeScope,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.question_frame import (
    QuestionMode,
    QuestionSlotKind,
    SlotQuestionTarget,
)
from app.interview_vnext.domain.reducers import (
    append_consultant_question,
    open_episode,
    transition_gap,
)
from app.interview_vnext.domain.session import SessionStatus, session_at
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.support import (
    LiteralEmployeeSpanSupport,
    QuoteSpan,
)
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.domain.turn_identity import turn_interpretation_id
from app.interview_vnext.llm.context import QUESTION_SELECT_CONTEXT_POLICY_V1
from app.interview_vnext.llm.operation_documents import question_select_operation
from app.interview_vnext.llm.question_select import (
    QuestionSelectAction,
    QuestionSelectOutput,
    QuestionSelectRejectCode,
)
from app.job_authoring.commands import CreateJobDocumentCommand
from app.job_authoring.digest import build_job_state_digest
from app.job_authoring.transitions import create_initial_document


NOW = datetime(2026, 7, 23, 9, 0, tzinfo=UTC)
HASH = "sha256:" + "0" * 64


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-question-select-test:{name}")


def _turn(
    *,
    session_id: UUID,
    sequence: int,
    role: TranscriptRole,
    text: str,
    previous_turn_id: UUID | None,
) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=uid(f"turn-{sequence}-{text}"),
        session_id=session_id,
        client_turn_id=f"client-{sequence}",
        sequence=sequence,
        role=role,
        text=text,
        previous_turn_id=previous_turn_id,
        occurred_at=NOW + timedelta(minutes=sequence),
        received_at=NOW + timedelta(minutes=sequence),
    )


def _digest(session_id: UUID):
    revision = create_initial_document(
        CreateJobDocumentCommand(
            command_id=uid(f"create-document-{session_id}"),
            tenant_id=uid("tenant"),
            session_id=session_id,
            job_title="營運專員",
            occurred_at=NOW,
        )
    )
    return build_job_state_digest(
        revision=revision,
        pending_proposals=(),
        pending_proposal_count=0,
        stale_proposal_count=0,
    )


def _state(*, active_episode: bool, include_output: bool = False) -> InterviewState:
    session_id = uid(f"session-{active_episode}-{include_output}")
    if active_episode:
        consultant = _turn(
            session_id=session_id,
            sequence=1,
            role=TranscriptRole.CONSULTANT,
            text="請先說一項你平常會做的主要工作。",
            previous_turn_id=None,
        )
        employee = _turn(
            session_id=session_id,
            sequence=2,
            role=TranscriptRole.EMPLOYEE,
            text="我每天核對異常訂單。",
            previous_turn_id=consultant.turn_id,
        )
        turns = (consultant, employee)
        episode_id = uid(f"episode-{session_id}")
        operation_id = uid(f"interpret-{session_id}")
        evidence = [
            Evidence(
                evidence_id=uid(f"action-{session_id}"),
                session_id=session_id,
                episode_id=episode_id,
                subject=EvidenceSubject.EMPLOYEE,
                kind=EvidenceKind.ACTION,
                claim="核對異常訂單",
                support=LiteralEmployeeSpanSupport(
                    employee_turn_id=employee.turn_id,
                    quote=employee.text,
                    span=QuoteSpan(start=0, end=len(employee.text)),
                ),
                qualifiers=EvidenceQualifiers(
                    time_scope=TimeScope.CURRENT,
                    polarity=Polarity.AFFIRMED,
                ),
                extractor_operation_id=operation_id,
            )
        ]
        if include_output:
            evidence.append(
                Evidence(
                    evidence_id=uid(f"output-{session_id}"),
                    session_id=session_id,
                    episode_id=episode_id,
                    subject=EvidenceSubject.EMPLOYEE,
                    kind=EvidenceKind.OUTPUT,
                    claim="異常訂單清單",
                    support=LiteralEmployeeSpanSupport(
                        employee_turn_id=employee.turn_id,
                        quote=employee.text,
                        span=QuoteSpan(start=0, end=len(employee.text)),
                    ),
                    qualifiers=EvidenceQualifiers(
                        time_scope=TimeScope.CURRENT,
                        polarity=Polarity.AFFIRMED,
                    ),
                    extractor_operation_id=operation_id,
                )
            )
        episode = EpisodeState(
            episode_id=episode_id,
            session_id=session_id,
            target="異常訂單核對",
            opened_turn_id=consultant.turn_id,
            evidence_ids=tuple(item.evidence_id for item in evidence),
            created_at=consultant.occurred_at,
            updated_at=employee.occurred_at,
        )
    else:
        employee = _turn(
            session_id=session_id,
            sequence=1,
            role=TranscriptRole.EMPLOYEE,
            text="我想整理目前的工作內容。",
            previous_turn_id=None,
        )
        turns = (employee,)
        episode_id = None
        operation_id = uid(f"interpret-{session_id}")
        evidence = []
        episode = None

    receipt = TurnInterpretationRecord(
        interpretation_id=turn_interpretation_id(operation_id),
        session_id=session_id,
        employee_turn_id=employee.turn_id,
        operation_id=operation_id,
        context_packet_hash=HASH,
        output_hash=HASH,
        verification_report_hash=HASH,
        accepted_evidence_ids=tuple(item.evidence_id for item in evidence),
        dialogue_act=DialogueAct.STANDALONE_ANSWER,
        episode_signal=EpisodeSignal.CONTINUE,
        applied_at=employee.occurred_at,
    )
    session = session_at(
        session_id=session_id,
        profile_id=uid("profile"),
        tenant_id=uid("tenant"),
        workflow_version="3.0.0",
        reference_snapshot_id="fixture",
        now=NOW,
    ).model_copy(
        update={
            "status": SessionStatus.ACTIVE,
            "state_version": 4,
            "active_episode_id": episode_id,
            "turn_count": len(turns),
            "updated_at": employee.occurred_at,
        }
    )
    return InterviewState(
        session=session,
        turns=turns,
        evidence=tuple(evidence),
        episodes=(episode,) if episode is not None else (),
        turn_interpretations=(receipt,),
    )


def _context(state: InterviewState):
    agenda = build_question_agenda(
        state=state, job_digest=_digest(state.session.session_id)
    )
    operation = question_select_operation()
    result = ContextBuilder().build_question_select(
        state=state,
        agenda=agenda,
        job_digest=_digest(state.session.session_id),
        operation_id=uid(f"question-operation-{state.session.session_id}"),
        operation_definition_hash=operation.definition_hash,
        policy=QUESTION_SELECT_CONTEXT_POLICY_V1,
    )
    return agenda, result


def test_agenda_prioritizes_output_then_purpose_without_field_checklist():
    state = _state(active_episode=True)

    first = build_question_agenda(
        state=state, job_digest=_digest(state.session.session_id)
    )
    second = build_question_agenda(
        state=state, job_digest=_digest(state.session.session_id)
    )

    assert first == second
    assert [item.dimension for item in first.candidates] == [
        GapDimension.OUTPUT_RECIPIENT,
        GapDimension.PURPOSE,
    ]
    assert len(first.candidates) <= 3

    with_output = _state(active_episode=True, include_output=True)
    output_agenda = build_question_agenda(
        state=with_output, job_digest=_digest(with_output.session.session_id)
    )
    assert GapDimension.OUTPUT_RECIPIENT not in {
        item.dimension for item in output_agenda.candidates
    }

    unknown_time = InterviewState.model_validate(
        state.model_copy(
            update={
                "evidence": (
                    state.evidence[0].model_copy(
                        update={
                            "qualifiers": EvidenceQualifiers(
                                time_scope=TimeScope.UNKNOWN,
                                polarity=Polarity.AFFIRMED,
                            )
                        }
                    ),
                )
            }
        ).model_dump()
    )
    unknown_agenda = build_question_agenda(
        state=unknown_time,
        job_digest=_digest(unknown_time.session.session_id),
    )
    assert unknown_agenda.candidates[0].dimension == GapDimension.OUTPUT_RECIPIENT


def test_context_is_bounded_and_projects_no_provider_ids():
    state = _state(active_episode=True)
    agenda, result = _context(state)
    projection = question_select_projection(result.packet)

    assert len(result.packet.agenda_candidates) == len(agenda.candidates) == 2
    assert len(result.packet.supporting_evidence) == 1
    assert projection.input.candidates[0].supporting_evidence_ordinals == (1,)
    assert projection.input.job_state.job_title == "營運專員"
    assert "evidence_id" not in projection.input.model_dump_json()
    assert result.budget.within_budget


def test_invalid_ordinal_and_repeated_question_fail_closed():
    state = _state(active_episode=True)
    _agenda, result = _context(state)
    invalid = QuestionSelectOutput(
        acknowledgement="了解。",
        action=QuestionSelectAction.ASK_GAP,
        selected_gap_ordinal=3,
        question_text="這項工作會產出什麼？",
    )
    report = verify_question_select_output(output=invalid, context=result.packet)
    assert report.reason_codes == (
        QuestionSelectRejectCode.GAP_ORDINAL_OUT_OF_RANGE,
    )
    with pytest.raises(QuestionSelectionRejected):
        materialize_question_selection(
            state=state,
            context=result.packet,
            output=invalid,
            operation_id=result.packet.operation_id,
            occurred_at=NOW + timedelta(hours=1),
        )

    repeated = QuestionSelectOutput(
        acknowledgement="",
        action=QuestionSelectAction.ASK_GAP,
        selected_gap_ordinal=1,
        question_text="請先說一項你平常會做的主要工作。",
    )
    report = verify_question_select_output(output=repeated, context=result.packet)
    assert QuestionSelectRejectCode.DUPLICATE_RECENT_QUESTION in report.reason_codes


def test_output_gap_materializes_a_grounded_slot_frame_and_reducer_accepts_it():
    state = _state(active_episode=True)
    _agenda, result = _context(state)
    output = QuestionSelectOutput(
        acknowledgement="了解，你會核對異常訂單。",
        action=QuestionSelectAction.ASK_GAP,
        selected_gap_ordinal=1,
        question_text="這項工作最後會產出什麼？",
    )

    plan = materialize_question_selection(
        state=state,
        context=result.packet,
        output=output,
        operation_id=result.packet.operation_id,
        occurred_at=NOW + timedelta(hours=1),
    )
    reduced = append_consultant_question(state, plan.append_question)

    assert plan.transition_gap is None
    assert plan.open_episode is None
    assert reduced.state.active_question_frame_id is not None
    frame = reduced.state.question_frames[-1]
    assert frame.definition.mode == QuestionMode.SLOT_REQUEST
    target = frame.definition.targets[0]
    assert isinstance(target, SlotQuestionTarget)
    assert target.slot_kind == QuestionSlotKind.OUTPUT
    assert target.claim_template == "{value}"
    assert target.source_refs[0].source_ref == str(state.evidence[0].evidence_id)


def test_broaden_coverage_opens_an_episode_after_the_question():
    state = _state(active_episode=False)
    _agenda, result = _context(state)
    output = QuestionSelectOutput(
        acknowledgement="我們先從主要工作開始。",
        action=QuestionSelectAction.BROADEN_COVERAGE,
        selected_gap_ordinal=None,
        question_text="請說一項你目前最主要、最常處理的工作。",
    )

    plan = materialize_question_selection(
        state=state,
        context=result.packet,
        output=output,
        operation_id=result.packet.operation_id,
        occurred_at=NOW + timedelta(hours=1),
    )
    after_question = append_consultant_question(state, plan.append_question).state
    final = open_episode(after_question, plan.open_episode).state

    assert plan.append_question.frame_definition.mode == QuestionMode.OPEN_NARRATIVE
    assert final.session.active_episode_id == plan.open_episode.episode_id
    assert final.episodes[-1].target == "下一項主要工作"
    assert final.turns[-1].text == plan.display_text


def test_existing_gap_is_marked_asked_after_question_is_persisted():
    base = _state(active_episode=True)
    episode = base.episodes[0]
    gap = Gap(
        gap_id=uid("existing-contradiction-gap"),
        session_id=base.session.session_id,
        episode_id=episode.episode_id,
        dimension=GapDimension.CONTRADICTION,
        question_goal="釐清目前有兩種不同說法的處理方式",
        supporting_evidence_ids=(base.evidence[0].evidence_id,),
        priority_features=GapPriorityFeatures(
            jd_value=ValueLevel.HIGH,
            contradiction=True,
        ),
    )
    state = InterviewState.model_validate(
        base.model_copy(
            update={
                "episodes": (
                    episode.model_copy(update={"gap_ids": (gap.gap_id,)}),
                ),
                "gaps": (gap,),
            }
        ).model_dump()
    )
    _agenda, result = _context(state)
    assert result.packet.agenda_candidates[0].existing_gap_id == gap.gap_id
    output = QuestionSelectOutput(
        acknowledgement="這裡有兩種不同說法，我想先確認。",
        action=QuestionSelectAction.ASK_GAP,
        selected_gap_ordinal=1,
        question_text="目前實際採用的是哪一種處理方式？",
    )

    plan = materialize_question_selection(
        state=state,
        context=result.packet,
        output=output,
        operation_id=result.packet.operation_id,
        occurred_at=NOW + timedelta(hours=1),
    )
    after_question = append_consultant_question(state, plan.append_question).state
    final = transition_gap(after_question, plan.transition_gap).state

    assert final.gaps[0].status.value == "asked"
    assert final.gaps[0].asked_turn_ids == (
        plan.append_question.turn.turn_id,
    )
