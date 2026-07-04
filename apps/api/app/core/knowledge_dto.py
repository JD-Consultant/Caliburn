"""Indexer query-API DTOs — re-exported from the shared contract package.

Single source of truth = packages/indexer-contract. Kept as this module path so
existing `from app.core.knowledge_dto import ...` sites (ports, adapters, services,
tests) are unchanged.
"""
from indexer_contract.models import (  # noqa: F401
    CitableItem,
    CodeName,
    CompetencyPool,
    MatchItem,
    MatchResponse,
    OccupationDetail,
    OccupationHit,
    OccupationSearchResponse,
    OccupationTasks,
    OcsName,
    SourceRef,
    TaskHit,
    TaskRef,
    TaskSearchResponse,
    UnitTasks,
)
