"""讀取最新保存的 Plan；與 Agent 配置及輪次無關。"""

from fastapi import APIRouter, HTTPException, Request, Response

from caliburn.modules.plan.application.errors import (
    PlanDataError,
    PlanQueryError,
    WorkspaceNotFoundError,
)
from caliburn.modules.plan.application.queries import PlanQueries
from caliburn.modules.plan.presentation.api.schemas import PlanResponse
from caliburn.shared.presentation.api.diagnostics import log_http_failure
from caliburn.shared.presentation.api.schemas import ErrorResponse
from caliburn.shared.presentation.api.values import HttpId


def build_plan_router(queries: PlanQueries) -> APIRouter:
    """只注入唯讀公開介面；HTTP 不持有寫入依賴。"""
    router = APIRouter(prefix="/workspaces/{workspace_id}/plan", tags=["plan"])

    @router.get(
        "",
        response_model=PlanResponse,
        operation_id="get_current_plan",
        summary="查詢目前保存的 Plan",
        responses={
            200: {
                "headers": {
                    "Cache-Control": {
                        "description": "目前內容不快取",
                        "schema": {"type": "string", "const": "no-store"},
                    }
                }
            },
            404: {"model": ErrorResponse},
            503: {
                "model": ErrorResponse,
                "headers": {
                    "X-Request-ID": {
                        "description": "故障日誌識別",
                        "schema": {"type": "string"},
                    }
                },
            },
        },
    )
    def get_current(
        workspace_id: HttpId, request: Request, response: Response
    ) -> PlanResponse:
        try:
            plan = queries.get_current(workspace_id=workspace_id)
        except WorkspaceNotFoundError as error:
            raise HTTPException(404, detail={"code": "workspace_not_found"}) from error
        except (PlanQueryError, PlanDataError) as error:
            request_id = log_http_failure(request, error, status_code=503)
            raise HTTPException(
                503,
                detail={"code": "plan_unavailable"},
                headers={"X-Request-ID": request_id},
            ) from error
        response.headers["Cache-Control"] = "no-store"
        return PlanResponse(
            workspace_id=plan.workspace_id, version=plan.version, body=plan.body
        )

    return router
