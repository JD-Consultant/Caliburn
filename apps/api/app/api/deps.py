"""Composition dependencies owned by the current job-analysis routes."""

import httpx
from fastapi import Request

from app.adapters.openrouter import (
    OpenRouterAdapter,
    OpenRouterConfig,
    httpx_chat_transport,
)
from app.adapters.postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.config import settings
from app.core.persistence import JobAnalysisUnitOfWorkFactory
from app.database import AsyncSessionLocal
from app.adapters.langgraph.postgres import PostgresConsultantRuntime
from app.consultant.run_service import ConsultantTurnProcessor


def get_job_analysis_uow_factory() -> JobAnalysisUnitOfWorkFactory:
    return lambda: SqlAlchemyJobAnalysisUnitOfWork(AsyncSessionLocal)


async def get_job_analysis_adapter():
    """One exact A6 route; no registry, fallback, retry, or legacy AI wiring."""

    async with httpx.AsyncClient() as client:
        yield OpenRouterAdapter(
            config=OpenRouterConfig(
                model=settings.job_analysis_model,
                provider_order=(settings.job_analysis_provider,),
                max_output_tokens=settings.job_analysis_max_output_tokens,
                timeout_seconds=settings.job_analysis_timeout_s,
            ),
            api_key=settings.openrouter_api_key,
            transport=httpx_chat_transport(client),
        )


def get_consultant_runtime(request: Request) -> PostgresConsultantRuntime:
    return request.app.state.consultant_runtime


def get_consultant_turn_processor(request: Request) -> ConsultantTurnProcessor:
    return request.app.state.consultant_turn_processor
