"""Single aggregation point for the current job-analysis API."""
from fastapi import APIRouter

from app.api.routes import job_analysis

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(job_analysis.router)
