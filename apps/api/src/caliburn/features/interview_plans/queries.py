"""Plan owner 的具名讀取投影；不複製採用資格或保存另一份 head。"""

from uuid import UUID

from sqlalchemy import Select

from caliburn.features.interview_plans import persistence


def candidate_plan_heads_projection(job_file_id: UUID) -> Select[UUID, UUID, str | None]:
    """回傳候選目前的 execution、revision、nullable body，不讀取所有 operation。"""
    return persistence.candidate_plan_heads_projection(job_file_id)
