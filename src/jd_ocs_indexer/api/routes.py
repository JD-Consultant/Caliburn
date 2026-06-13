"""FastAPI router. Blocking embed/Qdrant work runs in a threadpool; the embed
lock serializes BGE-M3 calls (FlagEmbedding is not guaranteed thread-safe)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

from jd_ocs_indexer.api import service
from jd_ocs_indexer.api.schemas import (
    PairsResponse,
    SearchRequest,
    SearchResponse,
    StatsResponse,
    TaskPoolRequest,
    TaskPoolResponse,
)

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
async def post_search(req: SearchRequest, request: Request):
    app = request.app

    def _run():
        with app.state.embed_lock:
            return service.search(
                app.state.client,
                app.state.embedder,
                app.state.settings.qdrant_collection,
                query=req.query,
                level=req.level,
                hybrid=req.hybrid,
                top_k=req.top_k,
                filters=req.filters.model_dump(),
                include_text=req.include_text,
                text_lines=req.text_lines,
            )

    return await run_in_threadpool(_run)


@router.post("/task-pool", response_model=TaskPoolResponse)
async def post_task_pool(req: TaskPoolRequest, request: Request):
    app = request.app
    return await run_in_threadpool(
        service.build_task_pool,
        app.state.client,
        app.state.settings.qdrant_collection,
        ocs_codes=req.ocs_codes,
        activity_examples=req.activity_examples,
    )


@router.get("/profile/{ocs_code}/pairs", response_model=PairsResponse)
async def get_profile_pairs(ocs_code: str, request: Request):
    app = request.app
    result = await run_in_threadpool(
        service.get_pairs,
        app.state.client,
        app.state.settings.qdrant_collection,
        ocs_code=ocs_code,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="ocs_code not found")
    return result


@router.get("/stats", response_model=StatsResponse)
async def get_stats(request: Request):
    app = request.app
    return await run_in_threadpool(
        service.get_stats, app.state.client, app.state.settings.qdrant_collection
    )


@router.get("/healthz")
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
