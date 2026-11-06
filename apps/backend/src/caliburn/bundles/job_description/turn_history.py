"""將已由 Host 確認正常完成的輪次，投影成 JD 固定版本。"""

from collections.abc import Mapping
from uuid import UUID

from caliburn.modules.job_description.application.turn_history import (
    JobDescriptionTurnDataError,
    JobDescriptionTurnNotFoundError,
    JobDescriptionTurnVersions,
)


def project_completed_turn(
    *, workspace_id: UUID, turn_id: UUID, values: Mapping[str, object]
) -> JobDescriptionTurnVersions:
    """Host 先核正常完成與 Workspace；此處只解讀 JD 自有保存字段。"""
    if values.get("jd_turn_id") != turn_id:
        raise JobDescriptionTurnNotFoundError("指定完成輪沒有 JD 參與紀錄")
    jd_id = values.get("jd_id")
    before_version = values.get("jd_turn_start_version")
    after_version = values.get("jd_completed_version")
    if (
        not isinstance(jd_id, UUID)
        or not isinstance(before_version, int)
        or not isinstance(after_version, int)
    ):
        raise JobDescriptionTurnDataError("完成輪缺少有效的 JD 固定版本")
    return JobDescriptionTurnVersions(
        workspace_id=workspace_id,
        job_description_id=jd_id,
        turn_id=turn_id,
        before_version=before_version,
        after_version=after_version,
    )
