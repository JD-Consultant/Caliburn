"""Indexer query-API wire contract — single source of truth (ocs-indexer ⇄ api).

Both the producer (FastAPI request/response_model) and the consumer (KnowledgePort
return types + HttpIndexerClient parsing) import THESE classes. extra="ignore"
tolerates additive producer evolution on the consumer side.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ── requests ──────────────────────────────────────────────────────────────────
class SearchRequest(_Base):
    query: str = Field(min_length=1)
    top_k: int = Field(10, ge=1, le=50)


class TaskBatchGetRequest(_Base):
    ids: list[str] = Field(min_length=1)


class FindSimilarRequest(_Base):
    ocs_codes: list[str] = Field(min_length=1)
    score_threshold: float = Field(0.85, ge=0.0, le=1.0)


class MatchItem(_Base):
    id: str
    text: str
    sources: list[str] = Field(default_factory=list)


class MatchRequest(_Base):
    kind: str
    items: list[MatchItem] = Field(default_factory=list)


# ── leaves ────────────────────────────────────────────────────────────────────
class CodeName(_Base):
    code: str = ""
    name: str = ""


class OcsName(_Base):
    job_category_name: Optional[str] = None
    occupation_name: Optional[str] = None


class SourceRef(_Base):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_level: Optional[int] = None


class CitableItem(_Base):
    id: str = ""
    type: str = ""
    code: str = ""
    name: Optional[str] = None
    text: Optional[str] = None
    ocs_code: str = ""
    ocs_name: str = ""
    sources: list[SourceRef] = Field(default_factory=list)


# ── occupation detail / competencies ──────────────────────────────────────────
class OccupationDetail(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: OcsName = Field(default_factory=OcsName)
    job_categories: list[CodeName] = Field(default_factory=list)
    occupations: list[CodeName] = Field(default_factory=list)
    industries: list[CodeName] = Field(default_factory=list)
    job_description: str = ""
    ocs_level: Optional[int] = None
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


# ── occupation tasks ──────────────────────────────────────────────────────────
class TaskRef(_Base):
    task_code: str = ""
    task_name: str = ""
    urn: str = ""


class UnitTasks(_Base):
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    urn: str = ""
    tasks: list[TaskRef] = Field(default_factory=list)


class OccupationTasks(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    units: list[UnitTasks] = Field(default_factory=list)


# ── search ────────────────────────────────────────────────────────────────────
class OccupationHit(_Base):
    ocs_code: str = ""
    urn: str = ""
    ocs_name: str = ""
    job_description: str = ""
    ocs_level: Optional[int] = None
    score: Optional[float] = None


class OccupationSearchResponse(_Base):
    hits: list[OccupationHit] = Field(default_factory=list)


class TaskHit(_Base):
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    urn: str = ""
    score: Optional[float] = None


class TaskSearchResponse(_Base):
    hits: list[TaskHit] = Field(default_factory=list)


# ── batch get / find similar / ops ────────────────────────────────────────────
class TaskDetail(_Base):
    id: str = ""
    urn: str = ""
    ocs_code: str = ""
    ocs_name: str = ""
    ocu_code: Optional[str] = None
    ocu_name: Optional[str] = None
    task_code: Optional[str] = None
    task_name: Optional[str] = None
    competency_blocks: list[dict] = Field(default_factory=list)


class TasksResponse(_Base):
    tasks: list[TaskDetail] = Field(default_factory=list)


class SimilarTaskRef(_Base):
    urn: str = ""
    ocs_code: str = ""
    task_code: str = ""
    task_name: str = ""


class SimilarPair(_Base):
    left: SimilarTaskRef
    right: SimilarTaskRef
    score: float


class FindSimilarResponse(_Base):
    candidates: list[SimilarPair] = Field(default_factory=list)


# ── items:match 相似比對(ADR 0022)。pair 命名照 Splink left/right 慣例(禁用 a/b)──
class GroupMember(_Base):
    id: str = ""
    score: float = 0.0          # 與群中心的分數;中心自身 = 1.0


class MatchGroup(_Base):
    medoid: str = ""            # 幾何代表(群內平均相似度最高的成員 id)
    members: list[GroupMember] = Field(default_factory=list)


class PossibleMatch(_Base):
    left_id: str = ""
    right_id: str = ""          # 恆 left_id < right_id(決定論)
    score: float = 0.0


class MatchConfig(_Base):
    kind: str = ""
    theta_high: float = 0.0
    theta_low: float = 0.0
    model: str = "bge-m3"


class MatchResponse(_Base):
    groups: list[MatchGroup] = Field(default_factory=list)
    possible_matches: list[PossibleMatch] = Field(default_factory=list)
    config: MatchConfig = Field(default_factory=MatchConfig)


class HealthResponse(_Base):
    status: str = ""
    model_loaded: bool = False
    qdrant: str = ""
    collection: str = ""
    index_model: Optional[str] = None


class StatsResponse(_Base):
    collection: str = ""
    total_points: int = 0
    by_level: dict[str, int] = Field(default_factory=dict)
