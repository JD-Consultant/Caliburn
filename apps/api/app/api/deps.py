"""Shared route dependencies (fastapi-best-practices "dependencies" module).

``get_knowledge`` moved here from routes/documents.py (ADR 0019) so both the
documents router and the root occupations router can depend on it.
"""
from app.adapters.knowledge_http import HttpIndexerClient
from app.adapters.job_analysis_postgres import SqlAlchemyJobAnalysisUnitOfWork
from app.config import settings
from app.database import AsyncSessionLocal
from app.job_analysis.application import JobAnalysisUnitOfWorkFactory


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
