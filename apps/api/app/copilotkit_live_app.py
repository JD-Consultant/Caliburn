"""Production CopilotKit app：live deps + AsyncPostgresSaver（D15/D17）。
跑：run_live.py（:8001）。REST wiring 走 app_factory.configure；本模組只加
需要 DB 的部分（PG checkpointer + /copilotkit）。tests/docker 用 app.main（ADR 0017）。"""
# Windows: psycopg async（AsyncPostgresSaver checkpointer）需 SelectorEventLoop，
# 不可用預設 ProactorEventLoop。在「模組 import 時」設好 loop policy，這樣不論
# 經由 run_live.py 或 uvicorn --reload 的 worker 子進程（會 import 本模組）都生效。
import asyncio  # noqa: E402
import sys  # noqa: E402

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import AsyncExitStack, asynccontextmanager  # noqa: E402

from fastapi import FastAPI
from ag_ui_langgraph import add_langgraph_fastapi_endpoint

from app.app_factory import configure
from app.config import settings
from app.authoring.checkpointer import open_pg_checkpointer
from app.authoring.serving import build_live_agent, build_live_deps
from app.authoring.tracing import setup_tracing


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


# Production entry. REST wiring (routers + CORS + /healthz) comes from the single
# composition root; this module only adds what needs the DB: the PG checkpointer
# and the /copilotkit AG-UI endpoint (mounted in lifespan above). (ADR 0017)
app = configure(FastAPI(title="Caliburn (live)", lifespan=lifespan))
