"""Public polling never exposes execution internals or grants pending input a formal identity."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionNotFoundError,
    ExecutionScope,
    ExecutionStatus,
)
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import SubmitInterviewInput
from caliburn.features.job_description.models import ProfileField, ReviseJdProfile, SetProfileField
from caliburn.workflows.consultant_status import (
    ConsultantStatusWorkflow,
    ConsultantTurnUnavailableError,
)
from caliburn.workflows.jd_candidates import JdCandidateWorkflow

pytestmark = pytest.mark.postgres


def test_status_keeps_original_input_nonformal_and_scopes_execution(client: TestClient) -> None:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "狀態合成", "employee_name": "合成人"},
    )
    file_id = UUID(created.json()["job_file_id"])

    async def scenario() -> None:
        database = client.app.state.database
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), " 原始輸入\n保持原樣。 ")
        )
        execution_id = accepted.accepted.execution_id
        workflow = ConsultantStatusWorkflow(database.sessions)
        status = await workflow.read(file_id, execution_id)
        assert status.status == ExecutionStatus.ACTIVE
        assert status.input_text == " 原始輸入\n保持原樣。 "
        with pytest.raises(ExecutionNotFoundError):
            await workflow.read(uuid4(), execution_id)
        scope = ExecutionScope(file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        async with database.sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.pause_execution(session, writer)
        assert (await workflow.read(file_id, execution_id)).status == ExecutionStatus.PAUSED
        async with database.sessions.begin() as session:
            await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)
        cancelled = await workflow.read(file_id, execution_id)
        assert cancelled.status == ExecutionStatus.CANCELLED
        assert cancelled.input_text == status.input_text
        async with database.sessions.begin() as session:
            history = await interviews.read_interview_history(session, file_id)
            assert [message.interview_sequence for message in history] == [1]
            foreign_scope = ExecutionScope(file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            await executions.admit_execution(session, foreign_scope)
        with pytest.raises(ExecutionNotFoundError):
            await workflow.read(file_id, foreign_scope.execution_id)

    client.portal.call(scenario)


def test_http_status_projects_only_public_fields_and_never_caches_input(client: TestClient) -> None:
    from caliburn.transport.http.consultant_turns import get_consultant_status_workflow, router

    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "HTTP合成", "employee_name": "合成人"},
    )
    file_id = UUID(created.json()["job_file_id"])

    async def accept_and_fail() -> UUID:
        database = client.app.state.database
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "保持可回看的失敗輸入")
        )
        execution_id = accepted.accepted.execution_id
        scope = ExecutionScope(file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        async with database.sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.finish_execution(session, writer, ExecutionStatus.FAILED)
        return execution_id

    execution_id = client.portal.call(accept_and_fail)
    workflow = ConsultantStatusWorkflow(client.app.state.database.sessions)
    client.app.dependency_overrides[get_consultant_status_workflow] = lambda: workflow
    client.app.include_router(router)
    response = client.get(f"/api/job-files/{file_id}/consultant-turns/{execution_id}")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "job_file_id": str(file_id),
        "execution_id": str(execution_id),
        "status": "failed",
        "pause_requested": False,
        "input_text": "保持可回看的失敗輸入",
        "allowed_controls": [],
        "commentary": None,
        "plan_preview": None,
        "candidate": None,
    }
    missing = client.get(f"/api/job-files/{uuid4()}/consultant-turns/{execution_id}")
    assert missing.status_code == 404
    assert missing.json() == {"detail": {"code": "consultant_turn_not_found"}}


def test_completed_status_requires_actual_formal_exchange(client: TestClient) -> None:
    created = client.post(
        "/api/job-files",
        json={"command_id": str(uuid4()), "display_name": "完成合成", "employee_name": "合成人"},
    )
    file_id = UUID(created.json()["job_file_id"])

    async def scenario() -> None:
        database = client.app.state.database
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "待完成原輸入")
        )
        execution_id = accepted.accepted.execution_id
        scope = ExecutionScope(file_id, execution_id, ExecutionKind.CONSULTANT_TURN)
        workflow = ConsultantStatusWorkflow(database.sessions)
        async with database.sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            await executions.finish_execution(session, writer, ExecutionStatus.COMPLETED)
        with pytest.raises(ConsultantTurnUnavailableError):
            await workflow.read(file_id, execution_id)
        # Populate the real public result to exercise read-side reconciliation only;
        # the production atomic completion boundary is covered by its own tests.
        async with database.sessions.begin() as session:
            await interview_service.formalize_exchange(
                session, job_file_id=file_id, execution_id=execution_id, reply_text="已保存答覆"
            )
        assert (await workflow.read(file_id, execution_id)).status == ExecutionStatus.COMPLETED

    client.portal.call(scenario)


def test_command_lookup_recovers_only_the_scoped_original_without_formalizing(
    client: TestClient,
) -> None:
    from caliburn.transport.http.consultant_turns import get_consultant_status_workflow, router

    file_ids = [
        UUID(
            client.post(
                "/api/job-files",
                json={"command_id": str(uuid4()), "display_name": name, "employee_name": "合成人"},
            ).json()["job_file_id"]
        )
        for name in ("原命令檔案", "另一份檔案")
    ]
    command_id = uuid4()

    async def accept() -> UUID:
        result = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_ids[0], command_id, " 遺失回應後查回\n原文。 ")
        )
        return result.accepted.execution_id

    execution_id = client.portal.call(accept)
    workflow = ConsultantStatusWorkflow(client.app.state.database.sessions)
    client.app.dependency_overrides[get_consultant_status_workflow] = lambda: workflow
    client.app.include_router(router)
    path = f"/api/job-files/{file_ids[0]}/consultant-turns/by-command/{command_id}"
    recovered = client.get(path)
    assert recovered.status_code == 200
    assert recovered.headers["cache-control"] == "no-store"
    assert recovered.json() == {
        "job_file_id": str(file_ids[0]),
        "execution_id": str(execution_id),
        "status": "active",
        "pause_requested": False,
        "input_text": " 遺失回應後查回\n原文。 ",
        "allowed_controls": [],
        "commentary": None,
        "plan_preview": None,
        "candidate": None,
    }
    for file_id, missing_command in ((file_ids[1], command_id), (file_ids[0], uuid4())):
        missing = client.get(
            f"/api/job-files/{file_id}/consultant-turns/by-command/{missing_command}"
        )
        assert missing.status_code == 404
        assert missing.json() == {"detail": {"code": "consultant_turn_not_found"}}

    async def read_original() -> None:
        async with client.app.state.database.sessions.begin() as session:
            original = await interviews.read_accepted_input(
                session, job_file_id=file_ids[0], command_id=command_id
            )
            assert original is not None
            assert original.command_id == command_id
            assert original.execution_id == execution_id
            assert (
                await interviews.read_accepted_input(
                    session, job_file_id=file_ids[1], command_id=command_id
                )
                is None
            )
            assert [
                item.interview_sequence
                for item in await interviews.read_interview_history(session, file_ids[0])
            ] == [1]

    client.portal.call(read_original)


def test_status_preview_reads_fixed_candidate_without_changing_formal_jd(
    client: TestClient,
) -> None:
    file_id = UUID(
        client.post(
            "/api/job-files",
            json={
                "command_id": str(uuid4()),
                "display_name": "候選預覽",
                "employee_name": "合成人",
            },
        ).json()["job_file_id"]
    )

    async def scenario() -> None:
        sessions = client.app.state.database.sessions
        accepted = await client.app.state.interview_input_workflow.accept(
            SubmitInterviewInput(file_id, uuid4(), "尚未正式完成的原話")
        )
        scope = ExecutionScope(
            file_id, accepted.accepted.execution_id, ExecutionKind.CONSULTANT_TURN
        )
        async with sessions.begin() as session:
            writer = await executions.claim_writer(session, scope, writer_id=uuid4())
        candidates = JdCandidateWorkflow(sessions)
        position = await candidates.start(writer)
        changed = await candidates.edit(
            writer,
            position.scope,
            ReviseJdProfile(
                uuid4(),
                position.revision_id,
                (SetProfileField(ProfileField.JOB_TITLE, "候選職稱"),),
            ),
        )
        status = await ConsultantStatusWorkflow(sessions).read(file_id, scope.execution_id)
        assert status.candidate is not None
        assert status.candidate.profile.job_title == "候選職稱"
        assert status.candidate.work.revision_id == changed.revision_id
        assert status.candidate.position.revision_id == changed.revision_id
        from caliburn.transport.http.consultant_turns import turn_view

        wire = turn_view(status).model_dump(mode="json")
        assert wire["candidate"]["work"]["revision_id"] == str(changed.revision_id)
        assert wire["candidate"]["profile"]["job_title"] == "候選職稱"
        assert set(wire["candidate"]) == {"profile", "work"}
        formal = await client.app.state.jd_editing_workflow.read_profile(file_id)
        assert formal.profile.job_title is None
        async with sessions.begin() as session:
            await executions.finish_execution(session, writer, ExecutionStatus.CANCELLED)
        cancelled = await ConsultantStatusWorkflow(sessions).read(file_id, scope.execution_id)
        assert cancelled.candidate is None

    client.portal.call(scenario)
