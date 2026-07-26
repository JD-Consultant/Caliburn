"""State-v3 eval fixture replay and production reference gate.

The planner is stateful on purpose: every non-target employee turn is followed
immediately by one adjudicated interpretation receipt before another consultant
question can be appended.  Pure and PostgreSQL replay consume the same steps.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid5

from app.interview_vnext.application.context_builder import ContextBuilder
from app.interview_vnext.application.operation_executor import CONTEXT_ARTIFACT_KIND
from app.interview_vnext.application.turn_interpret import (
    accepted_evidence,
    verify_turn_interpret_output,
)
from app.interview_vnext.domain.commands import (
    AppendConsultantQuestionCommand,
    AppendEmployeeTurnCommand,
    ApplyTurnInterpretationCommand,
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
from app.interview_vnext.domain.interpretation import (
    TurnInsufficiencyCode,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.question_frame import (
    QuestionMode,
    build_question_frame_definition,
)
from app.interview_vnext.domain.reducers import (
    ReductionResult,
    append_consultant_question,
    append_employee_turn,
    apply_turn_interpretation,
    open_episode,
    transition_session,
)
from app.interview_vnext.domain.session import SessionStatus, session_at
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.support import (
    LiteralEmployeeSpanSupport,
    QuoteMatch,
    QuoteSpan,
)
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.domain.turn_identity import turn_interpretation_id
from app.interview_vnext.llm.context import (
    TURN_INTERPRET_CONTEXT_POLICY_V2,
    ContextBuildResult,
)
from app.interview_vnext.llm.operation_documents import turn_interpret_operation
from app.interview_vnext.llm.turn_interpret import (
    EvidenceQualifiersProposal,
    TurnInterpretOutput,
    TurnInterpretVerificationReport,
)
from app.interview_vnext.observability.artifacts import ArtifactRecord, build_inline_artifact

from .contracts import (
    SEED_ARTIFACT_KIND,
    ExpectedCommit,
    GoldRequirement,
    QualifierExact,
    QualifierNotApplicable,
    QualifierOneOf,
    TurnEvalGoldObservation,
    TurnEvalPriorEvidenceBinding,
    TurnEvalPriorInterpretationSeed,
    TurnEvalPriorInterpretationSeedOutput,
    TurnEvalPriorInterpretationSeedReport,
    TurnEvalReferenceOutput,
)
from .identities import (
    TrialScopedIds,
    episode_uuid,
    prior_evidence_uuid,
    prior_operation_uuid,
    trial_scoped_ids,
    turn_uuid,
)
from .loader import TurnEvalCaseGold, TurnEvalCaseInputs


WORKFLOW_VERSION = "1.0.0"
SUITE_VERSION = "turn-interpret-c1-v2-pilot.v1"
CONTEXT_PACKET_SCHEMA_ID = "https://caliburn.local/schemas/context-packet.v2.schema.json"
SEED_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-eval-prior-interpretation-seed.v1.schema.json"
)


class ReferenceGateError(AssertionError):
    """A known-good fixture failed a production contract."""


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
class PriorEvidenceIdentity:
    evidence_key: str
    source_turn_key: str
    observation_index: int
    operation_id: UUID
    evidence_id: UUID


def prior_evidence_identities(
    inputs: TurnEvalCaseInputs, *, trial_id: UUID
) -> tuple[PriorEvidenceIdentity, ...]:
    positions: dict[str, int] = {}
    identities: list[PriorEvidenceIdentity] = []
    for item in inputs.initial_fixture.prior_evidence:
        index = positions.get(item.source_turn_key, 0) + 1
        positions[item.source_turn_key] = index
        operation_id = prior_operation_uuid(trial_id, item.source_turn_key)
        identities.append(
            PriorEvidenceIdentity(
                evidence_key=item.evidence_key,
                source_turn_key=item.source_turn_key,
                observation_index=index,
                operation_id=operation_id,
                evidence_id=prior_evidence_uuid(
                    trial_id, item.source_turn_key, index
                ),
            )
        )
    return tuple(identities)


def prior_evidence_id_map(
    inputs: TurnEvalCaseInputs, *, trial_id: UUID
) -> dict[str, UUID]:
    return {
        item.evidence_key: item.evidence_id
        for item in prior_evidence_identities(inputs, trial_id=trial_id)
    }


@dataclass(frozen=True)
class SetupStep:
    name: str
    command: CommandBase
    stage: str
    additional_artifacts: tuple[ArtifactRecord, ...] = ()


@dataclass(frozen=True)
class SetupPlan:
    steps: tuple[SetupStep, ...]
    final_state: InterviewState
    prior_identities: tuple[PriorEvidenceIdentity, ...]


_PURE_REDUCERS = {
    TransitionSessionCommand: transition_session,
    AppendConsultantQuestionCommand: append_consultant_question,
    AppendEmployeeTurnCommand: append_employee_turn,
    OpenEpisodeCommand: open_episode,
    ApplyTurnInterpretationCommand: apply_turn_interpretation,
}


def build_setup_plan(
    inputs: TurnEvalCaseInputs, *, ids: TrialScopedIds, base_time: datetime
) -> SetupPlan:
    """Build and apply the one authoritative interleaved setup plan."""

    trial_id = ids.trial_id
    fixture = inputs.initial_fixture
    operation = turn_interpret_operation()
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
    steps: list[SetupStep] = []
    identity_by_key = {
        item.evidence_key: item
        for item in prior_evidence_identities(inputs, trial_id=trial_id)
    }
    prior_by_turn: dict[str, list] = {}
    for item in fixture.prior_evidence:
        prior_by_turn.setdefault(item.source_turn_key, []).append(item)

    def append(step: SetupStep) -> None:
        nonlocal state
        reducer = _PURE_REDUCERS[type(step.command)]
        state = reducer(state, step.command).state
        steps.append(step)

    append(
        SetupStep(
            name="activate",
            command=TransitionSessionCommand(
                command_id=uuid5(trial_id, "command/activate"),
                expected_state_version=state.session.state_version,
                occurred_at=base_time + timedelta(seconds=1),
                target_status=SessionStatus.ACTIVE,
            ),
            stage="turn.receive",
        )
    )

    previous_turn_id: UUID | None = None
    for record in inputs.transcript:
        turn_id = turn_uuid(trial_id, record.turn_key)
        occurred_at = base_time + timedelta(
            seconds=1 + record.occurred_offset_seconds
        )
        turn = TranscriptTurn(
            turn_id=turn_id,
            session_id=ids.session_id,
            client_turn_id=record.turn_key,
            sequence=record.sequence,
            role=record.role,
            text=record.text,
            previous_turn_id=previous_turn_id,
            locale=record.locale,
            occurred_at=occurred_at,
            received_at=occurred_at,
        )
        if record.role == TranscriptRole.CONSULTANT:
            command = AppendConsultantQuestionCommand(
                command_id=uuid5(trial_id, f"command/append/{record.turn_key}"),
                expected_state_version=state.session.state_version,
                occurred_at=occurred_at,
                turn=turn,
                frame_definition=build_question_frame_definition(
                    mode=QuestionMode.OPEN_NARRATIVE,
                    question_text=record.text,
                    targets=(),
                ),
            )
        else:
            command = AppendEmployeeTurnCommand(
                command_id=uuid5(trial_id, f"command/append/{record.turn_key}"),
                expected_state_version=state.session.state_version,
                occurred_at=occurred_at,
                turn=turn,
            )
        append(SetupStep(name=f"append/{record.turn_key}", command=command, stage="turn.receive"))
        previous_turn_id = turn_id

        if (
            fixture.open_episode is not None
            and fixture.open_episode.opened_turn_key == record.turn_key
        ):
            append(
                SetupStep(
                    name="open-episode",
                    command=OpenEpisodeCommand(
                        command_id=uuid5(trial_id, "command/open-episode"),
                        expected_state_version=state.session.state_version,
                        occurred_at=occurred_at + timedelta(microseconds=1),
                        episode_id=episode_uuid(
                            trial_id, fixture.open_episode.episode_key
                        ),
                        target=fixture.open_episode.target,
                        opened_turn_id=turn_id,
                    ),
                    stage="episode.code",
                )
            )

        if record.role != TranscriptRole.EMPLOYEE or record.turn_key == inputs.case.target_turn_key:
            continue
        declared = prior_by_turn[record.turn_key]
        prior_operation_id = prior_operation_uuid(trial_id, record.turn_key)
        context = ContextBuilder().build_turn_interpret(
            state=state,
            employee_turn_id=turn_id,
            operation_id=prior_operation_id,
            operation_definition_hash=operation.definition_hash,
            policy=TURN_INTERPRET_CONTEXT_POLICY_V2,
        )
        if context.packet.question_frame is None:
            raise ReferenceGateError(
                f"{inputs.case.case_id}: prior employee turn has no eligible frame"
            )
        observations: list[Evidence] = []
        bindings: list[TurnEvalPriorEvidenceBinding] = []
        for item in declared:
            identity = identity_by_key[item.evidence_key]
            evidence = Evidence(
                evidence_id=identity.evidence_id,
                session_id=ids.session_id,
                episode_id=(
                    episode_uuid(trial_id, item.episode_key)
                    if item.episode_key is not None
                    else None
                ),
                subject=item.subject,
                kind=item.kind,
                claim=item.claim,
                support=LiteralEmployeeSpanSupport(
                    employee_turn_id=turn_id,
                    quote=item.quote,
                    span=_exact_span(record.text, item.quote, item.quote_occurrence),
                    quote_match=QuoteMatch.EXACT,
                ),
                qualifiers=domain_qualifiers(item.qualifiers),
                extractor_operation_id=prior_operation_id,
            )
            observations.append(evidence)
            bindings.append(
                TurnEvalPriorEvidenceBinding(
                    evidence_key=item.evidence_key,
                    observation_index=identity.observation_index,
                    evidence_id=identity.evidence_id,
                )
            )
        seed_output = TurnEvalPriorInterpretationSeedOutput(
            initial_fixture_hash=canonical_hash(fixture),
            employee_turn_key=record.turn_key,
            observations=tuple(declared),
        )
        seed_report = TurnEvalPriorInterpretationSeedReport(
            output_hash=canonical_hash(seed_output),
            evidence_bindings=tuple(bindings),
            accepted_evidence_ids=tuple(item.evidence_id for item in bindings),
        )
        frame = context.packet.question_frame.frame
        seed = TurnEvalPriorInterpretationSeed(
            suite_version=SUITE_VERSION,
            case_id=inputs.case.case_id,
            trial_id=trial_id,
            employee_turn_id=turn_id,
            operation_id=prior_operation_id,
            question_frame_id=frame.question_frame_id,
            question_frame_definition_hash=frame.definition.definition_hash,
            context_packet_hash=canonical_hash(context.packet),
            output=seed_output,
            report=seed_report,
        )
        applied_at = occurred_at + timedelta(microseconds=1)
        receipt = TurnInterpretationRecord(
            interpretation_id=turn_interpretation_id(prior_operation_id),
            session_id=ids.session_id,
            employee_turn_id=turn_id,
            operation_id=prior_operation_id,
            question_frame_id=frame.question_frame_id,
            question_frame_definition_hash=frame.definition.definition_hash,
            context_packet_hash=seed.context_packet_hash,
            output_hash=canonical_hash(seed.output),
            verification_report_hash=canonical_hash(seed.report),
            accepted_evidence_ids=seed.report.accepted_evidence_ids,
            dialogue_act=seed.output.dialogue_act,
            episode_signal=seed.output.episode_signal,
            insufficiency_codes=seed.output.insufficiency_codes,
            applied_at=applied_at,
        )
        prior_command = ApplyTurnInterpretationCommand(
            command_id=uuid5(prior_operation_id, "command/turn-interpretation"),
            expected_state_version=state.session.state_version,
            occurred_at=applied_at,
            record=receipt,
            observations=tuple(observations),
        )
        context_artifact = build_inline_artifact(
            artifact_id=uuid5(prior_operation_id, "artifact/context-packet"),
            kind=CONTEXT_ARTIFACT_KIND,
            media_type="application/json",
            payload=context.packet,
            schema_id=CONTEXT_PACKET_SCHEMA_ID,
            run_id=ids.run_id,
            session_id=ids.session_id,
            turn_id=turn_id,
            operation_id=prior_operation_id,
            created_at=applied_at,
            contains_test_data=True,
        )
        seed_artifact = build_inline_artifact(
            artifact_id=uuid5(prior_operation_id, "artifact/seed"),
            kind=SEED_ARTIFACT_KIND,
            media_type="application/json",
            payload=seed,
            schema_id=SEED_SCHEMA_ID,
            run_id=ids.run_id,
            session_id=ids.session_id,
            turn_id=turn_id,
            operation_id=prior_operation_id,
            created_at=applied_at,
            contains_test_data=True,
        )
        append(
            SetupStep(
                name=f"prior-interpretation/{record.turn_key}",
                command=prior_command,
                stage="turn.interpret",
                additional_artifacts=(context_artifact, seed_artifact),
            )
        )

    return SetupPlan(
        steps=tuple(steps),
        final_state=state,
        prior_identities=tuple(identity_by_key.values()),
    )


def setup_commands(
    inputs: TurnEvalCaseInputs, *, ids: TrialScopedIds, base_time: datetime
) -> tuple[SetupStep, ...]:
    return build_setup_plan(inputs, ids=ids, base_time=base_time).steps


def materialize_pure_state(
    inputs: TurnEvalCaseInputs, *, ids: TrialScopedIds, base_time: datetime
) -> InterviewState:
    return build_setup_plan(inputs, ids=ids, base_time=base_time).final_state


def materialize_reference_output(
    inputs: TurnEvalCaseInputs,
    reference: TurnEvalReferenceOutput,
    *,
    trial_id: UUID,
    context=None,
) -> TurnInterpretOutput:
    """Resolve logical prior evidence keys to current context candidate ordinals."""

    output = reference.output
    if not reference.correction_target_bindings:
        return output
    if context is None:
        raise ReferenceGateError("correction bindings require the built context packet")
    evidence_ids = prior_evidence_id_map(inputs, trial_id=trial_id)
    ordinal_by_evidence = {
        item.evidence.evidence_id: ordinal
        for ordinal, item in enumerate(context.correction_candidates, 1)
    }
    observations = []
    for index, proposal in enumerate(output.literal_observations, 1):
        keys = reference.correction_target_bindings.get(str(index), ())
        try:
            ordinals = tuple(ordinal_by_evidence[evidence_ids[key]] for key in keys)
        except KeyError as exc:
            raise ReferenceGateError(
                f"literal observation {index} references an unavailable prior evidence key"
            ) from exc
        observations.append(
            proposal.model_copy(
                update={
                    "correction": proposal.correction.model_copy(
                        update={"target_candidate_ordinals": ordinals}
                    )
                }
            )
        )
    return output.model_copy(update={"literal_observations": tuple(observations)})


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
    receipt: TurnInterpretationRecord
    accepted_count: int
    prior_identities: tuple[PriorEvidenceIdentity, ...]


def _anchor_covers(observation, gold: TurnEvalGoldObservation, target_text: str) -> bool:
    span = _exact_span(target_text, observation.quote, observation.quote_occurrence)
    for anchor in gold.source_anchors:
        if observation.quote == anchor.quote and observation.quote_occurrence == anchor.occurrence:
            return True
        anchor_span = _exact_span(target_text, anchor.quote, anchor.occurrence)
        if anchor_span.start <= span.start and span.end <= anchor_span.end:
            return True
    return False


def _observation_matches_gold(observation, gold, target_text: str) -> bool:
    return (
        observation.subject in gold.allowed_subjects
        and observation.kind in gold.allowed_kinds
        and "literal_employee_span" in gold.allowed_support_kinds
        and _anchor_covers(observation, gold, target_text)
    )


def run_pure_reference_gate(
    inputs: TurnEvalCaseInputs,
    evaluation: TurnEvalCaseGold,
    *,
    trial_id: UUID,
    base_time: datetime,
) -> ReferenceGateResult:
    ids = trial_scoped_ids(trial_id)
    gold = evaluation.gold
    operation = turn_interpret_operation()
    plan = build_setup_plan(inputs, ids=ids, base_time=base_time)
    state_before = plan.final_state
    state_before_hash = canonical_hash(state_before)
    target_turn_id = turn_uuid(trial_id, inputs.case.target_turn_key)
    context = ContextBuilder().build_turn_interpret(
        state=state_before,
        employee_turn_id=target_turn_id,
        operation_id=ids.operation_id,
        operation_definition_hash=operation.definition_hash,
        policy=TURN_INTERPRET_CONTEXT_POLICY_V2,
    )
    output = materialize_reference_output(
        inputs,
        evaluation.reference_output,
        trial_id=trial_id,
        context=context.packet,
    )
    output = TurnInterpretOutput.model_validate(output.model_dump(mode="json"))
    report = verify_turn_interpret_output(
        output=output, context=context.packet, operation_id=ids.operation_id
    )
    if report.dropped_count:
        rejected = [
            (item.proposal_ref, tuple(code.value for code in item.reason_codes))
            for item in report.decisions
            if not item.accepted
        ] + [
            (item.binding_ref, tuple(code.value for code in item.reason_codes))
            for item in report.binding_decisions
            if not item.accepted
        ]
        raise ReferenceGateError(
            f"{inputs.case.case_id}: verifier rejected reference proposals {rejected}"
        )
    if report.dialogue_act not in gold.allowed_dialogue_acts:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: dialogue_act {report.dialogue_act} not allowed"
        )
    if report.episode_signal not in gold.allowed_episode_signals:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: episode_signal {report.episode_signal} not allowed"
        )
    produced_codes = set(report.model_insufficiency_codes) | set(
        report.system_insufficiency_codes
    )
    missing = set(gold.required_insufficiencies) - produced_codes
    extra = produced_codes - set(gold.required_insufficiencies) - set(
        gold.allowed_insufficiencies
    )
    if missing or extra:
        raise ReferenceGateError(
            f"{inputs.case.case_id}: insufficiency mismatch missing={sorted(missing)} extra={sorted(extra)}"
        )
    evidence = accepted_evidence(
        report=report,
        session_id=ids.session_id,
        turn_id=target_turn_id,
        operation_id=ids.operation_id,
    )
    if gold.expected_commit == ExpectedCommit.EVIDENCE_AND_RECEIPT and not evidence:
        raise ReferenceGateError(f"{inputs.case.case_id}: evidence case accepted nothing")
    if gold.expected_commit == ExpectedCommit.RECEIPT_ONLY and evidence:
        raise ReferenceGateError(f"{inputs.case.case_id}: receipt-only case accepted evidence")
    frame = context.packet.question_frame.frame if context.packet.question_frame else None
    receipt = TurnInterpretationRecord(
        interpretation_id=turn_interpretation_id(ids.operation_id),
        session_id=ids.session_id,
        employee_turn_id=target_turn_id,
        operation_id=ids.operation_id,
        question_frame_id=frame.question_frame_id if frame else None,
        question_frame_definition_hash=frame.definition.definition_hash if frame else None,
        context_packet_hash=canonical_hash(context.packet),
        output_hash=canonical_hash(output),
        verification_report_hash=canonical_hash(report),
        accepted_evidence_ids=tuple(item.evidence_id for item in evidence),
        dialogue_act=report.dialogue_act,
        episode_signal=report.episode_signal,
        insufficiency_codes=tuple(
            code for code in TurnInsufficiencyCode if code in produced_codes
        ),
        applied_at=state_before.session.updated_at + timedelta(microseconds=1),
    )
    command = ApplyTurnInterpretationCommand(
        command_id=uuid5(ids.operation_id, "command/turn-interpretation"),
        expected_state_version=state_before.session.state_version,
        occurred_at=receipt.applied_at,
        record=receipt,
        observations=evidence,
    )
    result: ReductionResult = apply_turn_interpretation(state_before, command)
    state_after = result.state
    state_after_hash = canonical_hash(state_after)
    if gold.state_expectation.state_hash_changed != (
        state_after_hash != state_before_hash
    ):
        raise ReferenceGateError(f"{inputs.case.case_id}: state hash expectation failed")
    prior_ids = prior_evidence_id_map(inputs, trial_id=trial_id)
    status_by_id = {item.evidence_id: item.status for item in state_after.evidence}
    for key in gold.state_expectation.prior_evidence_superseded_keys:
        if status_by_id.get(prior_ids[key]) != EvidenceStatus.SUPERSEDED:
            raise ReferenceGateError(f"{inputs.case.case_id}: {key} was not superseded")
    for key in gold.state_expectation.forbidden_superseded_keys:
        if status_by_id.get(prior_ids[key]) != EvidenceStatus.ACTIVE:
            raise ReferenceGateError(f"{inputs.case.case_id}: {key} must remain active")
    required = [
        item for item in gold.observations if item.requirement == GoldRequirement.REQUIRED
    ]
    target_text = inputs.transcript[-1].text
    for gold_item in required:
        matches = [
            observation
            for observation in output.literal_observations
            if _observation_matches_gold(observation, gold_item, target_text)
        ]
        if not matches:
            raise ReferenceGateError(
                f"{inputs.case.case_id}: required gold {gold_item.gold_id!r} is uncovered"
            )
        for observation in matches:
            _check_qualifier_expectations(inputs.case.case_id, gold_item, observation)
    for observation in output.literal_observations:
        if not any(
            _observation_matches_gold(observation, item, target_text)
            for item in gold.observations
        ):
            raise ReferenceGateError(
                f"{inputs.case.case_id}: a reference observation matches no gold"
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
        receipt=receipt,
        accepted_count=report.accepted_count,
        prior_identities=plan.prior_identities,
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


def _check_qualifier_expectations(case_id, gold_item, observation) -> None:
    for field_name, getter in _QUALIFIER_FIELDS.items():
        expectation = getattr(gold_item.qualifiers, field_name)
        if isinstance(expectation, QualifierNotApplicable):
            continue
        actual = getter(observation.qualifiers)
        if field_name == "frequency_value":
            if isinstance(expectation, QualifierExact):
                if actual is None or Decimal(actual) != Decimal(expectation.value):
                    raise ReferenceGateError(
                        f"{case_id}: {gold_item.gold_id} frequency_value mismatch"
                    )
            elif isinstance(expectation, QualifierOneOf):
                if actual is None or all(
                    Decimal(actual) != Decimal(value) for value in expectation.values
                ):
                    raise ReferenceGateError(
                        f"{case_id}: {gold_item.gold_id} frequency_value mismatch"
                    )
            continue
        if isinstance(expectation, QualifierExact) and actual != expectation.value:
            raise ReferenceGateError(
                f"{case_id}: {gold_item.gold_id} {field_name} expected {expectation.value!r}, got {actual!r}"
            )
        if isinstance(expectation, QualifierOneOf) and actual not in expectation.values:
            raise ReferenceGateError(
                f"{case_id}: {gold_item.gold_id} {field_name} {actual!r} outside {expectation.values}"
            )
