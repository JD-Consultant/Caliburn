from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import TypeAdapter

from app.interview_vnext.domain.commands import (
    ApplyCandidateProposalsCommand,
    ApplyEvidenceCommand,
    ApplyGapProposalsCommand,
    ApplyInferenceProposalsCommand,
    ApplyReviewDecisionCommand,
    AppendTranscriptTurnCommand,
    DecideInferenceCommand,
    OpenEpisodeCommand,
    SupersedeInferenceCommand,
    TransitionCandidateCommand,
    TransitionEpisodeCommand,
    TransitionGapCommand,
    TransitionSessionCommand,
    WithdrawEvidenceCommand,
)
from app.interview_vnext.domain.errors import DomainViolation
from app.interview_vnext.domain.episode import (
    EpisodeStatus,
    Gap,
    GapDimension,
    GapPriorityFeatures,
    GapStatus,
    Sensitivity,
    ValueLevel,
)
from app.interview_vnext.domain.events import DomainEvent
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceStatus,
    EvidenceSubject,
    Inference,
    InferenceMethod,
    InferenceStatus,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.job_model import (
    CandidateJobItem,
    CandidateKind,
    CandidateStatus,
)
from app.interview_vnext.domain.reason_codes import ReasonCode
from app.interview_vnext.domain.reducers import (
    apply_candidate_proposals,
    apply_evidence,
    apply_gap_proposals,
    apply_inference_proposals,
    apply_review_decision,
    append_transcript_turn,
    decide_inference,
    open_episode,
    supersede_inference,
    transition_candidate,
    transition_episode,
    transition_gap,
    transition_session,
    withdraw_evidence,
)
from app.interview_vnext.domain.review import ReviewAction, ReviewDecision
from app.interview_vnext.domain.session import InterviewSession, SessionStatus
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.support import QuoteSpan
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn


NOW = datetime(2026, 7, 16, 8, 0, tzinfo=UTC)


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-v1b-test:{name}")


def at(state: InterviewState, seconds: int = 1) -> datetime:
    return state.session.updated_at + timedelta(seconds=seconds)


def active_state() -> InterviewState:
    session = InterviewSession(
        session_id=uid("session"),
        profile_id=uid("profile"),
        tenant_id=uid("tenant"),
        workflow_version="1.0.0",
        reference_snapshot_id="reference-snapshot-v1",
        created_at=NOW,
        updated_at=NOW,
    )
    state = InterviewState(session=session)
    return transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("activate"),
            expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=1),
            target_status=SessionStatus.ACTIVE,
        ),
    ).state


def append_turn(
    state: InterviewState,
    *,
    name: str,
    role: TranscriptRole,
    text: str,
) -> tuple[InterviewState, TranscriptTurn]:
    occurred_at = at(state)
    turn = TranscriptTurn(
        turn_id=uid(f"turn:{name}"),
        session_id=state.session.session_id,
        client_turn_id=f"client:{name}",
        sequence=len(state.turns) + 1,
        role=role,
        text=text,
        previous_turn_id=state.turns[-1].turn_id if state.turns else None,
        occurred_at=occurred_at,
        received_at=occurred_at,
    )
    result = append_transcript_turn(
        state,
        AppendTranscriptTurnCommand(
            command_id=uid(f"append:{name}"),
            expected_state_version=state.session.state_version,
            occurred_at=occurred_at,
            turn=turn,
        ),
    )
    return result.state, turn


def evidence_for(
    turn: TranscriptTurn,
    *,
    name: str,
    quote: str,
    episode_id: UUID,
    kind: EvidenceKind = EvidenceKind.ACTION,
) -> Evidence:
    start = turn.text.index(quote)
    return Evidence(
        evidence_id=uid(f"evidence:{name}"),
        session_id=turn.session_id,
        turn_id=turn.turn_id,
        episode_id=episode_id,
        subject=EvidenceSubject.EMPLOYEE,
        kind=kind,
        claim=quote,
        quote=quote,
        span=QuoteSpan(start=start, end=start + len(quote)),
        qualifiers=EvidenceQualifiers(
            time_scope=TimeScope.CURRENT,
            typicality=Typicality.TYPICAL,
            polarity=Polarity.AFFIRMED,
            ownership=Ownership.OWNER,
        ),
        extractor_operation_id=uid(f"operation:{name}"),
    )


def state_with_open_episode_and_evidence() -> tuple[InterviewState, TranscriptTurn, Evidence]:
    state = active_state()
    state, _ = append_turn(
        state,
        name="opening-question",
        role=TranscriptRole.CONSULTANT,
        text="請描述一項固定負責的工作。",
    )
    state, answer = append_turn(
        state,
        name="opening-answer",
        role=TranscriptRole.EMPLOYEE,
        text="我每週整理測試結果並交給產品經理。",
    )
    episode_id = uid("episode:testing-report")
    state = open_episode(
        state,
        OpenEpisodeCommand(
            command_id=uid("open:testing-report"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=episode_id,
            target="例行測試結果整理",
            opened_turn_id=answer.turn_id,
        ),
    ).state
    evidence = evidence_for(
        answer,
        name="testing-action",
        quote="整理測試結果",
        episode_id=episode_id,
    )
    state = apply_evidence(
        state,
        ApplyEvidenceCommand(
            command_id=uid("apply:testing-action"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            turn_id=answer.turn_id,
            observations=(evidence,),
        ),
    ).state
    return state, answer, evidence


def gap_for(
    state: InterviewState,
    evidence: Evidence,
    *,
    name: str = "output-recipient",
    sensitivity: Sensitivity = Sensitivity.LOW,
) -> Gap:
    return Gap(
        gap_id=uid(f"gap:{name}"),
        session_id=state.session.session_id,
        episode_id=state.session.active_episode_id,
        dimension=GapDimension.OUTPUT_RECIPIENT,
        question_goal="確認工作產出交付給誰",
        supporting_evidence_ids=(evidence.evidence_id,),
        priority_features=GapPriorityFeatures(
            jd_value=ValueLevel.HIGH,
            sensitivity=sensitivity,
            burden=ValueLevel.LOW,
        ),
    )


def inference_for(
    state: InterviewState,
    evidence: Evidence,
    *,
    name: str = "reporting",
    statement: str = "負責彙整測試資訊供產品決策",
) -> Inference:
    return Inference(
        inference_id=uid(f"inference:{name}"),
        session_id=state.session.session_id,
        type="work.purpose",
        statement=statement,
        supporting_evidence_ids=(evidence.evidence_id,),
        method=InferenceMethod.LLM,
        operation_name="episode.code",
        operation_definition_hash=(
            "sha256:1111111111111111111111111111111111111111111111111111111111111111"
        ),
    )


def candidate_for(
    state: InterviewState,
    evidence: Evidence,
    *,
    name: str = "testing-task",
    inference_ids: tuple[UUID, ...] = (),
    statement: str = "整理測試結果",
) -> CandidateJobItem:
    return CandidateJobItem(
        candidate_id=uid(f"candidate:{name}"),
        session_id=state.session.session_id,
        kind=CandidateKind.TASK,
        statement=statement,
        evidence_ids=(evidence.evidence_id,),
        inference_ids=inference_ids,
        status=CandidateStatus.DRAFT,
        created_by_operation="episode.code",
    )


def apply_candidate(
    state: InterviewState,
    candidate: CandidateJobItem,
    *,
    name: str,
) -> InterviewState:
    return apply_candidate_proposals(
        state,
        ApplyCandidateProposalsCommand(
            command_id=uid(f"apply-candidate:{name}"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            candidates=(candidate,),
        ),
    ).state


def transition_candidate_to(
    state: InterviewState,
    candidate_id: UUID,
    target: CandidateStatus,
    *,
    name: str,
) -> InterviewState:
    return transition_candidate(
        state,
        TransitionCandidateCommand(
            command_id=uid(f"candidate-transition:{name}"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            candidate_id=candidate_id,
            target_status=target,
        ),
    ).state


def test_episode_has_one_active_owner_and_closes_only_after_gap_resolution():
    state, _, evidence = state_with_open_episode_and_evidence()
    with pytest.raises(DomainViolation) as caught:
        open_episode(
            state,
            OpenEpisodeCommand(
                command_id=uid("open:second"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                episode_id=uid("episode:second"),
                target="不應開啟",
                opened_turn_id=state.turns[-1].turn_id,
            ),
        )
    assert caught.value.reason_code == ReasonCode.ACTIVE_EPISODE_EXISTS

    gap = gap_for(state, evidence)
    state = apply_gap_proposals(
        state,
        ApplyGapProposalsCommand(
            command_id=uid("apply-gap:close-test"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            gaps=(gap,),
        ),
    ).state
    state = transition_episode(
        state,
        TransitionEpisodeCommand(
            command_id=uid("episode:closing"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            target_status=EpisodeStatus.CLOSING,
        ),
    ).state
    with pytest.raises(DomainViolation) as caught:
        transition_episode(
            state,
            TransitionEpisodeCommand(
                command_id=uid("episode:close-too-early"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                episode_id=state.session.active_episode_id,
                target_status=EpisodeStatus.CLOSED,
                closed_turn_id=state.turns[-1].turn_id,
            ),
        )
    assert caught.value.reason_code == ReasonCode.EPISODE_HAS_UNRESOLVED_GAPS

    state = transition_gap(
        state,
        TransitionGapCommand(
            command_id=uid("gap:defer-for-close"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            gap_id=gap.gap_id,
            target_status=GapStatus.DEFERRED,
            unresolved_reason="訪談時間不足，交由人工複核",
        ),
    ).state
    result = transition_episode(
        state,
        TransitionEpisodeCommand(
            command_id=uid("episode:closed"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            target_status=EpisodeStatus.CLOSED,
            closed_turn_id=state.turns[-1].turn_id,
        ),
    )
    assert result.state.session.active_episode_id is None
    assert result.state.episodes[0].status == EpisodeStatus.CLOSED


def test_closed_episode_rejects_late_or_backdated_evidence():
    state, _, _ = state_with_open_episode_and_evidence()
    episode_id = state.session.active_episode_id
    state = transition_episode(
        state,
        TransitionEpisodeCommand(
            command_id=uid("late-evidence:closing"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=episode_id,
            target_status=EpisodeStatus.CLOSING,
        ),
    ).state
    state = transition_episode(
        state,
        TransitionEpisodeCommand(
            command_id=uid("late-evidence:closed"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=episode_id,
            target_status=EpisodeStatus.CLOSED,
            closed_turn_id=state.turns[-1].turn_id,
        ),
    ).state
    state, late_turn = append_turn(
        state,
        name="late-evidence-answer",
        role=TranscriptRole.EMPLOYEE,
        text="補充一項已經關閉的工作內容。",
    )
    late = evidence_for(
        late_turn,
        name="late-closed-episode",
        quote="補充一項已經關閉的工作內容",
        episode_id=episode_id,
    )
    with pytest.raises(DomainViolation) as caught:
        apply_evidence(
            state,
            ApplyEvidenceCommand(
                command_id=uid("late-evidence:apply"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                turn_id=late_turn.turn_id,
                observations=(late,),
            ),
        )
    assert caught.value.reason_code == ReasonCode.EVIDENCE_EPISODE_INVALID


def test_gap_question_and_answer_are_role_bound_and_terminal():
    state, _, evidence = state_with_open_episode_and_evidence()
    gap = gap_for(state, evidence)
    state = apply_gap_proposals(
        state,
        ApplyGapProposalsCommand(
            command_id=uid("apply-gap:qa"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            gaps=(gap,),
        ),
    ).state
    state, question = append_turn(
        state,
        name="gap-question",
        role=TranscriptRole.CONSULTANT,
        text="整理完成後通常交給誰使用？",
    )
    state = transition_gap(
        state,
        TransitionGapCommand(
            command_id=uid("gap:asked"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            gap_id=gap.gap_id,
            target_status=GapStatus.ASKED,
            source_turn_id=question.turn_id,
        ),
    ).state
    state, answer = append_turn(
        state,
        name="gap-answer",
        role=TranscriptRole.EMPLOYEE,
        text="主要交給產品經理安排修正優先序。",
    )
    resolution = evidence_for(
        answer,
        name="gap-answer-recipient",
        quote="產品經理",
        episode_id=state.session.active_episode_id,
        kind=EvidenceKind.RECIPIENT,
    )
    state = apply_evidence(
        state,
        ApplyEvidenceCommand(
            command_id=uid("apply:gap-answer-recipient"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            turn_id=answer.turn_id,
            observations=(resolution,),
        ),
    ).state
    state = transition_gap(
        state,
        TransitionGapCommand(
            command_id=uid("gap:answered"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            gap_id=gap.gap_id,
            target_status=GapStatus.ANSWERED,
            source_turn_id=answer.turn_id,
            resolution_evidence_ids=(resolution.evidence_id,),
        ),
    ).state
    materialized = state.gaps[0]
    assert materialized.asked_turn_ids == (question.turn_id,)
    assert materialized.resolution_turn_id == answer.turn_id
    assert materialized.resolution_evidence_ids == (resolution.evidence_id,)

    with pytest.raises(DomainViolation) as caught:
        transition_gap(
            state,
            TransitionGapCommand(
                command_id=uid("gap:reask-terminal"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                gap_id=gap.gap_id,
                target_status=GapStatus.ASKED,
                source_turn_id=question.turn_id,
            ),
        )
    assert caught.value.reason_code == ReasonCode.GAP_TRANSITION_INVALID

    state, withdrawal_turn = append_turn(
        state,
        name="gap-answer-withdrawal",
        role=TranscriptRole.EMPLOYEE,
        text="更正，產品經理其實不使用這份資料。",
    )
    withdrawal = withdraw_evidence(
        state,
        WithdrawEvidenceCommand(
            command_id=uid("withdraw:gap-answer"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            evidence_id=resolution.evidence_id,
            source_turn_id=withdrawal_turn.turn_id,
            reason="員工撤回答案",
        ),
    )
    assert withdrawal.state.gaps[0].status == GapStatus.DEFERRED
    assert withdrawal.state.gaps[0].resolution_evidence_ids == ()
    assert [event.event_type for event in withdrawal.events] == [
        "evidence.withdrawn",
        "gap.transitioned",
    ]


def test_prohibited_gap_cannot_be_asked():
    state, _, evidence = state_with_open_episode_and_evidence()
    gap = gap_for(state, evidence, name="prohibited", sensitivity=Sensitivity.PROHIBITED)
    state = apply_gap_proposals(
        state,
        ApplyGapProposalsCommand(
            command_id=uid("apply-gap:prohibited"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            gaps=(gap,),
        ),
    ).state
    state, question = append_turn(
        state,
        name="prohibited-question",
        role=TranscriptRole.CONSULTANT,
        text="這題不應被送出。",
    )
    with pytest.raises(DomainViolation) as caught:
        transition_gap(
            state,
            TransitionGapCommand(
                command_id=uid("gap:ask-prohibited"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                gap_id=gap.gap_id,
                target_status=GapStatus.ASKED,
                source_turn_id=question.turn_id,
            ),
        )
    assert caught.value.reason_code == ReasonCode.GAP_TRANSITION_INVALID


def test_deferred_gap_can_be_reasked_but_declined_gap_cannot():
    state, _, evidence = state_with_open_episode_and_evidence()
    gap = gap_for(state, evidence, name="deferred-reask")
    state = apply_gap_proposals(
        state,
        ApplyGapProposalsCommand(
            command_id=uid("apply-gap:deferred-reask"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            gaps=(gap,),
        ),
    ).state
    state = transition_gap(
        state,
        TransitionGapCommand(
            command_id=uid("gap:deferred"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            gap_id=gap.gap_id,
            target_status=GapStatus.DEFERRED,
            unresolved_reason="先完成主流程再回來追問",
        ),
    ).state
    state, question = append_turn(
        state,
        name="deferred-reask-question",
        role=TranscriptRole.CONSULTANT,
        text="回到剛才的產出問題，主要交給誰？",
    )
    state = transition_gap(
        state,
        TransitionGapCommand(
            command_id=uid("gap:reasked"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            gap_id=gap.gap_id,
            target_status=GapStatus.ASKED,
            source_turn_id=question.turn_id,
        ),
    ).state
    assert state.gaps[0].status == GapStatus.ASKED
    assert state.gaps[0].unresolved_reason is None

    state, declined = append_turn(
        state,
        name="deferred-declined",
        role=TranscriptRole.EMPLOYEE,
        text="這部分我不方便回答。",
    )
    state = transition_gap(
        state,
        TransitionGapCommand(
            command_id=uid("gap:declined"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            gap_id=gap.gap_id,
            target_status=GapStatus.DECLINED,
            source_turn_id=declined.turn_id,
            unresolved_reason="員工拒絕回答",
        ),
    ).state
    with pytest.raises(DomainViolation) as caught:
        transition_gap(
            state,
            TransitionGapCommand(
                command_id=uid("gap:reask-declined"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                gap_id=gap.gap_id,
                target_status=GapStatus.ASKED,
                source_turn_id=question.turn_id,
            ),
        )
    assert caught.value.reason_code == ReasonCode.GAP_TRANSITION_INVALID


def test_inference_proposal_can_revise_but_employee_decision_is_protected():
    state, _, evidence = state_with_open_episode_and_evidence()
    inference = inference_for(state, evidence)
    state = apply_inference_proposals(
        state,
        ApplyInferenceProposalsCommand(
            command_id=uid("inference:apply"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            inferences=(inference,),
        ),
    ).state
    revised = inference.model_copy(update={"statement": "負責彙整測試結果供修正排序"})
    revised_result = apply_inference_proposals(
        state,
        ApplyInferenceProposalsCommand(
            command_id=uid("inference:revise"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            inferences=(revised,),
        ),
    )
    assert revised_result.events[0].previous_status == InferenceStatus.CANDIDATE
    state = revised_result.state

    state, confirmation_turn = append_turn(
        state,
        name="inference-confirmation",
        role=TranscriptRole.EMPLOYEE,
        text="是的，產品經理會用這份結果排修正順序。",
    )
    confirmation = evidence_for(
        confirmation_turn,
        name="inference-confirmation",
        quote="產品經理會用這份結果排修正順序",
        episode_id=state.session.active_episode_id,
        kind=EvidenceKind.PURPOSE,
    )
    state = apply_evidence(
        state,
        ApplyEvidenceCommand(
            command_id=uid("apply:inference-confirmation"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            turn_id=confirmation_turn.turn_id,
            observations=(confirmation,),
        ),
    ).state
    decision_result = decide_inference(
        state,
        DecideInferenceCommand(
            command_id=uid("inference:confirm"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            inference_id=inference.inference_id,
            target_status=InferenceStatus.CONFIRMED_BY_EMPLOYEE,
            decision_evidence_id=confirmation.evidence_id,
        ),
    )
    decided = decision_result.state.inferences[0]
    assert decided.status == InferenceStatus.CONFIRMED_BY_EMPLOYEE
    assert decided.decision_evidence_id == confirmation.evidence_id
    assert TypeAdapter(DomainEvent).validate_json(
        TypeAdapter(DomainEvent).dump_json(decision_result.events[0])
    ) == decision_result.events[0]

    with pytest.raises(DomainViolation) as caught:
        apply_inference_proposals(
            decision_result.state,
            ApplyInferenceProposalsCommand(
                command_id=uid("inference:model-overwrite"),
                expected_state_version=decision_result.state.session.state_version,
                occurred_at=at(decision_result.state),
                inferences=(revised,),
            ),
        )
    assert caught.value.reason_code == ReasonCode.HUMAN_DECISION_PROTECTED


def test_inference_supersede_preserves_bidirectional_lineage():
    state, _, evidence = state_with_open_episode_and_evidence()
    inference = inference_for(state, evidence, name="supersede-original")
    state = apply_inference_proposals(
        state,
        ApplyInferenceProposalsCommand(
            command_id=uid("inference:supersede-apply"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            inferences=(inference,),
        ),
    ).state
    replacement = inference.model_copy(
        update={
            "inference_id": uid("inference:supersede-replacement"),
            "statement": "負責提供測試結果，最終排序由產品經理決定",
            "supersedes": (inference.inference_id,),
        }
    )
    result = supersede_inference(
        state,
        SupersedeInferenceCommand(
            command_id=uid("inference:supersede"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            inference_id=inference.inference_id,
            replacement=replacement,
        ),
    )
    by_id = {item.inference_id: item for item in result.state.inferences}
    assert by_id[inference.inference_id].status == InferenceStatus.SUPERSEDED
    assert by_id[inference.inference_id].superseded_by == replacement.inference_id
    assert by_id[replacement.inference_id].supersedes == (inference.inference_id,)
    assert result.events[0].event_type == "inference.superseded"


def test_candidate_requires_closed_lineage_and_verifier_transitions():
    state, _, evidence = state_with_open_episode_and_evidence()
    missing = candidate_for(
        state,
        evidence,
        name="missing-inference",
        inference_ids=(uid("missing-inference"),),
    )
    with pytest.raises(DomainViolation) as caught:
        apply_candidate(
            state,
            missing,
            name="missing-inference",
        )
    assert caught.value.reason_code == ReasonCode.CANDIDATE_INFERENCE_NOT_FOUND

    candidate = candidate_for(state, evidence)
    state = apply_candidate(state, candidate, name="valid")
    revised = candidate.model_copy(update={"statement": "彙整並檢查測試結果"})
    result = apply_candidate_proposals(
        state,
        ApplyCandidateProposalsCommand(
            command_id=uid("candidate:revise"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            candidates=(revised,),
        ),
    )
    assert result.events[0].previous_status == CandidateStatus.DRAFT
    state = transition_candidate_to(
        result.state,
        candidate.candidate_id,
        CandidateStatus.VERIFIED,
        name="verify",
    )
    state = transition_candidate_to(
        state,
        candidate.candidate_id,
        CandidateStatus.PROJECTED,
        name="project",
    )
    assert state.candidates[0].status == CandidateStatus.PROJECTED

    with pytest.raises(DomainViolation) as caught:
        transition_candidate(
            state,
            TransitionCandidateCommand(
                command_id=uid("candidate:model-accept"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                candidate_id=candidate.candidate_id,
                target_status=CandidateStatus.ACCEPTED,
            ),
        )
    assert caught.value.reason_code == ReasonCode.HUMAN_DECISION_PROTECTED


def test_evidence_withdrawal_deterministically_invalidates_model_outputs():
    state, _, evidence = state_with_open_episode_and_evidence()
    inference = inference_for(state, evidence, name="withdraw")
    state = apply_inference_proposals(
        state,
        ApplyInferenceProposalsCommand(
            command_id=uid("inference:withdraw-apply"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            inferences=(inference,),
        ),
    ).state
    candidate = candidate_for(
        state,
        evidence,
        name="withdraw",
        inference_ids=(inference.inference_id,),
    )
    state = apply_candidate(state, candidate, name="withdraw")
    state = transition_candidate_to(
        state,
        candidate.candidate_id,
        CandidateStatus.VERIFIED,
        name="withdraw-verify",
    )
    state = transition_candidate_to(
        state,
        candidate.candidate_id,
        CandidateStatus.PROJECTED,
        name="withdraw-project",
    )
    state, withdrawal_turn = append_turn(
        state,
        name="withdrawal",
        role=TranscriptRole.EMPLOYEE,
        text="更正，我其實不負責整理測試結果。",
    )
    command = WithdrawEvidenceCommand(
        command_id=uid("withdraw:evidence"),
        expected_state_version=state.session.state_version,
        occurred_at=at(state),
        evidence_id=evidence.evidence_id,
        source_turn_id=withdrawal_turn.turn_id,
        reason="員工明確撤回原陳述",
    )
    result = withdraw_evidence(state, command)
    assert result.state.evidence[0].status == EvidenceStatus.WITHDRAWN
    assert result.state.inferences[0].status == InferenceStatus.INSUFFICIENT
    assert result.state.candidates[0].status == CandidateStatus.INSUFFICIENT
    assert [event.event_type for event in result.events] == [
        "evidence.withdrawn",
        "inference.transitioned",
        "candidate.transitioned",
    ]

    duplicate = withdraw_evidence(result.state, command)
    assert duplicate.idempotent is True
    assert duplicate.state_hash == result.state_hash
    assert len(duplicate.state.evidence) == 1


def test_review_after_completion_is_human_only_and_edit_is_materialized():
    state, _, evidence = state_with_open_episode_and_evidence()
    candidate = candidate_for(state, evidence, name="review")
    state = apply_candidate(state, candidate, name="review")
    state = transition_candidate_to(
        state,
        candidate.candidate_id,
        CandidateStatus.VERIFIED,
        name="review-verify",
    )
    state = transition_candidate_to(
        state,
        candidate.candidate_id,
        CandidateStatus.PROJECTED,
        name="review-project",
    )
    state = transition_episode(
        state,
        TransitionEpisodeCommand(
            command_id=uid("review:episode-closing"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            target_status=EpisodeStatus.CLOSING,
        ),
    ).state
    state = transition_episode(
        state,
        TransitionEpisodeCommand(
            command_id=uid("review:episode-closed"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            episode_id=state.session.active_episode_id,
            target_status=EpisodeStatus.CLOSED,
            closed_turn_id=state.turns[-1].turn_id,
        ),
    ).state
    state = transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("review:finishing"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            target_status=SessionStatus.FINISHING,
        ),
    ).state
    state = transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("review:completed"),
            expected_state_version=state.session.state_version,
            occurred_at=at(state),
            target_status=SessionStatus.COMPLETED,
            stop_reason="訪談資料已完成投影",
        ),
    ).state

    decision = ReviewDecision(
        review_id=uid("review:edit"),
        session_id=state.session.session_id,
        candidate_id=candidate.candidate_id,
        reviewer_id=uid("reviewer"),
        action=ReviewAction.EDIT,
        edited_statement="彙整、檢查並提交測試結果",
        decided_at=at(state),
    )
    command = ApplyReviewDecisionCommand(
        command_id=uid("review:apply-edit"),
        expected_state_version=state.session.state_version,
        occurred_at=decision.decided_at,
        decision=decision,
    )
    result = apply_review_decision(state, command)
    reviewed = result.state.candidates[0]
    assert reviewed.status == CandidateStatus.ACCEPTED
    assert reviewed.statement == decision.edited_statement
    assert reviewed.review_decision_id == decision.review_id
    assert result.state.session.status == SessionStatus.COMPLETED

    duplicate = apply_review_decision(result.state, command)
    assert duplicate.idempotent is True
    assert len(duplicate.state.reviews) == 1


def test_same_v1b_command_sequence_has_stable_hash_and_event_ids():
    def run() -> tuple[str, tuple[UUID, ...]]:
        state, _, evidence = state_with_open_episode_and_evidence()
        inference = inference_for(state, evidence, name="replay")
        inference_result = apply_inference_proposals(
            state,
            ApplyInferenceProposalsCommand(
                command_id=uid("replay:inference"),
                expected_state_version=state.session.state_version,
                occurred_at=at(state),
                inferences=(inference,),
            ),
        )
        candidate = candidate_for(
            inference_result.state,
            evidence,
            name="replay",
            inference_ids=(inference.inference_id,),
        )
        candidate_result = apply_candidate_proposals(
            inference_result.state,
            ApplyCandidateProposalsCommand(
                command_id=uid("replay:candidate"),
                expected_state_version=inference_result.state.session.state_version,
                occurred_at=at(inference_result.state),
                candidates=(candidate,),
            ),
        )
        event_ids = tuple(
            event.event_id
            for event in inference_result.events + candidate_result.events
        )
        return canonical_hash(candidate_result.state), event_ids

    assert run() == run()
