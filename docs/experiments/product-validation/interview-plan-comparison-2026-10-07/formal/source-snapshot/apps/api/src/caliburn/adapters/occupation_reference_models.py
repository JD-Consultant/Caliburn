"""Immutable external-reference values; no App state or independent RAG imports."""

from dataclasses import dataclass
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, with_config

_WIRE_CONFIG = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)
type _Locator = Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")]
type _SourceHash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
type _UnitId = Annotated[str, Field(pattern=r"^u[1-9][0-9]*$")]
type _TaskId = Annotated[str, Field(pattern=r"^u[1-9][0-9]*-t[1-9][0-9]*$")]
type _NonemptyText = Annotated[str, Field(min_length=1)]
type _Count = Annotated[int, Field(ge=0)]
type _PositiveCount = Annotated[int, Field(ge=1)]


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceTaskName:
    code: str | None
    name: str | None


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceTaskSummary:
    task_id: _TaskId
    names: tuple[ReferenceTaskName, ...]
    competency_block_count: _Count


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceUnit:
    unit_id: _UnitId
    code: str | None
    name: str | None
    tasks: tuple[ReferenceTaskSummary, ...]


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class OccupationReference:
    reference_id: _Locator
    source_sha256: _SourceHash
    source_file: _NonemptyText
    ocs_code: _NonemptyText
    title: _NonemptyText
    overview: str
    catalog_scope: Literal["all_parsed_task_groups"]
    units: tuple[ReferenceUnit, ...]


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceEvidence:
    document_cosine: float | None
    task_cosine: float | None
    matched_task_ids: tuple[_TaskId, ...]
    overview_matched: bool
    task_applicability: Literal["not_evaluated"]


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class OccupationReferenceHit:
    reference: OccupationReference
    retrieval_evidence: ReferenceEvidence
    rerank_logit: float


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceRetrievalPolicy:
    preprocessing: _NonemptyText
    candidate_limit_per_route: _PositiveCount
    candidate_count: _Count
    search: Literal["exact_dense_cosine"]
    fusion: Literal["full_union_before_rerank"]
    embedding_model: _NonemptyText
    embedding_dimensions: _PositiveCount
    reranker_model: _NonemptyText
    reranker_revision: _NonemptyText


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceSearchResult:
    references: tuple[OccupationReferenceHit, ...]
    retrieval_policy: ReferenceRetrievalPolicy


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceNamedContent:
    code: str | None
    name: str | None


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceIndicator:
    code: str | None
    text: str | None


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceCompetencyBlock:
    competency_level: int | None
    outputs: tuple[ReferenceNamedContent, ...]
    indicators: tuple[ReferenceIndicator, ...]
    knowledge: tuple[ReferenceNamedContent, ...]
    skills: tuple[ReferenceNamedContent, ...]


@with_config(_WIRE_CONFIG)
@dataclass(frozen=True, slots=True)
class ReferenceTaskDetail:
    reference_id: _Locator
    source_sha256: _SourceHash
    task_id: _TaskId
    unit_id: _UnitId
    names: tuple[ReferenceTaskName, ...]
    competency_blocks: tuple[ReferenceCompetencyBlock, ...]
