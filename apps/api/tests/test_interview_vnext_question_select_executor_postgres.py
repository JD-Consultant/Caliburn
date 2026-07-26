"""One real-PostgreSQL vertical for the production question.select executor."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import NAMESPACE_URL, uuid5

from app.interview_vnext.application.persistence import WorkflowRun
from app.interview_vnext.application.durable_commands import apply_durable_command
from app.interview_vnext.application.question_select_executor import (
    QUESTION_OUTPUT_SCHEMA_ID,
    execute_question_select,
)
from app.interview_vnext.domain.commands import (
    ApplyTurnInterpretationCommand,
    AppendEmployeeTurnCommand,
    TransitionSessionCommand,
)
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.interpretation import (
    DialogueAct,
    EpisodeSignal,
    TurnInterpretationRecord,
)
from app.interview_vnext.domain.session import (
    ARCHITECTURE_ID,
    SessionStatus,
    session_at,
)
from app.interview_vnext.domain.state import InterviewState
from app.interview_vnext.domain.transcript import TranscriptRole, TranscriptTurn
from app.interview_vnext.domain.turn_identity import turn_interpretation_id
from app.interview_vnext.llm.question_select import (
    QuestionSelectAction,
    QuestionSelectOutput,
)
from app.interview_vnext.llm.result import (
    FinishReason,
    ModelOutcome,
    TokenUsage,
    build_structured_payload,
)
from app.interview_vnext.llm.testing import (
    ScriptedLlmPort,
    ScriptedStep,
    scripted_provider_config,
    scripted_turn_binding,
)
from app.interview_vnext.observability.artifacts import build_inline_artifact
from app.interview_vnext.observability.taxonomy import INTERVIEW_VNEXT_EXECUTION_V2
from app.interview_vnext.persistence.unit_of_work import SqlAlchemyVNextUnitOfWork
from app.job_authoring.commands import CreateJobDocumentCommand
from app.job_authoring.postgres import SqlAlchemyAuthoringUnitOfWork
from app.job_authoring.service import create_job_document


NOW = datetime(2026, 7, 23, 10, 0, tzinfo=UTC)
HASH = "sha256:" + "0" * 64


def _uid(ids, label):
    return uuid5(NAMESPACE_URL, f"question-select:{ids.session_id}:{label}")


async def test_question_select_commits_question_and_episode_atomically(
    postgres_session_factory, vnext_profile
):
    ids = vnext_profile
    employee = TranscriptTurn(
        turn_id=_uid(ids, "employee"),
        session_id=ids.session_id,
        client_turn_id="question-select-employee-1",
        sequence=1,
        role=TranscriptRole.EMPLOYEE,
        text="我主要負責處理日常營運資料。",
        previous_turn_id=None,
        occurred_at=NOW + timedelta(seconds=1),
        received_at=NOW + timedelta(seconds=1),
    )
    state = InterviewState(
        session=session_at(
            session_id=ids.session_id,
            profile_id=ids.profile_id,
            tenant_id=ids.tenant_id,
            workflow_version="1.0.0",
            reference_snapshot_id="local-reference",
            now=NOW,
        )
    )
    taxonomy = INTERVIEW_VNEXT_EXECUTION_V2
    run = WorkflowRun(
        run_id=ids.run_id,
        session_id=ids.session_id,
        architecture_id=ARCHITECTURE_ID,
        workflow_version="1.0.0",
        taxonomy_id=taxonomy.taxonomy_id,
        taxonomy_version=taxonomy.version,
        taxonomy_hash=taxonomy.content_hash,
        started_at=NOW,
    )
    async with SqlAlchemyVNextUnitOfWork(postgres_session_factory) as uow:
        await uow.sessions.create(tenant_id=ids.tenant_id, state=state)
        await uow.capture.create_run(
            tenant_id=ids.tenant_id,
            run=run,
            snapshot_artifact_id=_uid(ids, "initial-state"),
            started_event_id=_uid(ids, "run-started"),
        )
        await uow.commit()

    uow_factory = lambda: SqlAlchemyVNextUnitOfWork(postgres_session_factory)

    async def commit(command, label):
        return await apply_durable_command(
            uow_factory,
            tenant_id=ids.tenant_id,
            session_id=ids.session_id,
            run_id=ids.run_id,
            command=command,
            stage="turn.receive",
            event_id=_uid(ids, f"event/{label}"),
            command_artifact_id=_uid(ids, f"command/{label}"),
            reduction_artifact_id=_uid(ids, f"reduction/{label}"),
            committed_at=command.occurred_at,
            request_idempotency_key=f"question-select-bootstrap:{label}",
        )

    await commit(
        TransitionSessionCommand(
            command_id=_uid(ids, "activate"),
            expected_state_version=0,
            occurred_at=NOW + timedelta(milliseconds=100),
            target_status=SessionStatus.ACTIVE,
        ),
        "activate",
    )
    await commit(
        AppendEmployeeTurnCommand(
            command_id=_uid(ids, "append-employee"),
            expected_state_version=1,
            occurred_at=employee.occurred_at,
            turn=employee,
        ),
        "append-employee",
    )
    interpret_operation_id = _uid(ids, "interpret")
    receipt = TurnInterpretationRecord(
        interpretation_id=turn_interpretation_id(interpret_operation_id),
        session_id=ids.session_id,
        employee_turn_id=employee.turn_id,
        operation_id=interpret_operation_id,
        context_packet_hash=HASH,
        output_hash=HASH,
        verification_report_hash=HASH,
        dialogue_act=DialogueAct.STANDALONE_ANSWER,
        episode_signal=EpisodeSignal.CONTINUE,
        applied_at=NOW + timedelta(seconds=2),
    )
    await commit(
        ApplyTurnInterpretationCommand(
            command_id=_uid(ids, "apply-interpretation"),
            expected_state_version=2,
            occurred_at=receipt.applied_at,
            record=receipt,
            observations=(),
        ),
        "apply-interpretation",
    )
    async with uow_factory() as uow:
        state = await uow.sessions.get(
            tenant_id=ids.tenant_id, session_id=ids.session_id
        )

    authoring_factory = lambda: SqlAlchemyAuthoringUnitOfWork(
        postgres_session_factory
    )
    document = await create_job_document(
        authoring_factory,
        CreateJobDocumentCommand(
            command_id=_uid(ids, "create-document"),
            tenant_id=ids.tenant_id,
            session_id=ids.session_id,
            job_title="營運資料人員",
            occurred_at=NOW + timedelta(seconds=3),
        ),
    )

    output = QuestionSelectOutput(
        acknowledgement="了解。",
        action=QuestionSelectAction.BROADEN_COVERAGE,
        selected_gap_ordinal=None,
        question_text="請先說一項你最常負責的主要工作？",
    )
    operation_id = _uid(ids, "question-select")
    attempt_id = uuid5(operation_id, "attempt/1")
    visible = build_inline_artifact(
        artifact_id=uuid5(attempt_id, "visible-response"),
        kind="model.visible_response",
        media_type="application/json",
        payload=output.model_dump(mode="json"),
        run_id=ids.run_id,
        session_id=ids.session_id,
        turn_id=employee.turn_id,
        operation_id=operation_id,
        attempt_id=attempt_id,
        created_at=NOW + timedelta(seconds=4),
        contains_test_data=True,
    )
    llm = ScriptedLlmPort(
        {
            "question.select": (
                ScriptedStep(
                    expected_attempt=1,
                    outcome=ModelOutcome.SUCCEEDED,
                    finish_reason=FinishReason.COMPLETED,
                    parsed_output=build_structured_payload(
                        schema_id=QUESTION_OUTPUT_SCHEMA_ID,
                        value=output,
                    ),
                    visible_response_artifact=visible.ref,
                    supporting_artifacts=(visible,),
                    usage=TokenUsage(
                        input_tokens=100,
                        output_tokens=40,
                        cache_read_tokens=0,
                        cache_write_tokens=0,
                        reasoning_tokens=0,
                    ),
                ),
            )
        }
    )
    binding = scripted_turn_binding(
        operation_name="question.select",
        binding_id="question-select-scripted",
    )
    outcome = await execute_question_select(
        uow_factory,
        tenant_id=ids.tenant_id,
        run_id=ids.run_id,
        session_id=ids.session_id,
        operation_id=operation_id,
        idempotency_key=f"question-select:{operation_id}",
        job_digest=document.digest,
        llm=llm,
        binding=binding,
        provider_config=scripted_provider_config(),
        started_at=NOW + timedelta(seconds=4),
        now=NOW + timedelta(seconds=4),
        contains_test_data=True,
    )

    assert outcome.status == "committed"
    assert outcome.command_plan is not None
    assert len(outcome.command_plan.items) == 2
    assert len(llm.calls) == 1
    assert llm.calls[0].request.output_schema_id == QUESTION_OUTPUT_SCHEMA_ID
    async with uow_factory() as uow:
        committed = await uow.sessions.get(
            tenant_id=ids.tenant_id, session_id=ids.session_id
        )
    assert committed.session.state_version == state.session.state_version + 2
    assert committed.session.active_episode_id is not None
    assert committed.turns[-1].role == TranscriptRole.CONSULTANT
    assert committed.active_question_frame_id is not None
    assert outcome.command_plan.final_state_hash == canonical_hash(committed)

    replay = await execute_question_select(
        uow_factory,
        tenant_id=ids.tenant_id,
        run_id=ids.run_id,
        session_id=ids.session_id,
        operation_id=operation_id,
        idempotency_key=f"question-select:{operation_id}",
        job_digest=document.digest,
        llm=llm,
        binding=binding,
        provider_config=scripted_provider_config(),
        started_at=NOW + timedelta(seconds=4),
        now=NOW + timedelta(seconds=5),
        contains_test_data=True,
    )
    assert replay.status == "committed"
    assert len(llm.calls) == 1
