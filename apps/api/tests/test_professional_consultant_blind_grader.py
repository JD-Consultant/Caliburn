"""Blind R1 grader: redaction, rubric coverage, failures and separated capture."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.professional_consultant.contracts import (
    BoundaryStatus,
    ClaimCertainty,
    ClaimKind,
    ConsultantAction,
    NextQuestion,
    OwnershipScope,
    Polarity,
    ReconciliationDecision,
    ReconciliationKind,
    SourceClaim,
    SourceSpan,
    Story,
    TaskBoundaryAssessment,
    TaskCandidate,
    TaskDiscoveryOutput,
    TimeScope,
    Typicality,
    UnmappedSignal,
    WorkUnit,
)
from evals.professional_consultant.r1.ablation import ABLATION_ARMS, ArmId
from evals.professional_consultant.r1.blind_projection import (
    REDACTED_GENERATOR_FIELDS,
    BlindTaskDiscoveryArtifact,
    project_blind_artifact,
    project_blind_source,
    submission_id_for,
)
from evals.professional_consultant.r1.grader import (
    GRADER_ID,
    BlindGraderVerdict,
    DimensionVerdict,
    GraderCallError,
    GraderFailureCode,
    GraderModelBinding,
    GraderOperationRequest,
    GraderOperationResponse,
    GraderRunError,
    RubricScore,
    RuleJudgement,
    RuleVerdict,
    blind_grader_output_schema,
    blind_grader_prompt,
    build_blind_grader_request,
    build_grader_operation_request,
    run_blind_grading,
    verify_blind_grader_verdict,
)
from evals.professional_consultant.r1.grader_capture import (
    GraderCaptureIntegrityError,
    GraderTrialStatus,
    grade_published_trial,
    read_grader_capture,
)
from evals.professional_consultant.r1.loader import (
    load_job_analysis_rubric,
    load_runtime_case,
)
from evals.professional_consultant.r1.minimal_harness import (
    MinimalTaskCandidate,
    MinimalTaskDiscoveryOutput,
)

from .test_professional_consultant_capture import _successful_bundle


R1_ROOT = (
    Path(__file__).parents[1] / "evals" / "professional_consultant" / "r1"
)
CASES_ROOT = R1_ROOT / "cases"
RUBRIC_ROOT = R1_ROOT / "rubric"
CASE_DIR = CASES_ROOT / "TI-R1-01-tools-not-task"

RATIONALE_SENTINEL = "ZZ-DECISION-RATIONALE-ZZ"
LIMITATION_SENTINEL = "ZZ-CANDIDATE-LIMITATION-ZZ"
GAP_SENTINEL = "ZZ-STORY-GAP-ZZ"
UNRESOLVED_SENTINEL = "ZZ-WORKUNIT-UNRESOLVED-ZZ"
SIGNIFICANCE_SENTINEL = "ZZ-SIGNAL-SIGNIFICANCE-ZZ"
SIGNAL_MISSING_SENTINEL = "ZZ-SIGNAL-MISSING-ZZ"
DECISION_MISSING_SENTINEL = "ZZ-DECISION-MISSING-ZZ"
TARGET_GAP_SENTINEL = "ZZ-QUESTION-TARGET-GAP-ZZ"

ALL_SENTINELS = (
    RATIONALE_SENTINEL,
    LIMITATION_SENTINEL,
    GAP_SENTINEL,
    UNRESOLVED_SENTINEL,
    SIGNIFICANCE_SENTINEL,
    SIGNAL_MISSING_SENTINEL,
    DECISION_MISSING_SENTINEL,
    TARGET_GAP_SENTINEL,
)


def _rubric():
    return load_job_analysis_rubric(RUBRIC_ROOT)


def _runtime_case():
    return load_runtime_case(CASE_DIR)


def _claim(message_id: str, text: str) -> SourceClaim:
    return SourceClaim(
        claim_id="c-1",
        kind=ClaimKind.WORK_ACTIVITY,
        statement="每週彙整客訴並回覆處理結果",
        ownership=OwnershipScope.EMPLOYEE_RESPONSIBLE,
        time_scope=TimeScope.CURRENT,
        typicality=Typicality.ROUTINE,
        polarity=Polarity.AFFIRMED,
        certainty=ClaimCertainty.EXPLICIT,
        action="彙整",
        object="客訴",
        recipient=None,
        outcome="客戶收到處理結果",
        tool_or_method=None,
        condition=None,
        correction_target_claim_id=None,
        anchors=(
            SourceSpan(
                message_id=message_id,
                start=0,
                end=len(text[:4]),
                quote=text[:4],
            ),
        ),
    )


def _rationale_rich_output(message_id: str, text: str) -> TaskDiscoveryOutput:
    return TaskDiscoveryOutput(
        schema_version="task_discovery_output.v1",
        claims=(_claim(message_id, text),),
        unmapped_signals=(
            UnmappedSignal(
                signal_id="s-1",
                summary="提到一個尚未能安全映射的訊號",
                significance=SIGNIFICANCE_SENTINEL,
                missing_information=SIGNAL_MISSING_SENTINEL,
                anchors=(
                    SourceSpan(
                        message_id=message_id,
                        start=0,
                        end=len(text[:4]),
                        quote=text[:4],
                    ),
                ),
            ),
        ),
        stories=(
            Story(
                story_id="st-1",
                summary="一次完整的客訴處理敘事",
                claim_ids=("c-1",),
                outcome="客戶收到處理結果",
                gaps=(GAP_SENTINEL,),
            ),
        ),
        work_units=(
            WorkUnit(
                work_unit_id="w-1",
                statement="處理客訴並回覆結果",
                claim_ids=("c-1",),
                story_ids=("st-1",),
                outcome="客戶收到處理結果",
                support_claim_ids=("c-1",),
                counter_claim_ids=(),
                unresolved_boundary=(UNRESOLVED_SENTINEL,),
            ),
        ),
        decisions=(
            ReconciliationDecision(
                decision_id="d-1",
                kind=ReconciliationKind.ADD,
                candidate_id="t-1",
                existing_candidate_ids=(),
                work_unit_ids=("w-1",),
                rationale=RATIONALE_SENTINEL,
                missing_information=None,
            ),
            ReconciliationDecision(
                decision_id="d-2",
                kind=ReconciliationKind.CLARIFY,
                candidate_id=None,
                existing_candidate_ids=(),
                work_unit_ids=("w-1",),
                rationale=RATIONALE_SENTINEL,
                missing_information=DECISION_MISSING_SENTINEL,
            ),
        ),
        task_candidates=(
            TaskCandidate(
                candidate_id="t-1",
                statement="處理客訴並回覆處理結果",
                work_unit_ids=("w-1",),
                support_claim_ids=("c-1",),
                counter_claim_ids=(),
                boundary=TaskBoundaryAssessment(
                    meaningful_outcome=BoundaryStatus.MET,
                    role_responsibility=BoundaryStatus.MET,
                    assignability=BoundaryStatus.MET,
                    checkability=BoundaryStatus.MET,
                    stability=BoundaryStatus.MET,
                    boundary_coherence=BoundaryStatus.MET,
                ),
                limitations=(LIMITATION_SENTINEL,),
            ),
        ),
        next_question=NextQuestion(
            action=ConsultantAction.DEEPEN_STORY,
            text="最近一次客訴處理是怎麼進行的？",
            target_gap=TARGET_GAP_SENTINEL,
            claim_ids=("c-1",),
        ),
    )


def _valid_verdict(submission_id: str, rubric) -> BlindGraderVerdict:
    return BlindGraderVerdict(
        schema_version="r1_blind_grader_verdict.v1",
        submission_id=submission_id,
        dimensions=tuple(
            DimensionVerdict(
                code=dimension.code,
                score=RubricScore.UNKNOWN
                if index == 0
                else RubricScore.SCORE_2,
                evidence="依 rubric 判斷的簡短理由",
            )
            for index, dimension in enumerate(rubric.task_boundary_dimensions)
        ),
        critical_rules=tuple(
            RuleVerdict(
                code=rule.code,
                judgement=RuleJudgement.PASS,
                evidence="未見違反",
            )
            for rule in rubric.critical_rules
        ),
        question_rules=tuple(
            RuleVerdict(
                code=rule.code,
                judgement=RuleJudgement.UNKNOWN,
                evidence="資訊不足以判斷",
            )
            for rule in rubric.question_rules
        ),
    )


class _ScriptedGrader:
    """The only grader-side external boundary fake; it never mutates input."""

    def __init__(self, *, outputs: tuple[str, ...] = (), fail: bool = False) -> None:
        self._outputs = outputs
        self._fail = fail
        self.requests: list[GraderOperationRequest] = []

    async def grade(
        self, request: GraderOperationRequest
    ) -> GraderOperationResponse:
        self.requests.append(request)
        if self._fail:
            raise GraderCallError("grader provider unavailable")
        index = len(self.requests) - 1
        return GraderOperationResponse(output_text=self._outputs[index])


# ---- blind projection ----------------------------------------------------


def test_blind_models_declare_no_generator_rationale_fields() -> None:
    from evals.professional_consultant.r1 import blind_projection

    blind_models = [
        value
        for name, value in vars(blind_projection).items()
        if name.startswith("Blind") and hasattr(value, "model_fields")
    ]

    assert blind_models
    for model in blind_models:
        overlap = set(model.model_fields) & set(REDACTED_GENERATOR_FIELDS)
        assert overlap == set(), f"{model.__name__} leaks {sorted(overlap)}"


def test_blind_artifact_drops_every_generator_rationale_value() -> None:
    case = _runtime_case()
    message = case.runtime_input.employee_message
    output = _rationale_rich_output(message.message_id, message.text)

    artifact = project_blind_artifact(output)
    artifact_json = artifact.model_dump_json()

    assert isinstance(artifact, BlindTaskDiscoveryArtifact)
    for sentinel in ALL_SENTINELS:
        assert sentinel not in artifact_json
    assert "boundary" not in artifact_json
    # the substantive product survives redaction
    assert artifact.task_candidates[0].statement == "處理客訴並回覆處理結果"
    assert artifact.task_candidates[0].support_claim_ids == ("c-1",)
    assert artifact.stories[0].claim_ids == ("c-1",)
    assert artifact.work_units[0].story_ids == ("st-1",)
    assert artifact.decisions[1].kind is ReconciliationKind.CLARIFY
    assert artifact.next_question.text == "最近一次客訴處理是怎麼進行的？"
    assert artifact.claims[0].ownership is OwnershipScope.EMPLOYEE_RESPONSIBLE


def test_minimal_output_projects_to_the_same_blind_shape_without_padding() -> None:
    minimal = MinimalTaskDiscoveryOutput(
        schema_version="minimal_task_discovery_output.v1",
        task_candidates=(
            MinimalTaskCandidate(candidate_id="t-1", statement="處理客訴"),
        ),
        next_question=NextQuestion(
            action=ConsultantAction.BROADEN,
            text="你還固定負責哪些工作？",
            target_gap=TARGET_GAP_SENTINEL,
            claim_ids=(),
        ),
    )

    artifact = project_blind_artifact(minimal)

    assert isinstance(artifact, BlindTaskDiscoveryArtifact)
    assert artifact.claims == ()
    assert artifact.stories == ()
    assert artifact.work_units == ()
    assert artifact.decisions == ()
    assert artifact.task_candidates[0].candidate_id == "t-1"
    assert artifact.task_candidates[0].work_unit_ids == ()
    assert artifact.task_candidates[0].support_claim_ids == ()
    assert TARGET_GAP_SENTINEL not in artifact.model_dump_json()


# ---- blind grader request ------------------------------------------------


def test_grader_request_hides_arm_identity_and_generator_rationale() -> None:
    case = _runtime_case()
    message = case.runtime_input.employee_message
    output = _rationale_rich_output(message.message_id, message.text)
    trial_id = f"fast-{case.metadata.case_id}-{ArmId.A3.value}"

    request = build_blind_grader_request(
        trial_id=trial_id,
        source=case.runtime_input,
        result=output,
        rubric=_rubric(),
    )
    operation_request = build_grader_operation_request(request)
    payload = operation_request.input_text

    assert request.submission_id == submission_id_for(trial_id)
    assert trial_id not in payload
    for arm in ABLATION_ARMS:
        assert f'"{arm.arm_id.value}"' not in payload
    for token in (
        "arm_id",
        "model_tier",
        "schema_profile",
        "harness_profile",
        "runner_kind",
        "requested_model",
        "resolved_model",
    ):
        assert token not in payload
    for sentinel in ALL_SENTINELS:
        assert sentinel not in payload
    # human adjudication never reaches the grader
    assert "expectations" not in payload
    assert "adjudication" not in payload
    assert "acceptable_task_examples" not in payload


def test_grader_request_carries_the_source_packet_and_single_rubric() -> None:
    case = _runtime_case()
    rubric = _rubric()

    request = build_blind_grader_request(
        trial_id=f"fast-{case.metadata.case_id}-A1",
        source=case.runtime_input,
        result=_rationale_rich_output(
            case.runtime_input.employee_message.message_id,
            case.runtime_input.employee_message.text,
        ),
        rubric=rubric,
    )

    assert request.rubric == rubric
    assert request.source == project_blind_source(case.runtime_input)
    assert (
        request.source.employee_message == case.runtime_input.employee_message
    )
    assert request.source.recent_questions == case.runtime_input.recent_questions


def test_grader_prompt_and_schema_are_separate_from_generator_assets() -> None:
    prompt = blind_grader_prompt()
    schema = blind_grader_output_schema()

    assert prompt.prompt_id == "r1-blind-grader.v1"
    assert schema.schema_id == "r1-blind-grader-verdict.v1"
    assert "task.discover" not in prompt.content
    assert "expectations" not in prompt.content
    parsed = json.loads(schema.schema_text)
    assert parsed["additionalProperties"] is False
    assert sorted(parsed["required"]) == [
        "critical_rules",
        "dimensions",
        "question_rules",
        "schema_version",
        "submission_id",
    ]
    score_enum = parsed["properties"]["dimensions"]["items"]["properties"][
        "score"
    ]["enum"]
    assert "unknown" in score_enum


# ---- verdict verification -------------------------------------------------


def test_valid_verdict_may_answer_unknown_for_every_dimension() -> None:
    case = _runtime_case()
    rubric = _rubric()
    request = build_blind_grader_request(
        trial_id=f"fast-{case.metadata.case_id}-A1",
        source=case.runtime_input,
        result=_rationale_rich_output(
            case.runtime_input.employee_message.message_id,
            case.runtime_input.employee_message.text,
        ),
        rubric=rubric,
    )
    verdict = _valid_verdict(request.submission_id, rubric).model_copy(
        update={
            "dimensions": tuple(
                DimensionVerdict(
                    code=dimension.code,
                    score=RubricScore.UNKNOWN,
                    evidence="資訊不足",
                )
                for dimension in rubric.task_boundary_dimensions
            )
        }
    )

    report = verify_blind_grader_verdict(request, verdict)

    assert report.passed is True


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("submission", "submission_mismatch"),
        ("drop_dimension", "dimension_coverage_mismatch"),
        ("unknown_dimension", "dimension_coverage_mismatch"),
        ("duplicate_dimension", "duplicate_code"),
        ("drop_critical_rule", "critical_rule_coverage_mismatch"),
        ("drop_question_rule", "question_rule_coverage_mismatch"),
    ],
)
def test_verdict_verification_fails_closed_on_coverage_drift(
    mutation: str, expected: str
) -> None:
    case = _runtime_case()
    rubric = _rubric()
    request = build_blind_grader_request(
        trial_id=f"fast-{case.metadata.case_id}-A1",
        source=case.runtime_input,
        result=_rationale_rich_output(
            case.runtime_input.employee_message.message_id,
            case.runtime_input.employee_message.text,
        ),
        rubric=rubric,
    )
    verdict = _valid_verdict(request.submission_id, rubric)
    if mutation == "submission":
        verdict = verdict.model_copy(update={"submission_id": "sub-other"})
    elif mutation == "drop_dimension":
        verdict = verdict.model_copy(
            update={"dimensions": verdict.dimensions[1:]}
        )
    elif mutation == "unknown_dimension":
        verdict = verdict.model_copy(
            update={
                "dimensions": (
                    *verdict.dimensions,
                    DimensionVerdict(
                        code="invented_dimension",
                        score=RubricScore.SCORE_2,
                        evidence="不存在的維度",
                    ),
                )
            }
        )
    elif mutation == "duplicate_dimension":
        verdict = verdict.model_copy(
            update={"dimensions": (*verdict.dimensions, verdict.dimensions[0])}
        )
    elif mutation == "drop_critical_rule":
        verdict = verdict.model_copy(
            update={"critical_rules": verdict.critical_rules[1:]}
        )
    else:
        verdict = verdict.model_copy(
            update={"question_rules": verdict.question_rules[1:]}
        )

    report = verify_blind_grader_verdict(request, verdict)

    assert report.passed is False
    assert expected in {issue.code.value for issue in report.issues}


# ---- grader runner --------------------------------------------------------


@pytest.mark.asyncio
async def test_run_blind_grading_returns_a_verified_verdict() -> None:
    case = _runtime_case()
    rubric = _rubric()
    request = build_blind_grader_request(
        trial_id=f"fast-{case.metadata.case_id}-A1",
        source=case.runtime_input,
        result=_rationale_rich_output(
            case.runtime_input.employee_message.message_id,
            case.runtime_input.employee_message.text,
        ),
        rubric=rubric,
    )
    expected = _valid_verdict(request.submission_id, rubric)
    provider = _ScriptedGrader(outputs=(expected.model_dump_json(),))

    verdict = await run_blind_grading(request, provider=provider)

    assert verdict == expected
    assert len(provider.requests) == 1
    assert provider.requests[0].grader_id == GRADER_ID


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("script", "expected"),
    [
        ("provider", GraderFailureCode.PROVIDER_FAILED),
        ("not json", GraderFailureCode.OUTPUT_JSON_INVALID),
        ('{"schema_version":"nope"}', GraderFailureCode.OUTPUT_SCHEMA_INVALID),
        ("coverage", GraderFailureCode.VERIFICATION_FAILED),
    ],
)
async def test_grader_failures_are_typed_and_terminal(
    script: str, expected: GraderFailureCode
) -> None:
    case = _runtime_case()
    rubric = _rubric()
    request = build_blind_grader_request(
        trial_id=f"fast-{case.metadata.case_id}-A1",
        source=case.runtime_input,
        result=_rationale_rich_output(
            case.runtime_input.employee_message.message_id,
            case.runtime_input.employee_message.text,
        ),
        rubric=rubric,
    )
    if script == "provider":
        provider = _ScriptedGrader(fail=True)
    elif script == "coverage":
        broken = _valid_verdict(request.submission_id, rubric).model_copy(
            update={"critical_rules": ()}
        )
        provider = _ScriptedGrader(outputs=(broken.model_dump_json(),))
    else:
        provider = _ScriptedGrader(outputs=(script,))

    with pytest.raises(GraderRunError) as excinfo:
        await run_blind_grading(request, provider=provider)

    assert excinfo.value.failure.code is expected
    if expected is GraderFailureCode.VERIFICATION_FAILED:
        assert excinfo.value.failure.verification_report is not None
    else:
        assert excinfo.value.failure.verification_report is None


# ---- separated grader capture --------------------------------------------


@pytest.mark.asyncio
async def test_grading_a_published_trial_writes_a_separate_capture(
    tmp_path: Path,
) -> None:
    from evals.professional_consultant.r1.capture import (
        read_trial_capture,
        write_trial_capture,
    )

    capture_root = tmp_path / "trials"
    grading_root = tmp_path / "grading"
    bundle = _successful_bundle()
    write_trial_capture(capture_root, bundle)
    trial_id = bundle.source_state.trial_id
    before = (capture_root / trial_id / "trial-evidence.json").read_bytes()
    rubric = _rubric()
    submission_id = submission_id_for(trial_id)
    provider = _ScriptedGrader(
        outputs=(_valid_verdict(submission_id, rubric).model_dump_json(),)
    )

    manifest = await grade_published_trial(
        capture_root=capture_root,
        grading_root=grading_root,
        trial_id=trial_id,
        rubric=rubric,
        provider=provider,
        binding=GraderModelBinding(
            schema_version="r1_grader_model_binding.v1",
            requested_model="requested/grader-alias",
            counted_in_generator_budget=False,
        ),
    )
    loaded = read_grader_capture(grading_root, manifest.grading_id)

    assert manifest.trial_id == trial_id
    assert manifest.submission_id == submission_id
    assert manifest.counted_in_generator_budget is False
    assert manifest.requested_model == "requested/grader-alias"
    assert manifest.grader_prompt_id == blind_grader_prompt().prompt_id
    assert loaded.grader_evidence.status is GraderTrialStatus.SUCCEEDED
    assert loaded.grader_evidence.verdict is not None
    assert loaded.grader_input.submission_id == submission_id
    # the grader never mutates or republishes generator evidence
    assert (capture_root / trial_id / "trial-evidence.json").read_bytes() == before
    assert read_trial_capture(capture_root, trial_id).trial_evidence == (
        bundle.trial_evidence
    )
    # generator and grader capture roots stay separate
    assert not (grading_root / trial_id).exists()
    assert sorted(
        path.name for path in (grading_root / manifest.grading_id).iterdir()
    ) == ["grader-evidence.json", "grader-input.json", "manifest.json"]
    # the artifact the grader saw carries no arm identity
    input_text = (
        grading_root / manifest.grading_id / "grader-input.json"
    ).read_text(encoding="utf-8")
    assert trial_id not in input_text
    assert "requested/grader-alias" not in input_text
    with pytest.raises(ValidationError, match="frozen"):
        manifest.trial_id = "changed"  # type: ignore[misc]


@pytest.mark.asyncio
async def test_grader_capture_reader_fails_closed_on_tampered_bytes(
    tmp_path: Path,
) -> None:
    from evals.professional_consultant.r1.capture import write_trial_capture

    capture_root = tmp_path / "trials"
    grading_root = tmp_path / "grading"
    bundle = _successful_bundle()
    write_trial_capture(capture_root, bundle)
    trial_id = bundle.source_state.trial_id
    rubric = _rubric()
    provider = _ScriptedGrader(
        outputs=(
            _valid_verdict(submission_id_for(trial_id), rubric).model_dump_json(),
        )
    )
    manifest = await grade_published_trial(
        capture_root=capture_root,
        grading_root=grading_root,
        trial_id=trial_id,
        rubric=rubric,
        provider=provider,
        binding=GraderModelBinding(
            schema_version="r1_grader_model_binding.v1",
            requested_model="requested/grader-alias",
            counted_in_generator_budget=False,
        ),
    )
    path = grading_root / manifest.grading_id / "grader-evidence.json"
    path.write_bytes(path.read_bytes() + b" ")

    with pytest.raises(GraderCaptureIntegrityError, match="digest"):
        read_grader_capture(grading_root, manifest.grading_id)
