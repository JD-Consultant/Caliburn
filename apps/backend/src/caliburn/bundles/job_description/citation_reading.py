"""沿同一 JD 快照展開公開來源結果，不在模型投影重算業務狀態。"""

from uuid import UUID

from caliburn.bundles.job_description.services import (
    JD_CITATION_SOURCES,
    JD_MEMORY_QUERIES,
)
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.job_description.application.citations import (
    CitationResult,
    describe_citation,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import MemoryReference


def read_citation_results(
    snapshot: JobDescriptionResult,
    *,
    services: PluginServices,
    published_version: int | None,
) -> dict[UUID, CitationResult]:
    if not snapshot.citations:
        return {}
    sources = services.require(JD_CITATION_SOURCES)
    memory = (
        services.require(JD_MEMORY_QUERIES)
        if published_version is not None
        and any(isinstance(item.source, MemoryReference) for item in snapshot.citations)
        else None
    )
    return {
        citation.id: describe_citation(
            citation=citation,
            sources=sources,
            published_version=published_version,
            memory_queries=memory,
        )
        for citation in snapshot.citations
    }
