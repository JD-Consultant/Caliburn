"""來源引用公開用例與同交易內容修改接縫。"""

from collections.abc import Callable
from uuid import UUID

from pydantic import PositiveInt

from caliburn.modules.job_description.application.citation_changes import (
    CitationSourceComparison,
    compare_memory_citation,
)
from caliburn.modules.job_description.application.citation_inputs import (
    AddCitationInput,
    CitationChange,
    ConfirmCitationInput,
)
from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceQueries,
    CitationSourceView,
)
from caliburn.modules.job_description.application.errors import (
    CitationNotFoundError,
    InvalidCitationSourceError,
)
from caliburn.modules.job_description.application.history.operations import (
    HistoryQueries,
    get_history,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.queries import (
    JobDescriptionQueries,
    get_job_description,
)
from caliburn.modules.job_description.application.writing import save_and_commit
from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    CitationTargetKind,
    MemoryReference,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.memory.application.persistence import MemoryQueries
from caliburn.shared.application.base_dto import BaseDTO


class ChangeCitationsInput(BaseDTO):
    job_description_id: UUID
    expected_version: PositiveInt
    target_kind: CitationTargetKind
    target_id: UUID
    changes: tuple[CitationChange, ...]
    correlation_id: str | None = None


class CitationResult(BaseDTO):
    citation: Citation
    source: CitationSourceView
    comparison: CitationSourceComparison | None = None
    source_changed: bool | None
    needs_recheck: bool | None


def apply_citation_changes(
    job_description: JobDescription,
    *,
    target_kind: CitationTargetKind,
    target_id: UUID,
    changes: tuple[CitationChange, ...],
    uow: JobDescriptionUnitOfWork,
) -> None:
    job_description.require_citation_target(
        target_kind=target_kind, target_id=target_id
    )
    for change in changes:
        if isinstance(change, AddCitationInput):
            if change.source.workspace_id != job_description.workspace_id:
                raise InvalidCitationSourceError("來源不屬於此 Workspace")
            uow.citation_sources.require_available(source=change.source)
            job_description.add_citation(
                target_kind=target_kind, target_id=target_id, source=change.source
            )
        else:
            citation = next(
                (x for x in job_description.citations if x.id == change.citation_id),
                None,
            )
            if citation is None or (citation.target_kind, citation.target_id) != (
                target_kind,
                target_id,
            ):
                raise CitationNotFoundError("引用不存在於此 JD 的指定目標")
            if isinstance(change, ConfirmCitationInput):
                source = citation.source
                if isinstance(source, MemoryReference):
                    if change.published_version is None:
                        raise InvalidCitationSourceError(
                            "核對 Memory 引用須提供固定發布版"
                        )
                    source = MemoryReference(
                        workspace_id=source.workspace_id,
                        published_version=change.published_version,
                        item_id=source.item_id,
                    )
                elif change.published_version is not None:
                    raise InvalidCitationSourceError("訪談引用不接受 Memory 發布版")
                uow.citation_sources.require_available(source=source)
                job_description.confirm_citation(citation_id=citation.id, source=source)
            else:
                job_description.remove_citation(citation_id=citation.id)


def change_citations(
    *,
    workspace_id: UUID,
    input: ChangeCitationsInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
) -> JobDescriptionResult:
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id, job_description_id=input.job_description_id
        )
        loaded.require_version(expected_version=input.expected_version)
        apply_citation_changes(
            loaded.job_description,
            target_kind=input.target_kind,
            target_id=input.target_id,
            changes=input.changes,
            uow=uow,
        )
        return save_and_commit(
            loaded.job_description, uow=uow, correlation_id=input.correlation_id
        )


def get_citation(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    citation_id: UUID,
    queries: JobDescriptionQueries,
    sources: CitationSourceQueries,
    published_version: int | None = None,
    memory_queries: MemoryQueries | None = None,
) -> CitationResult:
    content = get_job_description(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        queries=queries,
    )
    citation = next((x for x in content.citations if x.id == citation_id), None)
    if citation is None:
        raise CitationNotFoundError("引用不存在於此 JD")
    return describe_citation(
        citation=citation,
        sources=sources,
        published_version=published_version,
        memory_queries=memory_queries,
    )


def get_history_citation(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    version: int,
    citation_id: UUID,
    history_queries: HistoryQueries,
    sources: CitationSourceQueries,
    published_version: int | None = None,
    memory_queries: MemoryQueries | None = None,
) -> CitationResult:
    """從指定 JD 保存點選引用，不以目前稿或最新 Memory 取代固定定位。"""
    historical = get_history(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        version=version,
        queries=history_queries,
    )
    citation = next(
        (item for item in historical.content.citations if item.id == citation_id),
        None,
    )
    if citation is None:
        raise CitationNotFoundError("引用不存在於指定 JD 保存點")
    return describe_citation(
        citation=citation,
        sources=sources,
        published_version=published_version,
        memory_queries=memory_queries,
    )


def describe_citation(
    *,
    citation: Citation,
    sources: CitationSourceQueries,
    published_version: int | None = None,
    memory_queries: MemoryQueries | None = None,
) -> CitationResult:
    """沿呼叫端已核對範圍及讀取的 JD 快照展開，不重新取得目前 JD。"""
    comparison = None
    source_changed: bool | None = False
    if isinstance(citation.source, MemoryReference):
        source_changed = None
        if published_version is not None:
            if memory_queries is None:
                raise ValueError("來源比較需要 Memory 公開查詢")
            comparison = compare_memory_citation(
                source=citation.source,
                published_version=published_version,
                queries=memory_queries,
            )
            source_changed = comparison.source_changed
    return CitationResult(
        citation=citation,
        source=sources.read(source=citation.source),
        comparison=comparison,
        source_changed=source_changed,
        needs_recheck=True if citation.jd_changed else source_changed,
    )


def compare_citation_source(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    citation_id: UUID,
    published_version: int,
    queries: JobDescriptionQueries,
    memory_queries: MemoryQueries,
) -> CitationSourceComparison:
    content = get_job_description(
        workspace_id=workspace_id,
        job_description_id=job_description_id,
        queries=queries,
    )
    citation = next(
        (item for item in content.citations if item.id == citation_id), None
    )
    if citation is None:
        raise CitationNotFoundError("引用不存在於此 JD")
    if not isinstance(citation.source, MemoryReference):
        raise InvalidCitationSourceError("訪談來源沒有發布版本差異")
    return compare_memory_citation(
        source=citation.source,
        published_version=published_version,
        queries=memory_queries,
    )
