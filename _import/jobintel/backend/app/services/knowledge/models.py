"""jd-ocs-indexer query API 的回應模型（typed，extra 欄位忽略以容忍 API 演進）。"""
from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    # populate_by_name：別名欄位仍可用欄位名建構（stub/測試用）。
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class CodeName(_Base):
    code: str = ""
    name: str = ""


class OcsName(_Base):
    job_category_name: str | None = None
    occupation_name: str | None = None


class SourceRef(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    competency_level: int | None = None


class CitableItem(_Base):
    id: str = ""
    type: str = ""
    code: str = ""
    name: str | None = None
    text: str | None = None
    ocs_code: str = ""
    ocs_name: str = ""
    sources: list[SourceRef] = Field(default_factory=list)


class OccupationDetail(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: OcsName = Field(default_factory=OcsName)
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: int | None = None
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class CompetencyPool(_Base):
    ocs_code: str = ""
    knowledge: list[CitableItem] = Field(default_factory=list)
    skills: list[CitableItem] = Field(default_factory=list)
    outputs: list[CitableItem] = Field(default_factory=list)
    indicators: list[CitableItem] = Field(default_factory=list)
    attitudes: list[CitableItem] = Field(default_factory=list)


class TaskRef(_Base):
    task_code: str = ""
    task_name: str = ""
    urn: str = ""


class UnitTasks(_Base):
    ocu_code: str | None = None
    ocu_name: str | None = None
    urn: str = ""
    tasks: list[TaskRef] = Field(default_factory=list)


class OccupationTasks(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    units: list[UnitTasks] = Field(default_factory=list)


class OccupationHit(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: int | None = None
    score: float | None = None


class OccupationSearchResponse(_Base):
    hits: list[OccupationHit] = Field(default_factory=list)


class TaskHit(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: str | None = None
    ocu_name: str | None = None
    task_code: str | None = None
    task_name: str | None = None
    urn: str = ""
    score: float | None = None


class TaskSearchResponse(_Base):
    hits: list[TaskHit] = Field(default_factory=list)
