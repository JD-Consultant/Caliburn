"""Query-API pydantic models — re-exported from the shared contract package.

Single source of truth = packages/indexer-contract. Kept as this module path so
api/routes.py imports are unchanged.
"""
from indexer_contract.models import (  # noqa: F401
    CitableItem,
    CodeName,
    CompetencyPool,
    FindSimilarRequest,
    FindSimilarResponse,
    HealthResponse,
    OccupationDetail,
    OccupationHit,
    OccupationSearchResponse,
    OccupationTasks,
    OcsName,
    SearchRequest,
    SimilarPair,
    SimilarTaskRef,
    SourceRef,
    StatsResponse,
    TaskBatchGetRequest,
    TaskDetail,
    TaskHit,
    TaskRef,
    TaskSearchResponse,
    TasksResponse,
    UnitTasks,
)
