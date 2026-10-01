"""Behavior tests for the pure R1 deterministic verifier seam."""

from __future__ import annotations

from app.professional_consultant.contracts import (
    ClaimCertainty,
    ClaimKind,
    ConsultantAction,
    BoundaryStatus,
    EmployeeMessage,
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
    TaskDiscoveryInput,
    TaskDiscoveryOutput,
    TimeScope,
    Typicality,
    TranscriptRole,
    TranscriptTurn,
    WorkUnit,
)
from app.professional_consultant.verifier import (
    VerificationIssueCode,
    verify_task_discovery,
)


def _source() -> TaskDiscoveryInput:
    return TaskDiscoveryInput(
        schema_version="task_discovery_input.v1",
        employee_message=EmployeeMessage(
            message_id="message-1", text="我每週整理門市資料。"
        ),
        question_context=None,
        recent_transcript=(),
        prior_claims=(),
        prior_stories=(),
        prior_work_units=(),
        existing_task_candidates=(),
        recent_questions=("你平常固定負責哪些工作？",),
        omitted_relevant_context=False,
    )


def _next(text: str = "整理完成後，這些資料會交給誰使用？") -> NextQuestion:
    return NextQuestion(
        action=ConsultantAction.DEEPEN_STORY,
        text=text,
        target_gap="資料整理的接收者",
        claim_ids=(),
    )


def _output(**changes: object) -> TaskDiscoveryOutput:
    values: dict[str, object] = {
        "schema_version": "task_discovery_output.v1",
        "claims": (),
        "unmapped_signals": (),
        "stories": (),
        "work_units": (),
        "decisions": (),
        "task_candidates": (),
        "next_question": _next(),
    }
    values.update(changes)
    return TaskDiscoveryOutput(**values)


def _claim(
    *,
    claim_id: str,
    span: SourceSpan,
    kind: ClaimKind = ClaimKind.WORK_ACTIVITY,
    ownership: OwnershipScope = OwnershipScope.EMPLOYEE_RESPONSIBLE,
    time_scope: TimeScope = TimeScope.CURRENT,
    typicality: Typicality = Typicality.PERIODIC,
    polarity: Polarity = Polarity.AFFIRMED,
    correction_target_claim_id: str | None = None,
) -> SourceClaim:
    return SourceClaim(
        claim_id=claim_id,
        kind=kind,
        statement="每週整理門市資料",
        ownership=ownership,
        time_scope=time_scope,
        typicality=typicality,
        polarity=polarity,
        certainty=ClaimCertainty.EXPLICIT,
        action="整理",
        object="門市資料",
        recipient=None,
        outcome=None,
        tool_or_method=None,
        condition=None,
        correction_target_claim_id=correction_target_claim_id,
        anchors=(span,),
    )


def _work_and_task(
    claim_id: str, *, duplicate_support: bool = False
) -> tuple[WorkUnit, TaskCandidate]:
    support = (claim_id, claim_id) if duplicate_support else (claim_id,)
    work = WorkUnit(
        work_unit_id="work-1",
        statement="整理門市資料",
        claim_ids=(claim_id,),
        story_ids=(),
        outcome="提供可用門市資料",
        support_claim_ids=support,
        counter_claim_ids=(),
        unresolved_boundary=(),
    )
    task = TaskCandidate(
        candidate_id="task-1",
        statement="整理門市資料以供營運使用",
        work_unit_ids=(work.work_unit_id,),
        support_claim_ids=support,
        counter_claim_ids=(),
        boundary=TaskBoundaryAssessment(
            meaningful_outcome=BoundaryStatus.MET,
            role_responsibility=BoundaryStatus.MET,
            assignability=BoundaryStatus.MET,
            checkability=BoundaryStatus.MET,
            stability=BoundaryStatus.MET,
            boundary_coherence=BoundaryStatus.MET,
        ),
        limitations=(),
    )
    return work, task


def test_empty_task_result_is_a_valid_first_class_outcome() -> None:
    report = verify_task_discovery(_source(), _output())

    assert report.passed is True
    assert report.issues == ()


def test_source_span_and_cross_reference_failures_are_reported_together() -> None:
    bad_span = SourceSpan(
        message_id="message-1", start=0, end=2, quote="不符"
    )
    output = _output(
        claims=(_claim(claim_id="claim-1", span=bad_span),),
        stories=(
            Story(
                story_id="story-1",
                summary="資料整理故事",
                claim_ids=("claim-missing",),
                outcome=None,
                gaps=(),
            ),
        ),
    )

    report = verify_task_discovery(_source(), output)

    assert report.passed is False
    assert {issue.code for issue in report.issues} == {
        VerificationIssueCode.SPAN_QUOTE_MISMATCH,
        VerificationIssueCode.REFERENCE_MISSING,
    }


def test_disqualified_only_support_and_duplicate_relations_are_rejected() -> None:
    source = _source().model_copy(
        update={
            "employee_message": EmployeeMessage(
                message_id="message-1", text="上月臨時幫同事處理一次請款。"
            )
        }
    )
    claim = _claim(
        claim_id="claim-one-off",
        span=SourceSpan(
            message_id="message-1",
            start=0,
            end=len(source.employee_message.text),
            quote=source.employee_message.text,
        ),
        typicality=Typicality.ONE_OFF,
    )
    work, task = _work_and_task(claim.claim_id, duplicate_support=True)

    report = verify_task_discovery(
        source,
        _output(claims=(claim,), work_units=(work,), task_candidates=(task,)),
    )

    assert {issue.code for issue in report.issues} == {
        VerificationIssueCode.DISQUALIFIED_TASK_SUPPORT,
        VerificationIssueCode.DUPLICATE_RELATION,
    }


def test_correction_supersedes_old_support_and_unknown_targets_fail() -> None:
    old_text = "我負責把版本部署到正式環境。"
    current_text = "剛才說錯，正式部署是維運負責。"
    old = _claim(
        claim_id="claim-old",
        span=SourceSpan(
            message_id="message-old", start=0, end=len(old_text), quote=old_text
        ),
    )
    source = _source().model_copy(
        update={
            "employee_message": EmployeeMessage(
                message_id="message-1", text=current_text
            ),
            "recent_transcript": (
                TranscriptTurn(
                    turn_id="message-old", role=TranscriptRole.EMPLOYEE, text=old_text
                ),
            ),
            "prior_claims": (old,),
        }
    )
    correction = _claim(
        claim_id="claim-correction",
        span=SourceSpan(
            message_id="message-1",
            start=0,
            end=len(current_text),
            quote=current_text,
        ),
        kind=ClaimKind.CORRECTION,
        ownership=OwnershipScope.OTHER_RESPONSIBLE,
        correction_target_claim_id=old.claim_id,
    )
    missing_target = correction.model_copy(
        update={
            "claim_id": "claim-missing-target",
            "correction_target_claim_id": "claim-unknown",
        }
    )
    work, task = _work_and_task(old.claim_id)

    report = verify_task_discovery(
        source,
        _output(
            claims=(correction, missing_target),
            work_units=(work,),
            task_candidates=(task,),
        ),
    )

    assert {issue.code for issue in report.issues} == {
        VerificationIssueCode.CORRECTION_TARGET_MISSING,
        VerificationIssueCode.SUPERSEDED_CLAIM_SUPPORT,
    }


def test_exact_normalized_recent_question_is_not_repeated() -> None:
    output = _output(
        next_question=_next("  你平常固定負責哪些工作 ?  ")
    )

    report = verify_task_discovery(_source(), output)

    assert [issue.code for issue in report.issues] == [
        VerificationIssueCode.REPEATED_QUESTION
    ]


def test_duplicate_entity_ids_and_every_missing_relation_are_reported() -> None:
    text = _source().employee_message.text
    claim = _claim(
        claim_id="claim-duplicate",
        span=SourceSpan(message_id="message-1", start=0, end=len(text), quote=text),
    )
    work = WorkUnit(
        work_unit_id="work-1",
        statement="整理門市資料",
        claim_ids=("claim-missing",),
        story_ids=("story-missing",),
        outcome=None,
        support_claim_ids=("claim-missing",),
        counter_claim_ids=("claim-missing-counter",),
        unresolved_boundary=(),
    )
    _, task = _work_and_task("claim-missing")
    task = task.model_copy(
        update={
            "work_unit_ids": ("work-missing",),
            "counter_claim_ids": ("claim-missing-counter",),
        }
    )
    decision = ReconciliationDecision(
        decision_id="decision-1",
        kind=ReconciliationKind.NO_OP,
        candidate_id=None,
        existing_candidate_ids=("task-missing",),
        work_unit_ids=("work-missing",),
        rationale="沒有足夠資訊改動",
        missing_information=None,
    )

    report = verify_task_discovery(
        _source(),
        _output(
            claims=(claim, claim),
            work_units=(work,),
            decisions=(decision,),
            task_candidates=(task,),
            next_question=_next().model_copy(
                update={"claim_ids": ("claim-missing",)}
            ),
        ),
    )

    assert {issue.code for issue in report.issues} == {
        VerificationIssueCode.DUPLICATE_ID,
        VerificationIssueCode.REFERENCE_MISSING,
    }


def test_bounded_context_does_not_reverify_omitted_historical_anchors() -> None:
    historical = _claim(
        claim_id="claim-historical",
        span=SourceSpan(
            message_id="message-outside-context",
            start=0,
            end=4,
            quote="歷史內容",
        ),
    )
    source = _source().model_copy(
        update={"prior_claims": (historical,), "omitted_relevant_context": True}
    )

    report = verify_task_discovery(source, _output())

    assert report.passed is True
