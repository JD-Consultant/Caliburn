"""Public reference HTTP shapes; independent of employee state and JD completion."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReferenceSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    query: str = Field(min_length=1, max_length=12_000)
    limit: int = Field(default=5, ge=1, le=5)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must contain work content")
        return value


class ReferenceTaskName(BaseModel):
    code: str | None
    name: str | None


class ReferenceTaskSummary(BaseModel):
    task_id: str
    names: list[ReferenceTaskName]
    competency_block_count: int


class ReferenceUnit(BaseModel):
    unit_id: str
    code: str | None
    name: str | None
    tasks: list[ReferenceTaskSummary]


class OccupationReference(BaseModel):
    reference_id: str
    source_sha256: str
    source_file: str
    ocs_code: str
    title: str
    overview: str
    catalog_scope: Literal["all_parsed_task_groups"] = "all_parsed_task_groups"
    units: list[ReferenceUnit]


class ReferenceEvidence(BaseModel):
    document_cosine: float | None
    task_cosine: float | None
    matched_task_ids: list[str]
    overview_matched: bool
    task_applicability: Literal["not_evaluated"] = "not_evaluated"


class OccupationReferenceHit(BaseModel):
    reference: OccupationReference
    retrieval_evidence: ReferenceEvidence
    rerank_logit: float


class ReferenceRetrievalPolicy(BaseModel):
    preprocessing: str
    candidate_limit_per_route: int
    candidate_count: int
    search: Literal["exact_dense_cosine"] = "exact_dense_cosine"
    fusion: Literal["full_union_before_rerank"] = "full_union_before_rerank"
    embedding_model: str
    embedding_dimensions: int
    reranker_model: str
    reranker_revision: str


class ReferenceSearchResponse(BaseModel):
    references: list[OccupationReferenceHit]
    retrieval_policy: ReferenceRetrievalPolicy


class ReferenceNamedContent(BaseModel):
    code: str | None
    name: str | None


class ReferenceIndicator(BaseModel):
    code: str | None
    text: str | None


class ReferenceCompetencyBlock(BaseModel):
    competency_level: int | None
    outputs: list[ReferenceNamedContent]
    indicators: list[ReferenceIndicator]
    knowledge: list[ReferenceNamedContent]
    skills: list[ReferenceNamedContent]


class ReferenceTaskDetail(BaseModel):
    reference_id: str
    source_sha256: str
    task_id: str
    unit_id: str
    names: list[ReferenceTaskName]
    competency_blocks: list[ReferenceCompetencyBlock]
