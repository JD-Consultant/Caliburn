"""正式訪談唯讀 API；不啟動模型或還原 Agent 執行。"""

from collections.abc import Iterator
from contextlib import contextmanager

from fastapi import APIRouter, HTTPException, Request, Response

from caliburn.modules.interview.application.errors import (
    InterviewDataError,
    InterviewMessageNotFoundError,
    InterviewQueryError,
    WorkspaceNotFoundError,
)
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.interview.application.queries import get_message, list_messages
from caliburn.modules.interview.application.results import (
    MessageView,
    TranscriptMessage,
)
from caliburn.shared.presentation.api.diagnostics import log_http_failure
from caliburn.shared.presentation.api.schemas import ErrorResponse
from caliburn.shared.presentation.api.values import HttpId


@contextmanager
def _read_errors(request: Request) -> Iterator[None]:
    try:
        yield
    except WorkspaceNotFoundError as error:
        raise HTTPException(404, detail={"code": "workspace_not_found"}) from error
    except InterviewMessageNotFoundError as error:
        raise HTTPException(
            404, detail={"code": "interview_message_not_found"}
        ) from error
    except (InterviewQueryError, InterviewDataError) as error:
        request_id = log_http_failure(request, error, status_code=503)
        raise HTTPException(
            503,
            detail={"code": "interview_unavailable"},
            headers={"X-Request-ID": request_id},
        ) from error


def build_interview_router(queries: InterviewQueries) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/interview/messages",
        tags=["interview"],
        responses={404: {"model": ErrorResponse}, 503: {"model": ErrorResponse}},
    )

    @router.get("", response_model=tuple[TranscriptMessage, ...])
    def list_transcript(
        workspace_id: HttpId,
        request: Request,
        response: Response,
        turn_id: HttpId | None = None,
    ) -> tuple[TranscriptMessage, ...]:
        with _read_errors(request):
            messages = list_messages(
                workspace_id=workspace_id, turn_id=turn_id, queries=queries
            )
        response.headers["Cache-Control"] = "no-store"
        return messages

    @router.get("/{message_id}", response_model=MessageView)
    def get_original(
        workspace_id: HttpId,
        message_id: HttpId,
        request: Request,
        response: Response,
    ) -> MessageView:
        with _read_errors(request):
            message = get_message(
                workspace_id=workspace_id, message_id=message_id, queries=queries
            )
        response.headers["Cache-Control"] = "no-store"
        return message

    return router
