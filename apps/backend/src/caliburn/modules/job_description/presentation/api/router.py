"""JD HTTP 統一組裝入口；各能力仍依業務責任分檔。"""

from fastapi import APIRouter

from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceQueries,
)
from caliburn.modules.job_description.application.history.operations import (
    HistoryQueries,
)
from caliburn.modules.job_description.application.queries import JobDescriptionQueries
from caliburn.modules.job_description.application.turn_history import (
    CompletedTurnReader,
)
from caliburn.modules.job_description.presentation.api.dependencies import (
    JobDescriptionUoWFactory,
)
from caliburn.modules.job_description.presentation.api.routes.citations import (
    build_citations_router,
)
from caliburn.modules.job_description.presentation.api.routes.collaborations import (
    build_collaborations_router,
)
from caliburn.modules.job_description.presentation.api.routes.conditions import (
    build_conditions_router,
)
from caliburn.modules.job_description.presentation.api.routes.definitions import (
    build_definitions_router,
)
from caliburn.modules.job_description.presentation.api.routes.duties import (
    build_duties_router,
)
from caliburn.modules.job_description.presentation.api.routes.history import (
    build_history_router,
)
from caliburn.modules.job_description.presentation.api.routes.job_descriptions import (
    build_job_descriptions_router,
)
from caliburn.modules.job_description.presentation.api.routes.queries import (
    build_queries_router,
)
from caliburn.modules.job_description.presentation.api.routes.tasks import (
    build_tasks_router,
)
from caliburn.modules.job_description.presentation.api.routes.turn_history import (
    build_turn_history_router,
)
from caliburn.modules.memory.application.persistence import MemoryQueries


def build_job_description_router(
    *,
    uow_factory: JobDescriptionUoWFactory,
    queries: JobDescriptionQueries,
    history_queries: HistoryQueries,
    citation_sources: CitationSourceQueries | None = None,
    memory_queries: MemoryQueries | None = None,
    completed_turn_reader: CompletedTurnReader | None = None,
) -> APIRouter:
    router = APIRouter()
    router.include_router(build_job_descriptions_router(uow_factory))
    router.include_router(build_duties_router(uow_factory))
    router.include_router(build_tasks_router(uow_factory))
    router.include_router(build_definitions_router(uow_factory))
    router.include_router(build_collaborations_router(uow_factory))
    router.include_router(build_conditions_router(uow_factory))
    router.include_router(build_queries_router(queries))
    router.include_router(
        build_history_router(queries=history_queries, uow_factory=uow_factory)
    )
    if completed_turn_reader is not None:
        router.include_router(
            build_turn_history_router(
                queries=history_queries,
                completed_turn_reader=completed_turn_reader,
                uow_factory=uow_factory,
            )
        )
    if citation_sources is not None and memory_queries is not None:
        router.include_router(
            build_citations_router(
                uow_factory=uow_factory,
                queries=queries,
                history_queries=history_queries,
                sources=citation_sources,
                memory_queries=memory_queries,
            )
        )
    elif citation_sources is not None or memory_queries is not None:
        raise ValueError("JD 引用查讀須同時組裝來源與 Memory 公開查詢")
    return router
