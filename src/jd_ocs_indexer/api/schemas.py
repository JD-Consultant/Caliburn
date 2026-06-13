"""Pydantic request/response models for the query API."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class SearchFilters(BaseModel):
    ocs_code: Optional[str] = None
    is_current: Optional[bool] = None
    k_codes: Optional[list[str]] = None
    s_codes: Optional[list[str]] = None
    attitude_codes: Optional[list[str]] = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    level: Optional[Literal["profile", "unit", "block"]] = None
    hybrid: bool = True
    top_k: int = Field(10, ge=1, le=50)
    filters: SearchFilters = Field(default_factory=SearchFilters)
    include_text: bool = False
    text_lines: int = Field(6, ge=0, le=50)


class Pair(BaseModel):
    code: str
    name: str


class Hit(BaseModel):
    chunk_key: str
    chunk_level: str
    ocs_code: str
    job_title: str
    score: Optional[float] = None
    version: Optional[str] = None
    is_current: Optional[bool] = None
    ocs_level: Optional[int] = None
    competency_level: Optional[int] = None
    unit_id: Optional[str] = None
    unit_title: Optional[str] = None
    unit_order: Optional[int] = None
    task_ids: list[str] = Field(default_factory=list)
    task_titles: list[str] = Field(default_factory=list)
    block_order: Optional[int] = None
    k_pairs: list[Pair] = Field(default_factory=list)
    s_pairs: list[Pair] = Field(default_factory=list)
    industry_names: list[str] = Field(default_factory=list)
    occupation_names: list[str] = Field(default_factory=list)
    source_file: Optional[str] = None
    snippet: Optional[str] = None


class SearchResponse(BaseModel):
    mode: str
    level: Optional[str] = None
    hits: list[Hit]


class TaskPoolRequest(BaseModel):
    ocs_codes: list[str] = Field(min_length=1)
    activity_examples: int = Field(1, ge=0, le=10)


class Task(BaseModel):
    task_id: str
    task_title: Optional[str] = None
    activity_examples: list[str] = Field(default_factory=list)


class Unit(BaseModel):
    unit_id: Optional[str] = None
    unit_title: Optional[str] = None
    unit_order: Optional[int] = None
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


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    qdrant: str
    collection: str


class StatsResponse(BaseModel):
    collection: str
    total_points: int
    by_level: dict[str, int]
