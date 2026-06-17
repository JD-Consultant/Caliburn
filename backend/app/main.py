from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import documents, job_profiles, tasks, users
from app.config import settings
from app.database import AsyncSessionLocal, engine
from app.logging_config import setup_logging
from app.models.base import Base

setup_logging(debug=settings.debug)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="企業崗位知識萃取與職務說明書生成 AI",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router,        prefix="/api/v1")
app.include_router(job_profiles.router, prefix="/api/v1")
app.include_router(tasks.router,        prefix="/api/v1")
app.include_router(documents.router,    prefix="/api/v1")


@app.get("/health")
async def health():
    db_ok = False
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    return {
        "status": "ok" if db_ok else "degraded",
        "db":     db_ok,
        "app":    settings.app_name,
    }
