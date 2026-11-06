"""將 Workspace HTTP 請求交給 Application Service。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from caliburn.modules.workspace.application.errors import (
    InvalidWorkspacePaginationError,
    WorkspaceConcurrencyError,
    WorkspaceNotFoundError,
)
from caliburn.modules.workspace.application.results import WorkspaceResult
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.presentation.api.schemas import (
    CreateWorkspaceRequest,
    RenameWorkspaceRequest,
    WorkspaceConflictDetail,
    WorkspaceConflictResponse,
    WorkspacePageResponse,
    WorkspaceResponse,
)
from caliburn.shared.presentation.api.schemas import ErrorDetail, ErrorResponse
from caliburn.shared.presentation.api.values import HttpId


def _workspace_response(result: WorkspaceResult) -> WorkspaceResponse:
    return WorkspaceResponse(
        workspace_id=result.workspace_id,
        interviewee_name=result.interviewee_name,
    )


def build_workspace_router(
    service: WorkspaceService,
    *,
    create_workspace: Callable[[str], WorkspaceResult] | None = None,
    delete_workspace: Callable[[UUID], Awaitable[None]] | None = None,
) -> APIRouter:
    """接收已組裝的服務，負責 HTTP 解析與結果映射。"""
    router = APIRouter(prefix="/workspaces", tags=["workspaces"])

    @router.post(
        "",
        response_model=WorkspaceResponse,
        status_code=status.HTTP_201_CREATED,
        operation_id="create_workspace",
        summary="建立 Workspace",
        responses={
            201: {
                "headers": {
                    "Location": {
                        "description": "新 Workspace 的查詢位址",
                        "schema": {"type": "string", "format": "uri"},
                    }
                }
            }
        },
    )
    def create(
        body: CreateWorkspaceRequest, request: Request, response: Response
    ) -> WorkspaceResponse:
        result = (
            service.create(interviewee_name=body.interviewee_name)
            if create_workspace is None
            else create_workspace(body.interviewee_name)
        )
        response.headers["Location"] = str(
            request.url_for("get_workspace", workspace_id=result.workspace_id)
        )
        return _workspace_response(result)

    @router.get(
        "",
        response_model=WorkspacePageResponse,
        operation_id="list_workspaces",
        summary="列出 Workspace",
    )
    def list_page(
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        after: HttpId | None = None,
    ) -> WorkspacePageResponse:
        try:
            result = service.list(limit=limit, after=after)
        except InvalidWorkspacePaginationError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=ErrorDetail(code="invalid_workspace_page").model_dump(
                    exclude_none=True
                ),
            ) from error
        return WorkspacePageResponse(
            items=[_workspace_response(item) for item in result.items],
            next_cursor=result.next_cursor,
        )

    @router.get(
        "/{workspace_id}",
        response_model=WorkspaceResponse,
        name="get_workspace",
        operation_id="get_workspace",
        summary="查詢 Workspace",
        responses={404: {"model": ErrorResponse}},
    )
    def get(workspace_id: HttpId) -> WorkspaceResponse:
        try:
            result = service.get(workspace_id=workspace_id)
        except WorkspaceNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetail(code="workspace_not_found").model_dump(
                    exclude_none=True
                ),
            ) from error
        return _workspace_response(result)

    @router.patch(
        "/{workspace_id}",
        response_model=WorkspaceResponse,
        operation_id="rename_workspace",
        summary="變更受訪者姓名",
        responses={404: {"model": ErrorResponse}},
    )
    def rename(workspace_id: HttpId, body: RenameWorkspaceRequest) -> WorkspaceResponse:
        try:
            result = service.rename(
                workspace_id=workspace_id, interviewee_name=body.interviewee_name
            )
        except WorkspaceNotFoundError as error:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=ErrorDetail(code="workspace_not_found").model_dump(
                    exclude_none=True
                ),
            ) from error
        return _workspace_response(result)

    @router.delete(
        "/{workspace_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        operation_id="delete_workspace",
        summary="刪除 Workspace 與全部內容歷史",
        responses={409: {"model": WorkspaceConflictResponse}},
    )
    async def delete(workspace_id: HttpId) -> Response:
        try:
            if delete_workspace is None:
                await asyncio.to_thread(service.delete, workspace_id=workspace_id)
            else:
                await delete_workspace(workspace_id)
        except WorkspaceConcurrencyError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=WorkspaceConflictDetail(reason=error.reason).model_dump(),
            ) from error
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
