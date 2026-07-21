"""Case inputs -> domain commands, pure state materialization and reference gate.

V3-5 §6.3/§6.6:fixture 只能經公開 reducer 命令重建(禁止直接改 state_json)。
本模組的純函式部分(不碰 DB)供 E3 fixtures 測試與 E4 durable replay 共用:
兩邊都用 ``setup_commands()`` 的同一組命令,E4 只是把它們送進
``apply_durable_command``。Reference gate 用 production ContextBuilder/
verifier/reducer 驗證每個 case 的 known-good output;任何一項不過表示
case/gold/fixture 壞掉,不得發 live request。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from app.interview_vnext.application.context_builder import ContextBuilder
from app.interview_vnext.application.turn_interpret import (
    accepted_evidence,
    verify_turn_interpret_output,
)
from app.interview_vnext.domain.commands import (
    AppendTranscriptTurnCommand,
    ApplyEvidenceCommand,
    CommandBase,
    OpenEpisodeCommand,
    TransitionSessionCommand,
)
from app.interview_vnext.domain.evidence import (
    Evidence,
    EvidenceQualifiers,
    EvidenceStatus,
    FrequencyQualifier,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.reducers import (
    append_transcript_turn,
    apply_evidence,
    open_episode,
    transition_session,
)
from app.interview_vnext.domain.session import SessionStatus, session_at
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.support import QuoteMatch, QuoteSpan
from app.interview_vnext.domain.transcript import TranscriptTurn
from app.interview_vnext.llm.context import (
    TURN_INTERPRET_CONTEXT_POLICY_V1,
    ContextBuildResult,
)
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.turn_interpret import (
    EvidenceQualifiersProposal,
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)

from .contracts import (
    ExpectedCommit,
    GoldRequirement,
    QualifierExact,
    QualifierNotApplicable,
    QualifierOneOf,
    TurnEvalGoldObservation,
    TurnEvalReferenceOutput,
)
from .identities import (
    TrialScopedIds,
    episode_uuid,
    prior_evidence_uuid,
    trial_scoped_ids,
    turn_uuid,
)
from .loader import TurnEvalCaseGold, TurnEvalCaseInputs, quote_occurrences


WORKFLOW_VERSION = "1.0.0"


class ReferenceGateError(AssertionError):
    """Reference output failed the production gate — the case itself is broken."""


def _exact_span(text: str, quote: str, occurrence: int) -> QuoteSpan:
    positions: list[int] = []
    start = 0
    while True:
        found = text.find(quote, start)
        if found < 0:
            break
        positions.append(found)
        start = found + 1
    if occurrence < 1 or occurrence > len(positions):
        raise ReferenceGateError(
            f"quote occurrence {occurrence} unresolvable ({len(positions)} present)"
        )
    begin = positions[occurrence - 1]
    return QuoteSpan(start=begin, end=begin + len(quote))


def domain_qualifiers(proposal: EvidenceQualifiersProposal) -> EvidenceQualifiers:
    """Provider-facing qualifier proposal -> domain qualifiers (Decimal 轉換)。"""

    frequency = proposal.frequency
    return EvidenceQualifiers(
        time_scope=proposal.time_scope,
        typicality=proposal.typicality,
        polarity=proposal.polarity,
        frequency=FrequencyQualifier(
            value=Decimal(frequency.value) if frequency.value is not None else None,
            unit=frequency.unit,
            verbatim=frequency.verbatim,
        ),
        importance=proposal.importance,
        ownership=proposal.ownership,
    )


@dataclass(frozen=True)
class SetupStep:
    """One durable command plus the stage/idempotency identity E4 will persist."""

    name: str
    command: CommandBase
    stage: str


def setup_commands(
    inputs: TurnEvalCaseInputs, *, ids: TrialScopedIds, base_time: datetime
) -> tuple[SetupStep, ...]:
    """§6.3 fixture order:activate → transcript replay → open episode →
    prior evidence。每步 expected_state_version 遞增、occurred_at 嚴格遞增。"""

    trial_id = ids.trial_id
    steps: list[SetupStep] = []
    version = 0

    def at(seconds: int) -> datetime:
        return base_time + timedelta(seconds=seconds)

    steps.append(
        SetupStep(
            name="activate",
            command=TransitionSessionCommand(
                command_id=uuid5(trial_id, "command/activate"),
                expected_state_version=version,
                occurred_at=at(1),
                target_status=SessionStatus.ACTIVE,
            ),
            stage="turn.receive",
        )
    )
    version += 1

    fixture = inputs.initial_fixture
    previous_turn_id: UUID | None = None
    last_offset = 1
    for record in inputs.transcript:
        turn_id = turn_uuid(trial_id, record.turn_key)
        occurred = at(1 + record.occurred_offset_seconds)
        last_offset = 1 + record.occurred_offset_seconds
        steps.append(
            SetupStep(
                name=f"append/{record.turn_key}",
                command=AppendTranscriptTurnCommand(
                    command_id=uuid5(trial_id, f"command/append/{record.turn_key}"),
                    expected_state_version=version,
                    occurred_at=occurred,
                    turn=TranscriptTurn(
                        turn_id=turn_id,
                        session_id=ids.session_id,
                        client_turn_id=record.turn_key,
                        sequence=record.sequence,
                        role=record.role,
                        text=record.text,
                        previous_turn_id=previous_turn_id,
                        locale=record.locale,
                        occurred_at=occurred,
                        received_at=occurred,
                    ),
                ),
                stage="turn.receive",
            )
        )
        previous_turn_id = turn_id
        version += 1
        # production reducer 要求 episode 在其 opened turn 為 transcript tail 時
        # 開啟(§6.3 的「replay 後再開」在此 interleave 才 replay 得動)。
        if (
            fixture.open_episode is not None
            and fixture.open_episode.opened_turn_key == record.turn_key
        ):
            steps.append(
                SetupStep(
                    name="open-episode",
                    command=OpenEpisodeCommand(
                        command_id=uuid5(trial_id, "command/open-episode"),
                        expected_state_version=version,
                        occurred_at=at(last_offset + 1),
                        episode_id=episode_uuid(
                            trial_id, fixture.open_episode.episode_key
                        ),
                        target=fixture.open_episode.target,
                        opened_turn_id=turn_id,
                    ),
                    stage="episode.code",
                )
            )
            version += 1
            last_offset += 1

    turns_by_key = {record.turn_key: record for record in inputs.transcript}
    prior_extractor = uuid5(trial_id, "operation/prior-evidence")
    grouped: dict[str, list] = {}
    for item in fixture.prior_evidence:
        grouped.setdefault(item.source_turn_key, []).append(item)
    for index, (turn_key, items) in enumerate(grouped.items()):
        source = turns_by_key[turn_key]
        observations = tuple(
            Evidence(
                evidence_id=prior_evidence_uuid(trial_id, item.evidence_key),
                session_id=ids.session_id,
                turn_id=turn_uuid(trial_id, turn_key),
                episode_id=(
                    episode_uuid(trial_id, item.episode_key)
                    if item.episode_key is not None
                    else None
                ),
                subject=item.subject,
                kind=item.kind,
                claim=item.claim,
                quote=item.quote,
                span=_exact_span(source.text, item.quote, item.quote_occurrence),
                quote_match=QuoteMatch.EXACT,
                qualifiers=domain_qualifiers(item.qualifiers),
                extractor_operation_id=prior_extractor,
            )
            for item in items
        )
        steps.append(
            SetupStep(
                name=f"prior-evidence/{turn_key}",
                command=ApplyEvidenceCommand(
                    command_id=uuid5(trial_id, f"command/prior/{turn_key}"),
                    expected_state_version=version,
                    occurred_at=at(last_offset + 2 + index),
                    turn_id=turn_uuid(trial_id, turn_key),
                    observations=observations,
                ),
                stage="turn.interpret",
            )
        )
        version += 1
    return tuple(steps)


_PURE_REDUCERS = {
    TransitionSessionCommand: transition_session,
    AppendTranscriptTurnCommand: append_transcript_turn,
    OpenEpisodeCommand: open_episode,
    ApplyEvidenceCommand: apply_evidence,
}


def materialize_pure_state(
    inputs: TurnEvalCaseInputs, *, ids: TrialScopedIds, base_time: datetime
) -> InterviewState:
    """No-DB replay of the same setup commands through pure reducers."""

    state = InterviewState(
        session=session_at(
            session_id=ids.session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version=WORKFLOW_VERSION,
            reference_snapshot_id=inputs.reference_snapshot.snapshot_id,
            now=base_time,
        )
    )
    for step in setup_commands(inputs, ids=ids, base_time=base_time):
        reducer = _PURE_REDUCERS[type(step.command)]
        state = reducer(state, step.command).state
    return state


def materialize_reference_output(
    inputs: TurnEvalCaseInputs,
    reference: TurnEvalReferenceOutput,
    *,
    trial_id: UUID,
) -> TurnInterpretOutput:
    """Inject trial-scoped correction target UUIDs from logical bindings (§6.6)."""

    prior_keys = {
        item.evidence_key for item in inputs.initial_fixture.prior_evidence
    }
    observations = []
    for proposal in reference.output.observations:
        targets = reference.correction_target_bindings.get(proposal.proposal_key, ())
        unknown_keys = set(targets) - prior_keys
        if unknown_keys:
            raise ReferenceGateError(
                f"binding for {proposal.proposal_key!r} references unknown prior "
                f"evidence {sorted(unknown_keys)}"
            )
        observations.append(
            proposal.model_copy(
                update={
                    "correction_target_evidence_ids": tuple(
                        prior_evidence_uuid(trial_id, key) for key in targets
                    )
                }
            )
        )
    return reference.output.model_copy(update={"observations": tuple(observations)})


@dataclass(frozen=True)
class ReferenceGateResult:
    ids: TrialScopedIds
    state_before: InterviewState
    state_before_hash: str
    state_after: InterviewState
    state_after_hash: str
    context: ContextBuildResult
    output: TurnInterpretOutput
    report: TurnInterpretVerificationReport
    accepted_count: int


def _anchor_covers(
    observation, gold: TurnEvalGoldObservation, target_text: str
) -> bool:
    span = _exact_span(target_text, observation.quote, observation.quote_occurrence)
    for anchor in gold.source_anchors:
        if (
            observation.quote == anchor.quote
            and observation.quote_occurrence == anchor.occurrence
        ):
            return True
        anchor_span = _exact_span(target_text, anchor.quote, anchor.occurrence)
        if anchor_span.start <= span.start and span.end <= anchor_span.end:
            return True
    return False


def _observation_matches_gold(
    observation, gold: TurnEvalGoldObservation, target_text: str
) -> bool:
    if observation.subject not in gold.allowed_subjects:
        return False
    if observation.kind not in gold.allowed_kinds:
        return False
    return _anchor_covers(observation, gold, target_text)


def run_pure_reference_gate(
    inputs: TurnEvalCaseInputs,
    evaluation: TurnEvalCaseGold,
    *,
    trial_id: UUID,
    base_time: datetime,
) -> ReferenceGateResult:
    """§6.6 reference gate(純函式版):production context/verifier/reducer。

    「portable schema」由 provider 在 wire 上強制;此處等價地走
    ``TurnInterpretOutput`` local contract(portable schema 由同一 model 匯出)。
    """

    ids = trial_scoped_ids(trial_id)
    gold = evaluation.gold
    operation = turn_interpret_operation()
    state_before = materialize_pure_state(inputs, ids=ids, base_time=base_time)
    state_before_hash = canonical_hash(state_before)
    target_key = inputs.case.target_turn_key
    target_text = inputs.transcript[-1].text
    context = ContextBuilder().build_turn_interpret(
        state=state_before,
        employee_turn_id=turn_uuid(trial_id, target_key),
        operation_id=ids.operation_id,
        operation_definition_hash=operation.definition_hash,
        policy=TURN_INTERPRET_CONTEXT_POLICY_V1,
    )
    output = materialize_reference_output(
        inputs, evaluation.reference_output, trial_id=trial_id
    )
    output = TurnInterpretOutput.model_validate(output.model_dump(mode="json"))
    report = verify_turn_interpret_output(
        output=output, context=context.packet, operation_id=ids.operation_id
    )
    if report.dropped_count != 0:
        rejected = [
            (item.proposal_key, [code.value for code in item.reason_codes])
            for item in report.decisions
            if not item.accepted
        ]
        raise ReferenceGateError(
            f"{inputs.case.case_id}: verifier rejected reference proposals {rejected}"
        )
    if report.user_signal not in gold.allowed_user_signals:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: user_signal {report.user_signal} not allowed"
        )
    if report.episode_signal not in gold.allowed_episode_signals:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: episode_signal {report.episode_signal} not allowed"
        )
    produced_reasons = {item.reason_code for item in output.insufficiencies}
    missing_reasons = set(gold.required_insufficiencies) - produced_reasons
    if missing_reasons:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: missing required insufficiencies "
            f"{sorted(reason.value for reason in missing_reasons)}"
        )
    extra_reasons = produced_reasons - set(gold.required_insufficiencies) - set(
        gold.allowed_insufficiencies
    )
    if extra_reasons:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: unexpected insufficiencies "
            f"{sorted(reason.value for reason in extra_reasons)}"
        )

    evidence = accepted_evidence(
        report=report,
        session_id=ids.session_id,
        turn_id=turn_uuid(trial_id, target_key),
        operation_id=ids.operation_id,
    )
    if gold.expected_commit == ExpectedCommit.NO_OP:
        if evidence:
            raise ReferenceGateError(
                f"{inputs.case.case_id}: no-op case accepted evidence"
            )
        state_after = state_before
    else:
        if not evidence:
            raise ReferenceGateError(
                f"{inputs.case.case_id}: evidence case accepted nothing"
            )
        command = ApplyEvidenceCommand(
            command_id=uuid5(ids.operation_id, "command/evidence"),
            expected_state_version=state_before.session.state_version,
            occurred_at=state_before.session.updated_at + timedelta(seconds=5),
            turn_id=turn_uuid(trial_id, target_key),
            observations=evidence,
        )
        state_after = apply_evidence(state_before, command).state
    state_after_hash = canonical_hash(state_after)

    expectation = gold.state_expectation
    if expectation.state_hash_changed != (state_after_hash != state_before_hash):
        raise ReferenceGateError(
            f"{inputs.case.case_id}: state hash change mismatch "
            f"(expected changed={expectation.state_hash_changed})"
        )
    status_by_id = {item.evidence_id: item.status for item in state_after.evidence}
    for key in expectation.prior_evidence_superseded_keys:
        status = status_by_id.get(prior_evidence_uuid(trial_id, key))
        if status != EvidenceStatus.SUPERSEDED:
            raise ReferenceGateError(
                f"{inputs.case.case_id}: prior evidence {key!r} not superseded "
                f"(status={status})"
            )
    for key in expectation.forbidden_superseded_keys:
        status = status_by_id.get(prior_evidence_uuid(trial_id, key))
        if status != EvidenceStatus.ACTIVE:
            raise ReferenceGateError(
                f"{inputs.case.case_id}: prior evidence {key!r} must stay active "
                f"(status={status})"
            )

    # required recall = 1、precision = 1(§6.6):以 gold anchors 做靜態一對一檢查
    required = [
        item
        for item in gold.observations
        if item.requirement == GoldRequirement.REQUIRED
    ]
    for gold_item in required:
        if not any(
            _observation_matches_gold(observation, gold_item, target_text)
            for observation in output.observations
        ):
            raise ReferenceGateError(
                f"{inputs.case.case_id}: required gold {gold_item.gold_id!r} is not "
                "covered by the reference output"
            )
    for observation in output.observations:
        if not any(
            _observation_matches_gold(observation, gold_item, target_text)
            for gold_item in gold.observations
        ):
            raise ReferenceGateError(
                f"{inputs.case.case_id}: reference proposal "
                f"{observation.proposal_key!r} matches no gold observation"
            )
        targets = set(observation.correction_target_evidence_ids)
        for gold_item in gold.observations:
            if not gold_item.correction_target_evidence_keys:
                continue
            if _observation_matches_gold(observation, gold_item, target_text):
                expected_targets = {
                    prior_evidence_uuid(trial_id, key)
                    for key in gold_item.correction_target_evidence_keys
                }
                if targets != expected_targets:
                    raise ReferenceGateError(
                        f"{inputs.case.case_id}: correction targets mismatch for "
                        f"{observation.proposal_key!r}"
                    )

    # gold qualifier expectations must be satisfiable by the reference output
    for gold_item in required:
        matched = [
            observation
            for observation in output.observations
            if _observation_matches_gold(observation, gold_item, target_text)
        ]
        for observation in matched:
            _check_qualifier_expectations(
                inputs.case.case_id, gold_item, observation
            )

    return ReferenceGateResult(
        ids=ids,
        state_before=state_before,
        state_before_hash=state_before_hash,
        state_after=state_after,
        state_after_hash=state_after_hash,
        context=context,
        output=output,
        report=report,
        accepted_count=report.accepted_count,
    )


_QUALIFIER_FIELDS = {
    "time_scope": lambda q: q.time_scope.value,
    "typicality": lambda q: q.typicality.value,
    "polarity": lambda q: q.polarity.value,
    "frequency_unit": lambda q: q.frequency.unit.value,
    "frequency_value": lambda q: q.frequency.value,
    "importance": lambda q: q.importance.value,
    "ownership": lambda q: q.ownership.value,
}


def _check_qualifier_expectations(
    case_id: str, gold_item: TurnEvalGoldObservation, observation
) -> None:
    for field_name, getter in _QUALIFIER_FIELDS.items():
        expectation = getattr(gold_item.qualifiers, field_name)
        if isinstance(expectation, QualifierNotApplicable):
            continue
        actual = getter(observation.qualifiers)
        if field_name == "frequency_value":
            actual_text = actual if actual is not None else None
            if isinstance(expectation, QualifierExact):
                if actual_text is None or Decimal(actual_text) != Decimal(
                    expectation.value
                ):
                    raise ReferenceGateError(
                        f"{case_id}: {gold_item.gold_id} frequency_value "
                        f"expected {expectation.value!r}, got {actual_text!r}"
                    )
            elif isinstance(expectation, QualifierOneOf):
                if actual_text is None or all(
                    Decimal(actual_text) != Decimal(value)
                    for value in expectation.values
                ):
                    raise ReferenceGateError(
                        f"{case_id}: {gold_item.gold_id} frequency_value "
                        f"{actual_text!r} outside {expectation.values}"
                    )
            continue
        if isinstance(expectation, QualifierExact):
            if actual != expectation.value:
                raise ReferenceGateError(
                    f"{case_id}: {gold_item.gold_id} {field_name} expected "
                    f"{expectation.value!r}, got {actual!r}"
                )
        elif isinstance(expectation, QualifierOneOf):
            if actual not in expectation.values:
                raise ReferenceGateError(
                    f"{case_id}: {gold_item.gold_id} {field_name} {actual!r} "
                    f"outside {expectation.values}"
                )
