"""Shared route dependencies (fastapi-best-practices "dependencies" module).

``get_knowledge`` moved here from routes/documents.py (ADR 0019) so both the
documents router and the root occupations router can depend on it.
"""
from app.adapters.knowledge_http import HttpIndexerClient
from app.config import settings


async def get_knowledge():
    client = HttpIndexerClient(
        settings.indexer_base_url, settings.indexer_api_key, settings.indexer_timeout_s
    )
    try:
        yield client
    finally:
        await client.aclose()
