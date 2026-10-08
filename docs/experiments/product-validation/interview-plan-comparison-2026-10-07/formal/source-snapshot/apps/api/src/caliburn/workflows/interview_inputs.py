"""Accept original input and consultant admission together; do not start a model here."""

from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.features.executions import service as execution_service
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.interviews import service as interview_service
from caliburn.features.interviews.models import InputAcceptance, SubmitInterviewInput
from caliburn.features.job_files import service as job_file_service


class InterviewInputWorkflow:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def read_accepted(self, command: SubmitInterviewInput) -> InputAcceptance | None:
        """Reconcile immutable original text/result without requiring a live model.

        Absence grants no admission: accept() rechecks under the existing file lock.
        """
        async with self.sessions() as session:
            original = await interview_service.find_accepted_input(session, command)
        return InputAcceptance(original, is_new=False) if original is not None else None

    async def accept(self, command: SubmitInterviewInput) -> InputAcceptance:
        async with self.sessions.begin() as session:
            await job_file_service.lock_job_file(session, command.job_file_id)
            original = await interview_service.find_accepted_input(session, command)
            if original is not None:
                return InputAcceptance(original, is_new=False)
            scope = ExecutionScope(command.job_file_id, uuid4(), ExecutionKind.CONSULTANT_TURN)
            await execution_service.admit_execution(session, scope)
            accepted = await interview_service.accept_input(
                session, command, execution_id=scope.execution_id
            )
        return InputAcceptance(accepted, is_new=True)
