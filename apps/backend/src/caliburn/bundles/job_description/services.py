"""Host 注入的 JD 公開查詢、短交易與共用模型定位。"""

from collections.abc import Awaitable, Callable
from uuid import UUID

from langgraph.types import StateSnapshot

from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceQueries,
)
from caliburn.modules.job_description.application.history.operations import (
    HistoryQueries,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.queries import JobDescriptionQueries
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.modules.model_references.contracts import ModelReferences

JD_QUERIES = ServiceKey[JobDescriptionQueries]("jd_queries")
JD_HISTORY_QUERIES = ServiceKey[HistoryQueries]("jd_history_queries")
JD_UOW_FACTORY = ServiceKey[Callable[[], JobDescriptionUnitOfWork]]("jd_uow_factory")
JD_REFERENCES = ServiceKey[ModelReferences]("jd_references")
JD_MEMORY_QUERIES = ServiceKey[MemoryQueries]("jd_memory_queries")
JD_CITATION_SOURCES = ServiceKey[CitationSourceQueries]("jd_citation_sources")
JD_PREVIOUS_COMPLETED = ServiceKey[
    Callable[[UUID, UUID], Awaitable[StateSnapshot | None]]
]("jd_previous_completed_turn")
