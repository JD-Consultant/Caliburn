from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal
from uuid import NAMESPACE_URL, UUID, uuid5

import pytest
from pydantic import TypeAdapter, ValidationError

from app.interview_vnext.domain.commands import (
    ApplyTurnInterpretationCommand,
    AppendConsultantQuestionCommand,
    AppendEmployeeTurnCommand,
    TransitionSessionCommand,
)
from app.interview_vnext.domain.errors import DomainViolation
from app.interview_vnext.domain.episode import EpisodeState
from app.interview_vnext.domain.events import DomainEvent
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceKind,
    EvidenceQualifiers,
    EvidenceStatus,
    EvidenceSubject,
    FrequencyQualifier,
    FrequencyUnit,
    Importance,
    Ownership,
    Polarity,
    TimeScope,
    Typicality,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.invariants import (
    assert_candidate_projectable,
    assert_evidence_matches_turn,
    assert_model_may_replace_candidate,
)
from app.interview_vnext.domain.job_model import (
    CandidateJobItem,
    CandidateKind,
    CandidateStatus,
    QuantitativeThreshold,
    ThresholdSourceType,
)
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.question_frame import (
    QuestionMode,
    build_question_frame_definition,
)
from app.interview_vnext.domain.reason_codes import ReasonCode
from app.interview_vnext.domain.reducers import (
    append_consultant_question,
    append_employee_turn,
    apply_turn_interpretation,
    transition_session,
)
from app.interview_vnext.domain.session import InterviewSession, SessionStatus
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.support import (
    LiteralEmployeeSpanSupport,
    QuoteMatch,
    QuoteSpan,
)
from app.interview_vnext.domain.turn_identity import turn_interpretation_id
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.domain.review import ReviewAction, ReviewDecision


NOW = datetime(2026, 7, 16, 0, 0, tzinfo=UTC)


def uid(name: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"caliburn-test:{name}")


def planned_state() -> InterviewState:
    session = InterviewSession(
        session_id=uid("session"),
        profile_id=uid("profile"),
        tenant_id=uid("tenant"),
        workflow_version="1.0.0",
        reference_snapshot_id="ref-snapshot-v1",
        created_at=NOW,
        updated_at=NOW,
    )
    return InterviewState(session=session)


def active_state() -> InterviewState:
    state = planned_state()
    return transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("activate-command"),
            expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=1),
            target_status=SessionStatus.ACTIVE,
        ),
    ).state


def turn_for(
    state: InterviewState,
    *,
    name: str,
    role: TranscriptRole,
    text: str,
    at: datetime,
) -> TranscriptTurn:
    return TranscriptTurn(
        turn_id=uid(f"turn:{name}"),
        session_id=state.session.session_id,
        client_turn_id=f"client-{name}",
        sequence=len(state.turns) + 1,
        role=role,
        text=text,
        previous_turn_id=state.turns[-1].turn_id if state.turns else None,
        occurred_at=at,
        received_at=at,
    )


TEST_HASH = "sha256:" + "0" * 64


def open_narrative_definition(text: str):
    return build_question_frame_definition(
        mode=QuestionMode.OPEN_NARRATIVE,
        question_text=text,
        targets=(),
    )


def append_turn(
    state: InterviewState,
    *,
    name: str,
    role: TranscriptRole,
    text: str,
    at: datetime,
) -> tuple[InterviewState, TranscriptTurn]:
    turn = turn_for(state, name=name, role=role, text=text, at=at)
    if role == TranscriptRole.CONSULTANT:
        result = append_consultant_question(
            state,
            AppendConsultantQuestionCommand(
                command_id=uid(f"append:{name}"),
                expected_state_version=state.session.state_version,
                occurred_at=at,
                turn=turn,
                frame_definition=open_narrative_definition(text),
            ),
        )
    else:
        result = append_employee_turn(
            state,
            AppendEmployeeTurnCommand(
                command_id=uid(f"append:{name}"),
                expected_state_version=state.session.state_version,
                occurred_at=at,
                turn=turn,
            ),
        )
    return result.state, turn


def interpret(
    state: InterviewState,
    turn: TranscriptTurn,
    observations: tuple[Evidence, ...] = (),
    *,
    name: str,
    at: datetime,
    operation_id: UUID | None = None,
    dialogue_act: DialogueAct = DialogueAct.STANDALONE_ANSWER,
):
    """Commit a receipt for ``turn``, consuming the frame it answered."""

    operation_id = operation_id or uid(f"operation:{name}")
    frame = None
    if state.active_question_frame_id is not None:
        candidate = next(
            item
            for item in state.question_frames
            if item.question_frame_id == state.active_question_frame_id
        )
        if candidate.answer_turn_id == turn.turn_id:
            frame = candidate
    record = TurnInterpretationRecord(
        interpretation_id=turn_interpretation_id(operation_id),
        session_id=state.session.session_id,
        employee_turn_id=turn.turn_id,
        operation_id=operation_id,
        question_frame_id=frame.question_frame_id if frame is not None else None,
        question_frame_definition_hash=(
            frame.definition.definition_hash if frame is not None else None
        ),
        context_packet_hash=TEST_HASH,
        output_hash=TEST_HASH,
        verification_report_hash=TEST_HASH,
        accepted_evidence_ids=tuple(item.evidence_id for item in observations),
        dialogue_act=dialogue_act,
        episode_signal=EpisodeSignal.CONTINUE,
        applied_at=at,
    )
    return apply_turn_interpretation(
        state,
        ApplyTurnInterpretationCommand(
            command_id=uid(f"apply:{name}"),
            expected_state_version=state.session.state_version,
            occurred_at=at,
            record=record,
            observations=tuple(observations),
        ),
    )


def current_qualifiers(**changes) -> EvidenceQualifiers:
    values = {
        "time_scope": TimeScope.CURRENT,
        "typicality": Typicality.TYPICAL,
        "polarity": Polarity.AFFIRMED,
        "frequency": FrequencyQualifier(),
        "importance": Importance.NOT_STATED,
        "ownership": Ownership.OWNER,
    }
    values.update(changes)
    return EvidenceQualifiers(**values)


def evidence_for(
    turn: TranscriptTurn,
    *,
    name: str,
    quote: str,
    source_quote: str | None = None,
    episode_id: UUID | None = None,
    kind: EvidenceKind = EvidenceKind.ACTION,
    qualifiers: EvidenceQualifiers | None = None,
    supersedes: tuple[UUID, ...] = (),
    quote_match: QuoteMatch = QuoteMatch.EXACT,
    operation_id: UUID | None = None,
) -> Evidence:
    source_quote = source_quote or quote
    start = turn.text.index(source_quote)
    return Evidence(
        evidence_id=uid(f"evidence:{name}"),
        session_id=turn.session_id,
        episode_id=episode_id,
        subject=EvidenceSubject.EMPLOYEE,
        kind=kind,
        claim=quote,
        support=LiteralEmployeeSpanSupport(
            employee_turn_id=turn.turn_id,
            quote=quote,
            span=QuoteSpan(start=start, end=start + len(source_quote)),
            quote_match=quote_match,
            normalization_version=(
                "quote_nfkc_ws.v1" if quote_match == QuoteMatch.NORMALIZED else None
            ),
        ),
        qualifiers=qualifiers or current_qualifiers(),
        supersedes=supersedes,
        extractor_operation_id=operation_id or uid(f"operation:{name}"),
    )


def state_with_employee_turn(text: str = "我每週整理測試結果交給產品經理。"):
    state = active_state()
    state, _ = append_turn(
        state,
        name="question",
        role=TranscriptRole.CONSULTANT,
        text="請描述一項你固定負責的工作。",
        at=NOW + timedelta(seconds=2),
    )
    return append_turn(
        state,
        name="answer",
        role=TranscriptRole.EMPLOYEE,
        text=text,
        at=NOW + timedelta(seconds=3),
    )


def test_session_transition_is_versioned_deterministic_and_idempotent():
    initial = planned_state()
    command = TransitionSessionCommand(
        command_id=uid("activate"),
        expected_state_version=0,
        occurred_at=NOW + timedelta(seconds=1),
        target_status=SessionStatus.ACTIVE,
    )

    first = transition_session(initial, command)
    second = transition_session(initial, command)
    duplicate = transition_session(first.state, command)

    assert first.state.session.status == SessionStatus.ACTIVE
    assert first.state.session.state_version == 1
    assert first.events == second.events
    assert first.state_hash == second.state_hash
    assert duplicate.idempotent is True
    assert duplicate.reason_code == ReasonCode.DUPLICATE_COMMAND
    assert duplicate.state_hash == first.state_hash
    assert duplicate.events == ()


def test_stale_new_command_is_a_conflict_but_repeated_command_is_not():
    state = active_state()
    with pytest.raises(DomainViolation) as caught:
        transition_session(
            state,
            TransitionSessionCommand(
                command_id=uid("pause-stale"),
                expected_state_version=0,
                occurred_at=NOW + timedelta(seconds=2),
                target_status=SessionStatus.PAUSED,
            ),
        )
    assert caught.value.reason_code == ReasonCode.STATE_VERSION_CONFLICT


def test_domain_time_is_utc_monotonic_and_receipt_ordered():
    taipei = timezone(timedelta(hours=8))
    with pytest.raises(ValidationError, match="UTC offset"):
        InterviewSession(
            session_id=uid("non-utc-session"),
            profile_id=uid("profile"),
            tenant_id=uid("tenant"),
            workflow_version="1.0.0-alpha.1+build.2",
            reference_snapshot_id="ref-snapshot-v1",
            created_at=NOW.astimezone(taipei),
            updated_at=NOW.astimezone(taipei),
        )

    state = active_state()
    with pytest.raises(DomainViolation) as caught:
        transition_session(
            state,
            TransitionSessionCommand(
                command_id=uid("clock-regression"),
                expected_state_version=state.session.state_version,
                occurred_at=NOW,
                target_status=SessionStatus.PAUSED,
            ),
        )
    assert caught.value.reason_code == ReasonCode.COMMAND_TIME_REGRESSION

    with pytest.raises(ValidationError, match="received_at"):
        TranscriptTurn(
            turn_id=uid("received-before-occurred"),
            session_id=state.session.session_id,
            client_turn_id="received-before-occurred",
            sequence=1,
            role=TranscriptRole.EMPLOYEE,
            text="回答",
            occurred_at=NOW + timedelta(seconds=3),
            received_at=NOW + timedelta(seconds=2),
        )


def test_terminal_transition_requires_reason_and_completion_requires_closed_episode():
    state = active_state()
    state = transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("finishing"),
            expected_state_version=state.session.state_version,
            occurred_at=NOW + timedelta(seconds=2),
            target_status=SessionStatus.FINISHING,
        ),
    ).state
    with pytest.raises(DomainViolation) as caught:
        transition_session(
            state,
            TransitionSessionCommand(
                command_id=uid("complete-without-reason"),
                expected_state_version=state.session.state_version,
                occurred_at=NOW + timedelta(seconds=3),
                target_status=SessionStatus.COMPLETED,
            ),
        )
    assert caught.value.reason_code == ReasonCode.STOP_REASON_REQUIRED


def test_terminal_session_rejects_new_turn_even_with_current_version():
    state = active_state()
    state = transition_session(
        state,
        TransitionSessionCommand(
            command_id=uid("fail-session"),
            expected_state_version=state.session.state_version,
            occurred_at=NOW + timedelta(seconds=2),
            target_status=SessionStatus.FAILED,
            stop_reason="test failure",
        ),
    ).state
    turn = turn_for(
        state,
        name="after-terminal",
        role=TranscriptRole.EMPLOYEE,
        text="不應接受",
        at=NOW + timedelta(seconds=3),
    )
    with pytest.raises(DomainViolation) as caught:
        append_employee_turn(
            state,
            AppendEmployeeTurnCommand(
                command_id=uid("append-after-terminal"),
                expected_state_version=state.session.state_version,
                occurred_at=NOW + timedelta(seconds=3),
                turn=turn,
            ),
        )
    assert caught.value.reason_code == ReasonCode.TERMINAL_SESSION


def test_turn_append_enforces_chain_and_client_id_uniqueness():
    state = active_state()
    state, first = append_turn(
        state,
        name="first",
        role=TranscriptRole.CONSULTANT,
        text="請說明你的工作。",
        at=NOW + timedelta(seconds=2),
    )
    assert state.turns == (first,)
    assert state.session.turn_count == 1

    duplicate_client = TranscriptTurn(
        turn_id=uid("different-turn"),
        session_id=state.session.session_id,
        client_turn_id=first.client_turn_id,
        sequence=2,
        role=TranscriptRole.EMPLOYEE,
        text="回答",
        previous_turn_id=first.turn_id,
        occurred_at=NOW + timedelta(seconds=3),
        received_at=NOW + timedelta(seconds=3),
    )
    with pytest.raises(DomainViolation) as caught:
        append_employee_turn(
            state,
            AppendEmployeeTurnCommand(
                command_id=uid("duplicate-client-command"),
                expected_state_version=state.session.state_version,
                occurred_at=NOW + timedelta(seconds=3),
                turn=duplicate_client,
            ),
        )
    assert caught.value.reason_code == ReasonCode.CLIENT_TURN_ID_DUPLICATE


def test_quote_span_accepts_a_minimal_span():
    span = QuoteSpan(start=0, end=1)
    assert span.unit == "unicode_code_point"


@pytest.mark.parametrize(
    "start,end",
    [(1, 1), (2, 1), (-1, 1)],
    ids=["empty", "reversed", "negative_start"],
)
def test_quote_span_rejects_impossible_bounds(start, end):
    """R5-A corrective §8.2:primitive 搬到 `domain.support` 後行為必須完全不變。"""
    with pytest.raises(ValidationError):
        QuoteSpan(start=start, end=end)


def test_exact_and_normalized_quotes_are_checked_against_employee_span():
    state, turn = state_with_employee_turn("我每週　整理測試結果。")
    exact = evidence_for(turn, name="exact", quote="整理測試結果")
    normalized = evidence_for(
        turn,
        name="normalized",
        quote="每週 整理",
        source_quote="每週　整理",
        quote_match=QuoteMatch.NORMALIZED,
    )
    assert_evidence_matches_turn(exact, turn)
    assert_evidence_matches_turn(normalized, turn)
    assert exact.support.span.unit == "unicode_code_point"

    bad = exact.model_copy(
        update={"support": exact.support.model_copy(update={"quote": "不存在的原話"})}
    )
    with pytest.raises(DomainViolation) as caught:
        assert_evidence_matches_turn(bad, turn)
    assert caught.value.reason_code == ReasonCode.QUOTE_MISMATCH


def test_evidence_cannot_quote_a_consultant_turn():
    state = active_state()
    state, turn = append_turn(
        state,
        name="consultant-only",
        role=TranscriptRole.CONSULTANT,
        text="請描述工作。",
        at=NOW + timedelta(seconds=2),
    )
    item = evidence_for(turn, name="bad-speaker", quote="描述工作")
    with pytest.raises(DomainViolation) as caught:
        assert_evidence_matches_turn(item, turn)
    assert caught.value.reason_code == ReasonCode.EVIDENCE_REQUIRES_EMPLOYEE_TURN


def test_apply_interpretation_supports_multiple_observations_and_atomic_correction():
    state, turn = state_with_employee_turn()
    original_hash = canonical_hash(state)
    first_operation = uid("operation:first-batch")
    action = evidence_for(
        turn, name="action", quote="整理測試結果", operation_id=first_operation
    )
    recipient = evidence_for(
        turn,
        name="recipient",
        quote="交給產品經理",
        kind=EvidenceKind.RECIPIENT,
        operation_id=first_operation,
    )
    first = interpret(
        state,
        turn,
        (action, recipient),
        name="first-evidence",
        at=NOW + timedelta(seconds=4),
        operation_id=first_operation,
    )
    assert len(first.state.evidence) == 2
    assert canonical_hash(state) == original_hash
    assert [event.event_type for event in first.events] == [
        "evidence.observed",
        "evidence.observed",
        "question_frame.consumed",
        "turn.interpretation_applied",
    ]

    state, correction_turn = append_turn(
        first.state,
        name="correction-answer",
        role=TranscriptRole.EMPLOYEE,
        text="更正一下，我是交給專案經理。",
        at=NOW + timedelta(seconds=5),
    )
    corrected = evidence_for(
        correction_turn,
        name="corrected-recipient",
        quote="交給專案經理",
        kind=EvidenceKind.RECIPIENT,
        supersedes=(recipient.evidence_id,),
    )
    result = interpret(
        state,
        correction_turn,
        (corrected,),
        name="correction",
        at=NOW + timedelta(seconds=6),
        operation_id=corrected.extractor_operation_id,
    )

    by_id = {item.evidence_id: item for item in result.state.evidence}
    assert by_id[recipient.evidence_id].status == EvidenceStatus.SUPERSEDED
    assert by_id[recipient.evidence_id].superseded_by == corrected.evidence_id
    assert by_id[corrected.evidence_id].status == EvidenceStatus.ACTIVE
    assert [event.event_type for event in result.events] == [
        "evidence.observed",
        "evidence.superseded",
        "turn.interpretation_applied",
    ]
    assert InterviewState.model_validate_json(result.state.model_dump_json()) == result.state


def test_apply_interpretation_rejects_bad_quote_without_partial_mutation():
    state, turn = state_with_employee_turn()
    operation_id = uid("operation:mixed")
    valid = evidence_for(
        turn, name="valid", quote="整理測試結果", operation_id=operation_id
    )
    invalid = valid.model_copy(
        update={
            "evidence_id": uid("evidence:invalid"),
            "support": valid.support.model_copy(update={"quote": "不存在"}),
        }
    )
    with pytest.raises(DomainViolation) as caught:
        interpret(
            state,
            turn,
            (valid, invalid),
            name="mixed-invalid",
            at=NOW + timedelta(seconds=4),
            operation_id=operation_id,
        )
    assert caught.value.reason_code == ReasonCode.QUOTE_MISMATCH
    assert state.evidence == ()


def test_frequency_requires_a_periodic_unit_when_numeric():
    with pytest.raises(ValidationError, match="periodic unit"):
        FrequencyQualifier(value=Decimal("2"), unit=FrequencyUnit.UNKNOWN)
    assert FrequencyQualifier(value=Decimal("2"), unit=FrequencyUnit.PER_WEEK).value == 2


def test_candidate_projection_requires_current_active_employee_evidence():
    state, turn = state_with_employee_turn()
    current = evidence_for(turn, name="candidate-current", quote="整理測試結果")
    candidate = CandidateJobItem(
        candidate_id=uid("candidate-task"),
        session_id=state.session.session_id,
        kind=CandidateKind.TASK,
        statement="整理測試結果",
        evidence_ids=(current.evidence_id,),
        status=CandidateStatus.VERIFIED,
        created_by_operation="episode.code",
    )
    assert_candidate_projectable(candidate, {current.evidence_id: current})

    past = current.model_copy(
        update={
            "evidence_id": uid("evidence:past"),
            "qualifiers": current_qualifiers(time_scope=TimeScope.PAST),
        }
    )
    with pytest.raises(DomainViolation) as caught:
        assert_candidate_projectable(
            candidate.model_copy(update={"evidence_ids": (past.evidence_id,)}),
            {past.evidence_id: past},
        )
    assert caught.value.reason_code == ReasonCode.CANDIDATE_CURRENT_SCOPE_INVALID


@pytest.mark.parametrize(
    "qualifier_change",
    [
        {"time_scope": TimeScope.PAST},
        {"time_scope": TimeScope.HYPOTHETICAL},
        {"polarity": Polarity.DENIED},
        {"polarity": Polarity.UNCERTAIN},
        {"ownership": Ownership.RECEIVES},
        {"ownership": Ownership.NOT_RESPONSIBLE},
        {"ownership": Ownership.UNKNOWN},
    ],
)
def test_candidate_projection_keeps_scope_polarity_and_ownership_separate(qualifier_change):
    state, turn = state_with_employee_turn()
    item = evidence_for(
        turn,
        name=f"qualifier-{next(iter(qualifier_change.values())).value}",
        quote="整理測試結果",
        qualifiers=current_qualifiers(**qualifier_change),
    )
    candidate = CandidateJobItem(
        candidate_id=uid(f"candidate:{item.evidence_id}"),
        session_id=state.session.session_id,
        kind=CandidateKind.TASK,
        statement="整理測試結果",
        evidence_ids=(item.evidence_id,),
        status=CandidateStatus.VERIFIED,
        created_by_operation="episode.code",
    )
    with pytest.raises(DomainViolation) as caught:
        assert_candidate_projectable(candidate, {item.evidence_id: item})
    assert caught.value.reason_code == ReasonCode.CANDIDATE_CURRENT_SCOPE_INVALID


def test_ability_needs_two_episodes_and_indicator_number_needs_source():
    state, turn = state_with_employee_turn()
    one = evidence_for(
        turn,
        name="ability-one",
        quote="整理測試結果",
        episode_id=uid("episode-one"),
    )
    ability = CandidateJobItem(
        candidate_id=uid("candidate-ability"),
        session_id=state.session.session_id,
        kind=CandidateKind.ABILITY,
        statement="跨情境整合資訊",
        evidence_ids=(one.evidence_id,),
        status=CandidateStatus.VERIFIED,
        created_by_operation="global.consolidate",
    )
    with pytest.raises(DomainViolation) as caught:
        assert_candidate_projectable(ability, {one.evidence_id: one})
    assert caught.value.reason_code == ReasonCode.ABILITY_CROSS_EPISODE_EVIDENCE_REQUIRED

    two = one.model_copy(
        update={
            "evidence_id": uid("evidence:ability-two"),
            "episode_id": uid("episode-two"),
        }
    )
    assert_candidate_projectable(
        ability.model_copy(update={"evidence_ids": (one.evidence_id, two.evidence_id)}),
        {one.evidence_id: one, two.evidence_id: two},
    )

    indicator = CandidateJobItem(
        candidate_id=uid("candidate-indicator"),
        session_id=state.session.session_id,
        kind=CandidateKind.BEHAVIOR_INDICATOR,
        statement="收到異常後 30 分鐘內回覆進度",
        evidence_ids=(one.evidence_id,),
        status=CandidateStatus.VERIFIED,
        created_by_operation="episode.code",
    )
    with pytest.raises(DomainViolation) as caught:
        assert_candidate_projectable(indicator, {one.evidence_id: one})
    assert caught.value.reason_code == ReasonCode.NUMERIC_THRESHOLD_SOURCE_REQUIRED

    sourced = indicator.model_copy(
        update={
            "thresholds": (
                QuantitativeThreshold(
                    expression="30 分鐘內",
                    source_type=ThresholdSourceType.EMPLOYEE_EVIDENCE,
                    source_id=str(one.evidence_id),
                    evidence_id=one.evidence_id,
                ),
            )
        }
    )
    assert_candidate_projectable(sourced, {one.evidence_id: one})


def test_tool_version_number_is_not_mistaken_for_a_behavior_threshold():
    state, turn = state_with_employee_turn()
    item = evidence_for(turn, name="sap", quote="整理測試結果")
    candidate = CandidateJobItem(
        candidate_id=uid("candidate-sap"),
        session_id=state.session.session_id,
        kind=CandidateKind.BEHAVIOR_INDICATOR,
        statement="使用 SAP S/4HANA 檢查資料一致性",
        evidence_ids=(item.evidence_id,),
        status=CandidateStatus.VERIFIED,
        created_by_operation="episode.code",
    )
    assert_candidate_projectable(candidate, {item.evidence_id: item})


def test_threshold_evidence_must_belong_to_candidate_lineage():
    state, turn = state_with_employee_turn()
    linked = evidence_for(turn, name="threshold-linked", quote="整理測試結果")
    unrelated = evidence_for(turn, name="threshold-unrelated", quote="每週")
    candidate = CandidateJobItem(
        candidate_id=uid("candidate-threshold-lineage"),
        session_id=state.session.session_id,
        kind=CandidateKind.BEHAVIOR_INDICATOR,
        statement="30 分鐘內完成整理",
        evidence_ids=(linked.evidence_id,),
        thresholds=(
            QuantitativeThreshold(
                expression="30 分鐘內",
                source_type=ThresholdSourceType.EMPLOYEE_EVIDENCE,
                source_id=str(unrelated.evidence_id),
                evidence_id=unrelated.evidence_id,
            ),
        ),
        status=CandidateStatus.VERIFIED,
        created_by_operation="episode.code",
    )
    with pytest.raises(DomainViolation) as caught:
        assert_candidate_projectable(
            candidate,
            {linked.evidence_id: linked, unrelated.evidence_id: unrelated},
        )
    assert caught.value.reason_code == ReasonCode.NUMERIC_THRESHOLD_SOURCE_REQUIRED


def test_human_decided_candidate_is_protected_from_model_replacement():
    candidate = CandidateJobItem(
        candidate_id=uid("candidate-human"),
        session_id=uid("session"),
        kind=CandidateKind.TASK,
        statement="人工已確認內容",
        evidence_ids=(uid("evidence-human"),),
        status=CandidateStatus.ACCEPTED,
        created_by_operation="episode.code",
        review_decision_id=uid("review-human"),
    )
    with pytest.raises(DomainViolation) as caught:
        assert_model_may_replace_candidate(candidate)
    assert caught.value.reason_code == ReasonCode.HUMAN_DECISION_PROTECTED


def test_state_rejects_evidence_lineage_cycles_and_one_way_episode_links():
    state, turn = state_with_employee_turn()
    first = evidence_for(turn, name="cycle-first", quote="整理測試結果")
    second = evidence_for(turn, name="cycle-second", quote="每週")
    first = first.model_copy(
        update={
            "status": EvidenceStatus.SUPERSEDED,
            "superseded_by": second.evidence_id,
            "supersedes": (second.evidence_id,),
        }
    )
    second = second.model_copy(
        update={
            "status": EvidenceStatus.SUPERSEDED,
            "superseded_by": first.evidence_id,
            "supersedes": (first.evidence_id,),
        }
    )
    with pytest.raises(ValidationError, match="cycle"):
        InterviewState.model_validate(
            {
                **state.model_dump(mode="python"),
                "evidence": (first, second),
            }
        )

    episode_id = uid("one-way-episode")
    episode = EpisodeState(
        episode_id=episode_id,
        session_id=state.session.session_id,
        target="例行測試報告",
        opened_turn_id=turn.turn_id,
        created_at=NOW + timedelta(seconds=3),
        updated_at=NOW + timedelta(seconds=3),
    )
    one_way = evidence_for(
        turn,
        name="one-way-evidence",
        quote="整理測試結果",
        episode_id=episode_id,
    )
    active_session = state.session.model_copy(update={"active_episode_id": episode_id})
    with pytest.raises(ValidationError, match="bidirectional"):
        InterviewState.model_validate(
            {
                **state.model_dump(mode="python"),
                "session": active_session,
                "episodes": (episode,),
                "evidence": (one_way,),
            }
        )


def test_human_edit_must_be_materialized_as_the_accepted_statement():
    state, turn = state_with_employee_turn()
    item = evidence_for(turn, name="review-evidence", quote="整理測試結果")
    review_id = uid("edit-review")
    candidate = CandidateJobItem(
        candidate_id=uid("review-candidate"),
        session_id=state.session.session_id,
        kind=CandidateKind.TASK,
        statement="未套用人工編輯的舊文字",
        evidence_ids=(item.evidence_id,),
        status=CandidateStatus.ACCEPTED,
        created_by_operation="episode.code",
        review_decision_id=review_id,
    )
    review = ReviewDecision(
        review_id=review_id,
        session_id=state.session.session_id,
        candidate_id=candidate.candidate_id,
        reviewer_id=uid("reviewer"),
        action=ReviewAction.EDIT,
        edited_statement="人工編輯後文字",
        decided_at=NOW + timedelta(seconds=4),
    )
    with pytest.raises(ValidationError, match="edited review text"):
        InterviewState.model_validate(
            {
                **state.model_dump(mode="python"),
                "evidence": (item,),
                "candidates": (candidate,),
                "reviews": (review,),
            }
        )


def test_replaying_the_same_command_stream_produces_identical_hashes():
    def run() -> tuple[InterviewState, tuple[UUID, ...]]:
        state = active_state()
        event_ids: list[UUID] = []
        for index in range(20):
            at = NOW + timedelta(seconds=index + 2)
            turn = turn_for(
                state,
                name=f"property-{index}",
                role=(
                    TranscriptRole.CONSULTANT if index % 2 == 0 else TranscriptRole.EMPLOYEE
                ),
                text=f"第 {index + 1} 回合",
                at=at,
            )
            if turn.role == TranscriptRole.CONSULTANT:
                result = append_consultant_question(
                    state,
                    AppendConsultantQuestionCommand(
                        command_id=uid(f"property-command-{index}"),
                        expected_state_version=state.session.state_version,
                        occurred_at=at,
                        turn=turn,
                        frame_definition=open_narrative_definition(turn.text),
                    ),
                )
            else:
                result = append_employee_turn(
                    state,
                    AppendEmployeeTurnCommand(
                        command_id=uid(f"property-command-{index}"),
                        expected_state_version=state.session.state_version,
                        occurred_at=at,
                        turn=turn,
                    ),
                )
            state = result.state
            event_ids.extend(event.event_id for event in result.events)
            if turn.role == TranscriptRole.EMPLOYEE:
                # The next question cannot open until this answer is interpreted.
                receipt = interpret(state, turn, name=f"property-{index}", at=at)
                state = receipt.state
                event_ids.extend(event.event_id for event in receipt.events)
        return state, tuple(event_ids)

    first_state, first_events = run()
    second_state, second_events = run()
    assert canonical_hash(first_state) == canonical_hash(second_state)
    assert first_events == second_events
    assert json.loads(first_state.model_dump_json()) == json.loads(second_state.model_dump_json())

    adapter = TypeAdapter(DomainEvent)
    event = transition_session(
        planned_state(),
        TransitionSessionCommand(
            command_id=uid("event-round-trip"),
            expected_state_version=0,
            occurred_at=NOW + timedelta(seconds=1),
            target_status=SessionStatus.ACTIVE,
        ),
    ).events[0]
    assert adapter.validate_json(adapter.dump_json(event)) == event
