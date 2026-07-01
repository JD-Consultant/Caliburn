"""FastAPI router. Blocking embed/Qdrant work runs in a threadpool; the embed
lock serializes BGE-M3 calls (FlagEmbedding is not guaranteed thread-safe)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from jd_ocs_indexer.api import service
from jd_ocs_indexer.api.schemas import (
    CompetencyPool,
    FindSimilarRequest,
    FindSimilarResponse,
    HealthResponse,
    OccupationDetail,
    OccupationSearchResponse,
    OccupationTasks,
    SearchRequest,
    StatsResponse,
    TaskBatchGetRequest,
    TaskSearchResponse,
    TasksResponse,
)

router = APIRouter()


@router.post("/occupations:search", response_model=OccupationSearchResponse)
async def search_occupations(req: SearchRequest, request: Request):
    app = request.app
    def _run():
        with app.state.embed_lock:
            return service.search_occupations(
                app.state.client, app.state.embedder,
                app.state.settings.qdrant_collection, query=req.query, top_k=req.top_k)
    return await run_in_threadpool(_run)


@router.post("/tasks:search", response_model=TaskSearchResponse)
async def search_tasks(req: SearchRequest, request: Request):
    app = request.app
    def _run():
        with app.state.embed_lock:
            return service.search_tasks(
                app.state.client, app.state.embedder,
                app.state.settings.qdrant_collection, query=req.query, top_k=req.top_k)
    return await run_in_threadpool(_run)


# AIP-136 custom method (`:verb`). 刻意偏離嚴格 AIP-231:POST body {ids}
# (URN 長且可多 — AIP-136 的 URL 上限例外)、缺失 id 靜默略過(producer
# 去重流程需要容忍)。ADR 0019。
@router.post("/tasks:batchGet", response_model=TasksResponse)
async def batch_get_tasks(req: TaskBatchGetRequest, request: Request):
    app = request.app
    return await run_in_threadpool(
        service.batch_get_tasks, app.state.client,
        app.state.settings.qdrant_collection, ids=req.ids)


@router.post("/tasks:findSimilar", response_model=FindSimilarResponse)
async def find_similar_tasks(req: FindSimilarRequest, request: Request):
    app = request.app
    return await run_in_threadpool(
        service.find_similar_tasks, app.state.client,
        app.state.settings.qdrant_collection,
        ocs_codes=req.ocs_codes, score_threshold=req.score_threshold)


@router.get("/occupations/{ocs_code}", response_model=OccupationDetail)
async def get_occupation(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_occupation, app.state.client,
        app.state.settings.qdrant_collection, ocs_code=ocs_code)
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result


@router.get("/occupations/{ocs_code}/tasks", response_model=OccupationTasks)
async def get_occupation_tasks(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_occupation_tasks, app.state.client,
        app.state.settings.qdrant_collection, ocs_code=ocs_code)
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result


@router.get("/occupations/{ocs_code}/competencies", response_model=CompetencyPool)
async def get_competencies(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_competencies, app.state.client,
        app.state.settings.qdrant_collection, ocs_code=ocs_code)
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result


@router.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request):
    app = request.app
    return await run_in_threadpool(
        service.get_stats, app.state.client, app.state.settings.qdrant_collection
    )


# response_model documents the shape in OpenAPI; we still return JSONResponse
# directly so the status code can be 200 (ok) or 503 (degraded).
@router.get("/healthz", response_model=HealthResponse)
async def get_healthz(request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.healthcheck,
        app.state.client,
        app.state.embedder,
        app.state.settings.qdrant_collection,
    )
    code = 200 if result["status"] == "ok" else 503
    return JSONResponse(status_code=code, content=result)
