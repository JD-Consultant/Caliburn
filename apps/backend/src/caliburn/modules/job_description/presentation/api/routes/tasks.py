"""任務的複合建立、局部修改與移動。"""

from fastapi import APIRouter, Request, Response, status

from caliburn.modules.job_description.application.tasks import lifecycle
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.errors import (
    ERROR_RESPONSES,
    JobDescriptionRoute,
)
from caliburn.modules.job_description.presentation.api.responses import (
    CREATED_RESPONSES,
    created_response,
    write_response,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CorrelationIdInput,
    ExpectedVersionQuery,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)
from caliburn.modules.job_description.presentation.api.schemas.tasks import (
    AddTaskRequest,
    UpdateTaskRequest,
)
from caliburn.shared.presentation.api.values import HttpId


def build_tasks_router(uow_factory: JobDescriptionUoWFactory) -> APIRouter:
    """只映射 HTTP 與用例；交易與版本前置由 Application 完成。"""
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/job-descriptions",
        tags=["jd-tasks"],
        route_class=JobDescriptionRoute,
        responses=ERROR_RESPONSES,
    )

    @router.post(
        "/{job_description_id}/tasks",
        response_model=JobDescriptionResponse,
        operation_id="jd_add_task",
        summary="新增任務與關聯內容",
        name="jd_add_task",
        status_code=status.HTTP_201_CREATED,
        responses=CREATED_RESPONSES,
    )
    def add_task(
        workspace_id: HttpId,
        job_description_id: HttpId,
        body: AddTaskRequest,
        request: Request,
        response: Response,
    ) -> JobDescriptionResponse:
        result = lifecycle.add_task(
            workspace_id=workspace_id,
            input=body.to_application(job_description_id),
            uow_factory=uow_factory,
        )
        return created_response(request, response, result)

    @router.patch(
        "/{job_description_id}/tasks/{task_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_update_task",
        summary="原子修改任務內容、分類、順序與關聯",
        description=(
            "自訂 JSON PATCH：省略欄位保留原值。先修改本體及 placement，再依 changes "
            "次序套用 O/P 與 K/S 關係。任一步驟拒絕則整份不提交；有效變更只增加一版。"
        ),
        name="jd_update_task",
    )
    def update_task(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        task_id: HttpId,
        body: UpdateTaskRequest,
    ) -> JobDescriptionResponse:
        result = lifecycle.update_task(
            workspace_id=workspace_id,
            input=body.to_application(job_description_id, task_id),
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    @router.delete(
        "/{job_description_id}/tasks/{task_id}",
        response_model=JobDescriptionResponse,
        operation_id="jd_delete_task",
        summary="刪除任務",
        name="jd_delete_task",
    )
    def delete_task(
        workspace_id: HttpId,
        request: Request,
        job_description_id: HttpId,
        task_id: HttpId,
        expected_version: ExpectedVersionQuery,
        correlation_id: CorrelationIdInput | None = None,
    ) -> JobDescriptionResponse:
        result = lifecycle.delete_task(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
            task_id=task_id,
            expected_version=expected_version,
            correlation_id=correlation_id,
            uow_factory=uow_factory,
        )
        return write_response(request, result)

    return router
