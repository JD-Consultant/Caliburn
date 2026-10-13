"""JD 依據的查閱投影，與內部固定來源／資格分開。"""

from typing import Literal

from pydantic import StrictBool, StrictStr

from caliburn.features.interviews.models import InterviewSpeaker
from caliburn.features.job_description.models import ProfileField
from caliburn.features.job_description.sources import SourceTargetKind
from caliburn.transport.http.models.common import HttpModel, NonemptyText, PositiveInteger, WireUuid


class Target(HttpModel):
    kind: SourceTargetKind
    field: ProfileField | None
    item_id: WireUuid | None


class Reference(HttpModel):
    citation_id: WireUuid
    target_label: StrictStr
    target: Target
    source_kind: Literal["interview", "work_situation", "work_understanding"]
    source_label: StrictStr
    needs_recheck: StrictBool
    jd_changed: StrictBool
    source_changed: StrictBool


class JdSourcesView(HttpModel):
    revision_id: WireUuid
    references: list[Reference]


class SourceLink(HttpModel):
    source_ref: NonemptyText
    kind: Literal["interview", "work_situation"]
    label: StrictStr


class MemoryContent(HttpModel):
    kind: Literal["work_situation", "work_understanding"]
    title: StrictStr
    description: StrictStr
    body: StrictStr
    references: list[SourceLink]


class InterviewContent(HttpModel):
    kind: Literal["interview"]
    interview_sequence: PositiveInteger
    speaker: InterviewSpeaker
    interview_text: StrictStr


class JdSourceContentView(HttpModel):
    revision_id: WireUuid
    citation_id: WireUuid
    content: MemoryContent | InterviewContent


class SourceVersion(HttpModel):
    snapshot_id: WireUuid
    revision_id: WireUuid | None
    covered_through_sequence: PositiveInteger


class JdSourceChangesView(HttpModel):
    revision_id: WireUuid
    citation_id: WireUuid
    jd_markdown: StrictStr
    source_markdown: StrictStr | None
    source_version: SourceVersion | None
    comparison_version: SourceVersion | None
