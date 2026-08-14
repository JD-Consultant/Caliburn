"""Single aggregation point for the current job-analysis API."""
from fastapi import APIRouter

from app.api.routes import consultant, consultation, documents, export, opks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(documents.router)
api_router.include_router(consultation.router)
api_router.include_router(opks.router)
api_router.include_router(export.router)
api_router.include_router(consultant.router)
