"""Pydantic request/response models for the query API."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(10, ge=1, le=50)


class CodeName(BaseModel):
    code: str = ""
    name: str = ""


class OcsName(BaseModel):
    job_category_name: Optional[str] = None
    occupation_name: Optional[str] = None

class OccupationDetail(BaseModel):
    ocs_code: str
    urn: str
    ocs_name: OcsName
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: Optional[int] = None
    attitudes: list[CodeName] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class TaskRef(BaseModel):
    task_code: str
    task_name: str
    urn: str

class UnitTasks(BaseModel):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    urn: str
    tasks: list[TaskRef] = Field(default_factory=list)

class OccupationTasks(BaseModel):
    ocs_code: str
    ocs_name: str
    units: list[UnitTasks] = Field(default_factory=list)


class OccupationHit(BaseModel):
    ocs_code: str
    urn: str
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: Optional[int] = None
    score: Optional[float] = None

class OccupationSearchResponse(BaseModel):
    hits: list[OccupationHit]


class TaskHit(BaseModel):
    ocs_code: str
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    urn: str
    score: Optional[float] = None

class TaskSearchResponse(BaseModel):
    hits: list[TaskHit]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    qdrant: str
    collection: str


class StatsResponse(BaseModel):
    collection: str
    total_points: int
    by_level: dict[str, int]


class SourceRef(BaseModel):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_level: Optional[int] = None


class CitableItem(BaseModel):
    id: str                      # URN
    type: str                    # K | S | O | P | A
    code: str
    name: Optional[str] = None   # K/S/O/A
    text: Optional[str] = None   # P
    ocs_code: str
    ocs_name: str
    sources: list[SourceRef] = Field(default_factory=list)


class CompetencyPool(BaseModel):
    ocs_code: str
    knowledge: list[CitableItem] = Field(default_factory=list)
    skills: list[CitableItem] = Field(default_factory=list)
    outputs: list[CitableItem] = Field(default_factory=list)
    indicators: list[CitableItem] = Field(default_factory=list)
    attitudes: list[CitableItem] = Field(default_factory=list)


class TaskBatchGetRequest(BaseModel):
    ids: list[str] = Field(min_length=1)

class TaskDetail(BaseModel):
    id: str
    urn: str
    ocs_code: str
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_blocks: list[dict] = Field(default_factory=list)

class TasksResponse(BaseModel):
    tasks: list[TaskDetail]


class FindSimilarRequest(BaseModel):
    ocs_codes: list[str] = Field(min_length=1)
    score_threshold: float = Field(0.85, ge=0.0, le=1.0)


class SimilarTaskRef(BaseModel):
    urn: str
    ocs_code: str
    task_code: str
    task_name: str


class SimilarPair(BaseModel):
    a: SimilarTaskRef
    b: SimilarTaskRef
    score: float


class FindSimilarResponse(BaseModel):
    candidates: list[SimilarPair]
