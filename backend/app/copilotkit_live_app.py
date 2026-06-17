"""Production v3 CopilotKit app：live deps + AsyncPostgresSaver（D15/D17）。
跑：uvicorn app.copilotkit_live_app:app --port 8000
demo（無依賴）仍在 app.copilotkit_app。"""
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from copilotkit.integrations.fastapi import add_fastapi_endpoint

from app.config import settings
from app.graph_v3.checkpointer import open_pg_checkpointer
from app.graph_v3.serving import build_live_deps, build_live_sdk


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncExitStack() as stack:
        saver = await stack.enter_async_context(open_pg_checkpointer(settings.database_url))
        deps = build_live_deps()
        add_fastapi_endpoint(app, build_live_sdk(saver, deps), "/copilotkit")
        try:
            yield
        finally:
            await deps.knowledge.aclose()   # 關 httpx client


app = FastAPI(title="jobintel v3 (live)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
