"""Own reference clients, lazy local models and their blocking execution lane."""

from collections.abc import AsyncIterator, Iterator
from contextlib import ExitStack, asynccontextmanager, contextmanager
from dataclasses import dataclass

from qdrant_client import QdrantClient

from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration
from caliburn.modules.occupation_reference.infrastructure.execution import (
    RetrievalWorker,
)
from caliburn.modules.occupation_reference.infrastructure.models.local import (
    LocalModels,
)
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    QdrantReferenceStore,
)


@dataclass(frozen=True)
class ReferenceResources:
    client: QdrantClient
    models: LocalModels
    search: ReferenceSearch


@contextmanager
def open_reference_resources(
    configuration: ReferenceConfiguration,
) -> Iterator[ReferenceResources]:
    """Construction opens no models and never builds or migrates an index."""
    with ExitStack() as stack:
        client = QdrantClient(
            url=configuration.qdrant_url,
            timeout=configuration.qdrant_timeout_seconds,
            check_compatibility=False,
        )
        stack.callback(client.close)
        models = LocalModels(
            embedding_path=configuration.embedding_path,
            reranker_path=configuration.reranker_path,
            cache_dir=configuration.cache_dir,
            device=configuration.device,
            use_fp16=configuration.use_fp16,
            batch_size=configuration.batch_size,
        )
        stack.callback(models.close)
        store = QdrantReferenceStore(client, configuration.collection, models.signature)
        yield ReferenceResources(
            client,
            models,
            ReferenceSearch(
                store, models, models, candidate_limit=configuration.candidate_limit
            ),
        )


@asynccontextmanager
async def open_reference(
    configuration: ReferenceConfiguration,
) -> AsyncIterator[tuple[ReferenceSearch, RetrievalWorker]]:
    """Drain physical model work before closing either model or database client."""
    with open_reference_resources(configuration) as resources:
        worker = RetrievalWorker(
            admission_timeout=configuration.admission_timeout_seconds
        )
        try:
            yield resources.search, worker
        finally:
            await worker.aclose()
