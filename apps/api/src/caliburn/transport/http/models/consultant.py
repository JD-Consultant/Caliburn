"""顧問輪次、公開過程及計畫的 HTTP 值；不授予執行資格。"""

from typing import Literal

from pydantic import Field, StrictBool, StrictStr, field_validator

from caliburn.contracts.generated.tools.interview_plan import InterviewPlan
from caliburn.features.executions.models import ExecutionStatus
from caliburn.transport.http.models.common import (
    HttpModel,
    NonblankText,
    NonemptyText,
    NonnegativeInteger,
    WireUuid,
)
from caliburn.transport.http.models.jd_views import CandidateJdPreview

type AllowedControl = Literal["pause", "cancel", "resume"]


class HealthStatus(HttpModel):
    status: Literal["ok"]


class SubmitInterviewInput(HttpModel):
    command_id: WireUuid
    text: NonblankText


class AcceptedInterviewInput(HttpModel):
    job_file_id: WireUuid
    command_id: WireUuid
    source_id: WireUuid
    execution_id: WireUuid


class PublicCommentary(HttpModel):
    response_id: NonemptyText
    message_id: NonemptyText
    text: NonemptyText


class CommentaryUpdate(HttpModel):
    job_file_id: WireUuid
    execution_id: WireUuid
    response_id: StrictStr
    message_id: StrictStr
    text: StrictStr


class ReasoningSummary(HttpModel):
    response_id: NonemptyText
    item_id: NonemptyText
    output_index: NonnegativeInteger
    summary_index: NonnegativeInteger
    text: NonemptyText


class ConsultantTurn(HttpModel):
    job_file_id: WireUuid
    execution_id: WireUuid
    status: ExecutionStatus
    pause_requested: StrictBool
    input_text: NonemptyText
    commentary: list[PublicCommentary] | None
    candidate: CandidateJdPreview | None
    plan_preview: InterviewPlan | None
    allowed_controls: list[AllowedControl] = Field(
        max_length=3, json_schema_extra={"uniqueItems": True}
    )

    @field_validator("allowed_controls")
    @classmethod
    def unique_controls(cls, value: list[AllowedControl]) -> list[AllowedControl]:
        if len(value) != len(set(value)):
            raise ValueError("Controls must be unique")
        return value


class CurrentConsultantTurn(HttpModel):
    turn: ConsultantTurn | None


class InterviewPlanView(InterviewPlan):
    job_file_id: WireUuid


class TurnJdChanges(HttpModel):
    execution_id: WireUuid
    markdown: StrictStr


class Call(HttpModel):
    request_id: WireUuid
    response_id: StrictStr
    call_id: StrictStr
    name: StrictStr
    arguments: StrictStr
    result_state: Literal["recorded", "not_recorded"]
    output: StrictStr | None


class TurnTools(HttpModel):
    execution_id: WireUuid
    calls: list[Call]
