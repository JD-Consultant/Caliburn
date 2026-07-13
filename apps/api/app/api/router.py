"""Single aggregation point for all REST routers (ADR 0017).

The one place that decides which routers the API exposes. Both app entry
module (``main``) mounts this via
``app_factory.configure`` so the route set can't drift between the app tests
hit and the app production runs.
"""
from fastapi import APIRouter

from app.api.routes import ai, documents, interview, job_profiles, occupations, users

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(users.router)
api_router.include_router(job_profiles.router)
api_router.include_router(documents.router)
api_router.include_router(occupations.router)
api_router.include_router(ai.router)
api_router.include_router(interview.router)
