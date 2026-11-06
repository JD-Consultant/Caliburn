"""已完成輪次的 JD 差異與撤銷；固定版本由唯讀 callback 提供。"""

from fastapi import APIRouter, Request

from caliburn.modules.job_description.application.history.operations import (
    HistoryQueries,
)
from caliburn.modules.job_description.application.turn_history import (
    CompletedTurnReader,
    get_turn_changes,
    restore_completed_turn_changes,
)
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.responses import write_response
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.turn_history import (
    JobDescriptionTurnChangesResponse,
)
from caliburn.shared.presentation.api.values import HttpId


def build_turn_history_router(
    *,
    queries: HistoryQueries,
    completed_turn_reader: CompletedTurnReader,
    uow_factory: JobDescriptionUoWFactory,
) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions/{job_description_id}",
        tags=["JD 歷史"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.get(
        "/turns/{turn_id}/changes",
        operation_id="get_job_description_turn_changes",
        response_model=JobDescriptionTurnChangesResponse,
        summary="讀取完成輪次的固定 JD 前後內容與差異",
    )
    async def turn_changes(
        workspace_id: HttpId, job_description_id: HttpId, turn_id: HttpId
    ) -> JobDescriptionTurnChangesResponse:
        return JobDescriptionTurnChangesResponse.model_validate(
            await get_turn_changes(
                workspace_id=workspace_id,
                job_description_id=job_description_id,
                turn_id=turn_id,
                completed_turn_reader=completed_turn_reader,
                queries=queries,
            )
        )

    @router.post(
        "/turns/{turn_id}:restore",
        operation_id="restore_job_description_turn",
        response_model=JobDescriptionResponse,
        summary="撤銷已完成輪次的 JD 修改",
    )
    async def restore_turn(
        workspace_id: HttpId,
        job_description_id: HttpId,
        turn_id: HttpId,
        request: Request,
    ) -> JobDescriptionResponse:
        result = await restore_completed_turn_changes(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            turn_id=turn_id,
            completed_turn_reader=completed_turn_reader,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
