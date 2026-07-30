"""Shared route dependencies (fastapi-best-practices "dependencies" module).

``get_knowledge`` moved here from routes/documents.py (ADR 0019) so both the
documents router and the root occupations router can depend on it.
"""
import httpx

from app.adapters.knowledge_http import HttpIndexerClient
from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.config import settings
from app.database import AsyncSessionLocal
from app.job_analysis.application import JobAnalysisUnitOfWorkFactory
from app.job_analysis.providers import (
    OpenRouterAdapter,
    OpenRouterConfig,
    httpx_chat_transport,
)


async def get_knowledge():
    client = HttpIndexerClient(
        settings.indexer_base_url, settings.indexer_api_key, settings.indexer_timeout_s
    )
    try:
        yield client
    finally:
        await client.aclose()


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
