"""固定複合命令共用候選准入與一次提交；來源解析留在各 prepare。"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caliburn.adapters.database import retry_database_operation
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionStateError, ExecutionWriter
from caliburn.features.job_description import compound_service, revision_editing
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.compound_edits import CompoundJdEdit, JdCompoundEditResult
from caliburn.features.job_files import service as job_files


@dataclass(frozen=True, slots=True)
class PreparedJdEdit[Command: CompoundJdEdit]:
    candidate: JdCandidateScope
    command: Command


@retry_database_operation
async def execute_prepared_jd_edit(
    sessions: async_sessionmaker[AsyncSession],
    writer: ExecutionWriter,
    prepared: PreparedJdEdit[CompoundJdEdit],
) -> JdCompoundEditResult:
    """候選重播仍須合法 writer；提交不明交 runtime 以原命令恢復。"""
    if (
        writer.scope.kind != ExecutionKind.CONSULTANT_TURN
        or writer.scope.execution_id != prepared.candidate.execution_id
    ):
        raise ExecutionStateError("This prepared edit belongs to a different Turn")
    async with sessions.begin() as session:
        file_id = writer.scope.job_file_id
        await job_files.lock_job_file(session, file_id)
        await executions.lock_active_writer(session, writer)
        await revision_editing.require_open_candidate(session, file_id, prepared.candidate)
        return await compound_service.apply_compound_edit(
            session, file_id, prepared.command, candidate=prepared.candidate
        )
