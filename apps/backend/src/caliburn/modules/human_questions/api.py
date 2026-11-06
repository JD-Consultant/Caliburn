"""問答 HTTP；停用提問工具不移除已保存問答的查讀入口。"""

from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from caliburn.modules.agent.application.views import TurnView
from caliburn.modules.agent.presentation.api.errors import http_errors
from caliburn.modules.human_questions.agent_history import QuestionExchange
from caliburn.modules.human_questions.question_service import QuestionService
from caliburn.modules.human_questions.questions import AnswerBatch, InvalidAnswers
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    InterviewText,
)
from caliburn.shared.presentation.api.schemas import (
    ErrorDetail,
    ErrorResponse,
    ValidationIssue,
)
from caliburn.shared.presentation.api.values import HttpId

PUBLIC_VALIDATION_FIELDS = frozenset(
    {"model_step", "call_id", "answers", "question_message_id", "selected", "custom"}
)


def _json_number(value: object) -> object:
    if isinstance(value, (bool, str)):
        raise ValueError("模型步必須是 JSON 數值")
    return value


class AnswerRequest(AnswerInput):
    question_message_id: HttpId
    selected: tuple[InterviewText, ...] = Field(..., strict=False)


class AnswerTurnRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    answers: list[AnswerRequest]
    model_step: Annotated[int, BeforeValidator(_json_number)] = Field(
        ge=1, le=9007199254740991
    )
    call_id: str = Field(min_length=1)


def build_question_router(service_provider: Callable[[], QuestionService]) -> APIRouter:
    router = APIRouter(
        prefix="/workspaces/{workspace_id}/agent/turns/{turn_id}",
        tags=["human_questions"],
        responses={
            404: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )

    @router.get("/questions", response_model=list[QuestionExchange])
    async def list_questions(
        workspace_id: HttpId,
        turn_id: HttpId,
        service: Annotated[QuestionService, Depends(service_provider)],
    ) -> list[QuestionExchange]:
        with http_errors():
            return await service.list_questions(
                workspace_id=workspace_id, turn_id=turn_id
            )

    @router.post(
        "/answers",
        response_model=TurnView,
        status_code=202,
        responses={200: {"model": TurnView}, 422: {"model": ErrorResponse}},
    )
    async def answer(
        workspace_id: HttpId,
        turn_id: HttpId,
        body: AnswerTurnRequest,
        response: Response,
        service: Annotated[QuestionService, Depends(service_provider)],
    ) -> TurnView:
        with http_errors():
            try:
                result = await service.submit_answers(
                    workspace_id=workspace_id,
                    turn_id=turn_id,
                    model_step=body.model_step,
                    call_id=body.call_id,
                    answers=AnswerBatch(answers=list(body.answers)),
                )
            except InvalidAnswers as error:
                raise HTTPException(
                    422,
                    detail=ErrorDetail(
                        code="agent_invalid_answers",
                        errors=[
                            ValidationIssue(
                                loc=["body", *error.location], code="invalid_value"
                            )
                        ],
                    ).model_dump(mode="json"),
                ) from error
        response.status_code = 202 if result.created else 200
        return result.turn

    return router
