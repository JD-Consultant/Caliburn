"""已提交 JD 的 HTTP 回覆與資源位置。"""

from typing import Any

from fastapi import Request, Response, status

from caliburn.modules.job_description.application.errors import (
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.presentation.api.schemas.content import (
    JobDescriptionResponse,
)

CREATED_RESPONSES: dict[int | str, dict[str, Any]] = {
    201: {
        "model": JobDescriptionResponse,
        "headers": {
            "Location": {
                "description": "本次完整 JD 的查詢 URL",
                "schema": {"type": "string", "format": "uri"},
            }
        },
    }
}


def write_response(
    request: Request, result: JobDescriptionResult
) -> JobDescriptionResponse:
    """回覆轉換失敗不能抹除 Application 已確認的提交事實。"""
    request.state.jd_write_committed = True
    try:
        return JobDescriptionResponse.model_validate(result)
    except Exception as error:
        raise JobDescriptionPersistenceError(commit_status="committed") from error


def created_response(
    request: Request, response: Response, result: JobDescriptionResult
) -> JobDescriptionResponse:
    payload = write_response(request, result)
    response.status_code = status.HTTP_201_CREATED
    response.headers["Location"] = str(
        request.url_for(
            "get_job_description",
            workspace_id=payload.workspace_id,
            job_description_id=payload.job_description_id,
        )
    )
    return payload
