"""組合 owner 的公開投影，在資料庫內選出固定訪談上界的最新合格 Plan。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caliburn.features.executions import queries as executions
from caliburn.features.interview_plans import queries as plans
from caliburn.features.interview_plans.models import PlanPosition, PlanSnapshot
from caliburn.features.interviews import queries as interviews
from caliburn.features.interviews.models import InterviewReadScope


async def read_adopted_plan(
    session: AsyncSession, scope: InterviewReadScope
) -> PlanSnapshot | None:
    """只回傳一列；最新合格正文為 null／空時仍勝出，不向舊正文回退。"""
    formal = interviews.formal_exchange_positions_projection(scope).subquery("formal_plan_turns")
    completed = executions.completed_consultant_executions_projection(scope.job_file_id).subquery(
        "completed_plan_turns"
    )
    heads = plans.candidate_plan_heads_projection(scope.job_file_id).subquery("plan_heads")
    row = (
        await session.execute(
            select(heads.c.execution_id, heads.c.revision_id, heads.c.body)
            .select_from(formal)
            .join(completed, completed.c.execution_id == formal.c.execution_id)
            .join(heads, heads.c.execution_id == formal.c.execution_id)
            .order_by(formal.c.employee_input_sequence.desc())
            .limit(1)
        )
    ).one_or_none()
    if row is None:
        return None
    execution_id, revision_id, body = row
    return PlanSnapshot(PlanPosition(scope.job_file_id, execution_id, revision_id), body)
