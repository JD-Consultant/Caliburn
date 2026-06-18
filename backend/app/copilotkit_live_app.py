"""Production v3 CopilotKit app：live deps + AsyncPostgresSaver（D15/D17）。
跑：uvicorn app.copilotkit_live_app:app --port 8000
demo（無依賴）仍在 app.copilotkit_app。"""
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from app.api.routes import job_profiles, users
from app.config import settings
from app.graph_v3.checkpointer import open_pg_checkpointer
from app.graph_v3.serving import build_live_agent, build_live_deps
from app.graph_v3.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_tracing()
    async with AsyncExitStack() as stack:
        saver = await stack.enter_async_context(open_pg_checkpointer(settings.database_url))
        deps = build_live_deps()
        add_langgraph_fastapi_endpoint(app, build_live_agent(saver, deps), "/copilotkit")
        try:
            yield
        finally:
            await deps.knowledge.aclose()   # 關 httpx client


app = FastAPI(title="jobintel v3 (live)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# v3 CRUD（dashboard/新增職務用）：只掛 users + job_profiles，
# 不掛舊 documents/tasks/interviews 路由（綁已移除的 graph_state，屬舊架構）。
app.include_router(users.router, prefix="/api/v1")
app.include_router(job_profiles.router, prefix="/api/v1")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
