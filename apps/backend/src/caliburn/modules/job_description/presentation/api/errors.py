"""JD HTTP 錯誤分類；提交事實與原始例外訊息分離。"""

from collections.abc import Callable, Coroutine
from typing import Any

from fastapi import Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import Field
from starlette.exceptions import HTTPException

from caliburn.modules.job_description.application import errors as application
from caliburn.modules.job_description.application.turn_history import (
    JobDescriptionTurnDataError,
    JobDescriptionTurnNotFoundError,
)
from caliburn.modules.job_description.domain import errors as domain
from caliburn.modules.job_description.domain.errors import (
    InvalidDefinitionOrderError,
)
from caliburn.shared.presentation.api.diagnostics import log_http_failure
from caliburn.shared.presentation.api.errors import validation_issues
from caliburn.shared.presentation.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    ValidationIssue,
)

from .schemas import PUBLIC_VALIDATION_FIELDS


class JobDescriptionErrorDetail(ErrorDetail):
    commit_status: application.CommitStatus | None = Field(
        default=None,
        description=(
            "not_committed：已確認未提交；committed：已提交但回覆或收尾失敗；"
            "unknown：提交效果未確認。讀取錯誤可省略；寫入錯誤缺此欄位時，"
            "須保守視為未知。不自動重送寫入，重新讀取核對目前狀態。"
        ),
    )
    reason: application.ConcurrencyReason | None = Field(
        default=None,
        description="jd_concurrency_conflict 的拒絕原因；version 表示原版本已過期。",
    )


class JobDescriptionErrorResponse(ErrorResponse):
    detail: JobDescriptionErrorDetail


ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": JobDescriptionErrorResponse, "description": "無法解碼請求內容"},
    404: {
        "model": JobDescriptionErrorResponse,
        "description": (
            "指定內容不存在。JD lookup 回 jd_not_found 時須先確認 Workspace 存在；"
            "建立時 workspace_not_found 表示檔案不存在，不能重建 JD。"
        ),
    },
    409: {
        "model": JobDescriptionErrorResponse,
        "description": (
            "jd_already_exists：已有 JD，首次建立競爭後可重查；"
            "jd_name_conflict：名稱重複；jd_concurrency_conflict：依 reason 處理，"
            "不自動換新版或重送。"
        ),
    },
    422: {"model": JobDescriptionErrorResponse, "description": "輸入或領域規則不符"},
    500: {
        "model": JobDescriptionErrorResponse,
        "description": "技術失敗；寫入請核對 commit_status，勿自動重送",
        "headers": {
            "X-Request-ID": {
                "description": "故障日誌識別，非重試或恢復憑證",
                "schema": {"type": "string"},
            }
        },
    },
}

_REJECTIONS: dict[type[Exception], tuple[int, str]] = {
    JobDescriptionTurnNotFoundError: (404, "jd_turn_not_found"),
    application.JobDescriptionWorkspaceNotFoundError: (404, "workspace_not_found"),
    application.JobDescriptionNotFoundError: (404, "jd_not_found"),
    application.JobDescriptionHistoryNotFoundError: (404, "jd_history_not_found"),
    application.TaskNotFoundError: (404, "task_not_found"),
    application.DutyNotFoundError: (404, "duty_not_found"),
    application.KnowledgeNotFoundError: (404, "knowledge_not_found"),
    application.SkillNotFoundError: (404, "skill_not_found"),
    application.CitationNotFoundError: (404, "citation_not_found"),
    application.InvalidCitationSourceError: (422, "invalid_citation_source"),
    domain.CitationTargetNotFoundError: (404, "citation_target_not_found"),
    domain.CitationNotFoundError: (404, "citation_not_found"),
    domain.InvalidCitationError: (422, "invalid_citation"),
    domain.TaskNotFoundError: (404, "task_not_found"),
    domain.DutyNotFoundError: (404, "duty_not_found"),
    domain.KnowledgeNotFoundError: (404, "knowledge_not_found"),
    domain.SkillNotFoundError: (404, "skill_not_found"),
    domain.TaskOutcomeNotFoundError: (404, "outcome_not_found"),
    domain.TaskRequirementNotFoundError: (404, "requirement_not_found"),
    domain.CollaborationNotFoundError: (404, "collaboration_not_found"),
    domain.JobConditionNotFoundError: (404, "condition_not_found"),
    application.JobDescriptionAlreadyExistsError: (409, "jd_already_exists"),
    application.JobDescriptionNameConflictError: (409, "jd_name_conflict"),
    domain.DuplicateNameError: (409, "jd_name_conflict"),
    application.JobDescriptionConcurrencyError: (409, "jd_concurrency_conflict"),
    application.InvalidTaskReferenceError: (422, "invalid_task_reference"),
    domain.InvalidTaskReferenceError: (422, "invalid_task_reference"),
    application.InvalidJobDescriptionInputError: (422, "invalid_jd_input"),
    application.InvalidHistoryPaginationError: (422, "invalid_history_pagination"),
    domain.InvalidNameError: (422, "invalid_name"),
    domain.InvalidTextError: (422, "invalid_text"),
    domain.InvalidCompetencyLevelError: (422, "invalid_competency_level"),
    domain.InvalidTaskOrderError: (422, "invalid_order"),
    InvalidDefinitionOrderError: (422, "invalid_order"),
    domain.InvalidJobDescriptionRecordOrderError: (422, "invalid_order"),
    domain.InvalidCollaborationNameError: (422, "invalid_collaborator_name"),
}


class JobDescriptionRoute(APIRoute):
    def get_route_handler(
        self,
    ) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handle(request: Request) -> Response:
            writing = request.method not in {"GET", "HEAD", "OPTIONS"}
            try:
                return await original(request)
            except RequestValidationError as error:
                decoding_failed = any(
                    issue["type"] == "json_invalid" for issue in error.errors()
                )
                return _error_response(
                    400 if decoding_failed else 422,
                    "invalid_request",
                    commit_status="not_committed" if writing else None,
                    errors=None
                    if decoding_failed
                    else validation_issues(
                        error, public_validation_fields=PUBLIC_VALIDATION_FIELDS
                    ),
                )
            except HTTPException as error:
                if error.status_code != 400:
                    raise
                return _error_response(
                    400,
                    "invalid_request",
                    commit_status="not_committed" if writing else None,
                )
            except Exception as error:
                commit_status: application.CommitStatus | None
                for exception_type, (status, code) in _REJECTIONS.items():
                    if isinstance(error, exception_type):
                        return _error_response(
                            status,
                            code,
                            commit_status="not_committed" if writing else None,
                            reason=error.reason
                            if isinstance(
                                error, application.JobDescriptionConcurrencyError
                            )
                            else None,
                        )
                request_id = log_http_failure(request, error)
                if isinstance(error, application.JobDescriptionPersistenceError):
                    code = "jd_persistence_error"
                    commit_status = error.commit_status
                else:
                    code = (
                        "jd_turn_data_error"
                        if isinstance(error, JobDescriptionTurnDataError)
                        else "jd_citation_source_data_error"
                        if isinstance(error, application.CitationSourceDataError)
                        else "jd_history_data_error"
                        if isinstance(error, application.JobDescriptionHistoryDataError)
                        else "jd_query_error"
                        if isinstance(error, application.JobDescriptionQueryError)
                        else "internal_error"
                    )
                    commit_status = (
                        "committed"
                        if getattr(request.state, "jd_write_committed", False)
                        else "unknown"
                        if writing
                        else None
                    )
                response = _error_response(500, code, commit_status=commit_status)
                response.headers["X-Request-ID"] = request_id
                return response

        return handle


def _error_response(
    status: int,
    code: str,
    *,
    commit_status: application.CommitStatus | None,
    errors: list[ValidationIssue] | None = None,
    reason: application.ConcurrencyReason | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content=JobDescriptionErrorResponse(
            detail=JobDescriptionErrorDetail(
                code=code, commit_status=commit_status, errors=errors, reason=reason
            )
        ).model_dump(mode="json", exclude_none=True),
    )
