"""Composition dependencies owned by the current job-analysis routes."""

import httpx

from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.config import settings
from app.database import AsyncSessionLocal
from app.job_analysis.application import JobAnalysisUnitOfWorkFactory
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    httpx_chat_transport,
)


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
