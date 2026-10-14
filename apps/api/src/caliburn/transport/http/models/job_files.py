"""職務檔案與正式訪談的 HTTP 值。"""

from pydantic import AwareDatetime, StrictStr

from caliburn.features.interviews.models import InterviewSpeaker
from caliburn.transport.http.models.common import (
    DisplayName,
    HeartbeatElapsedSeconds,
    HttpModel,
    NonnegativeInteger,
    PositiveInteger,
    WireUuid,
)


class CreateJobFileRequest(HttpModel):
    command_id: WireUuid
    display_name: DisplayName
    employee_name: DisplayName


class RenameJobFileRequest(HttpModel):
    command_id: WireUuid
    expected_name_revision: PositiveInteger
    display_name: DisplayName


class JobFile(HttpModel):
    job_file_id: WireUuid
    display_name: StrictStr
    name_revision: PositiveInteger
    employee_name: StrictStr
    created_at: AwareDatetime
    active_usage_seconds: NonnegativeInteger


class RecordUsageHeartbeatRequest(HttpModel):
    elapsed_seconds: HeartbeatElapsedSeconds


class JobFileList(HttpModel):
    job_files: list[JobFile]


class InterviewMessage(HttpModel):
    source_id: WireUuid
    interview_sequence: PositiveInteger
    speaker: InterviewSpeaker
    interview_text: StrictStr
    execution_id: WireUuid | None


class InterviewHistory(HttpModel):
    messages: list[InterviewMessage]
