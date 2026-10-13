"""JD 查閱投影共用同一份區段型別，預覽不另複製整份 shape。"""

from pydantic import StrictStr

from caliburn.features.job_description.capabilities import CapabilityKind
from caliburn.features.job_description.conditions import ConditionKind
from caliburn.transport.http.models.common import HttpModel, WireUuid


class Profile(HttpModel):
    job_title: StrictStr | None
    organization_unit: StrictStr | None
    reports_to: StrictStr | None
    purpose: StrictStr | None


class JdProfileView(HttpModel):
    revision_id: WireUuid
    profile: Profile


class Area(HttpModel):
    area_id: WireUuid
    title: StrictStr | None
    scope_text: StrictStr | None


class JdAreasView(HttpModel):
    revision_id: WireUuid
    areas: list[Area]


class Detail(HttpModel):
    detail_id: WireUuid
    text: StrictStr


class WorkTask(HttpModel):
    task_id: WireUuid
    area_id: WireUuid | None
    title: StrictStr | None
    description: StrictStr | None
    outcomes: list[Detail]
    requirements: list[Detail]


class JdTasksView(HttpModel):
    revision_id: WireUuid
    tasks: list[WorkTask]


class Capability(HttpModel):
    capability_id: WireUuid
    kind: CapabilityKind
    name: StrictStr | None
    description: StrictStr | None


class TaskLink(HttpModel):
    task_id: WireUuid
    capability_id: WireUuid


class JdCapabilitiesView(HttpModel):
    revision_id: WireUuid
    capabilities: list[Capability]
    task_links: list[TaskLink]


class Collaborator(HttpModel):
    collaborator_id: WireUuid
    name: StrictStr | None
    scope_text: StrictStr | None


class JdCollaboratorsView(HttpModel):
    revision_id: WireUuid
    collaborators: list[Collaborator]


class Condition(HttpModel):
    condition_id: WireUuid
    kind: ConditionKind
    text: StrictStr


class JdConditionsView(HttpModel):
    revision_id: WireUuid
    conditions: list[Condition]


class JdWorkView(HttpModel):
    revision_id: WireUuid
    areas: list[Area]
    tasks: list[WorkTask]
    capabilities: list[Capability]
    task_links: list[TaskLink]
    collaborators: list[Collaborator]
    conditions: list[Condition]


class CandidateJdPreview(HttpModel):
    profile: Profile
    work: JdWorkView
