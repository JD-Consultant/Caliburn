"""Pydantic request/response models for the query API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    ocs_code: Optional[str] = None
    is_current: Optional[bool] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    level: Optional[Literal["profile", "task"]] = None
    hybrid: bool = True
    top_k: int = Field(10, ge=1, le=50)
    filters: SearchFilters = Field(default_factory=SearchFilters)


class Pair(BaseModel):
    code: str
    name: str


class Hit(BaseModel):
    id: Optional[str] = None
    chunk_level: str
    ocs_code: str
    score: Optional[float] = None
    # profile fields
    job_title: Optional[str] = None
    job_description: Optional[str] = None
    version: Optional[str] = None
    is_current: Optional[bool] = None
    ocs_level: Optional[int] = None
    industry_names: list[str] = Field(default_factory=list)
    occupation_names: list[str] = Field(default_factory=list)
    # task fields
    unit_id: Optional[str] = None
    unit_title: Optional[str] = None
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    competency_level: Optional[int] = None
    activity_examples: list[str] = Field(default_factory=list)
    k_pairs: list[Pair] = Field(default_factory=list)
    s_pairs: list[Pair] = Field(default_factory=list)
    output_pairs: list[Pair] = Field(default_factory=list)
    source_file: Optional[str] = None


class SearchResponse(BaseModel):
    mode: str
    level: Optional[str] = None
    hits: list[Hit]


class TaskPoolRequest(BaseModel):
    ocs_codes: list[str] = Field(min_length=1)
    activity_examples: int = Field(1, ge=0, le=10)


class Task(BaseModel):
    id: Optional[str] = None
    task_id: str
    task_title: Optional[str] = None
    activity_examples: list[str] = Field(default_factory=list)


class Unit(BaseModel):
    unit_id: Optional[str] = None
    unit_title: Optional[str] = None
    tasks: list[Task]


class OcsGroup(BaseModel):
    ocs_code: str
    job_title: str
    units: list[Unit]


class TaskPoolResponse(BaseModel):
    groups: list[OcsGroup]


class PairsResponse(BaseModel):
    ocs_code: str
    job_title: str
    all_k_pairs: list[Pair]
    all_s_pairs: list[Pair]
    all_a_pairs: list[Pair]
    all_output_pairs: list[Pair]
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class CodeName(BaseModel):
    code: str = ""
    name: str = ""


class ProfileMetaResponse(BaseModel):
    """Profile-metadata for the document header (D29)."""

    ocs_code: str
    job_title: str = ""
    job_category: CodeName = Field(default_factory=CodeName)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: Optional[int] = None
    attitudes: list[Pair] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    supplements: list[str] = Field(default_factory=list)


class TaskByIdRequest(BaseModel):
    ids: list[str] = Field(min_length=1)


class TaskDetail(BaseModel):
    id: str
    ocs_code: str
    unit_id: Optional[str] = None
    unit_title: Optional[str] = None
    task_id: Optional[str] = None
    task_title: Optional[str] = None
    competency_level: Optional[int] = None
    activity_examples: list[str] = Field(default_factory=list)
    k_pairs: list[Pair] = Field(default_factory=list)
    s_pairs: list[Pair] = Field(default_factory=list)
    output_pairs: list[Pair] = Field(default_factory=list)


class TasksResponse(BaseModel):
    tasks: list[TaskDetail]


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    qdrant: str
    collection: str


class StatsResponse(BaseModel):
    collection: str
    total_points: int
    by_level: dict[str, int]
