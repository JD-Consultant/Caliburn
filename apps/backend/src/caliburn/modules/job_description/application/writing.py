"""用例共用的保存提交及領域錯誤轉譯。"""

from collections.abc import Iterator
from contextlib import contextmanager
from uuid import UUID

from caliburn.modules.job_description.application import errors
from caliburn.modules.job_description.application.citation_inputs import EditingActor
from caliburn.modules.job_description.application.history_types import RestoreMetadata
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.domain import errors as domain_errors
from caliburn.modules.job_description.domain.models.citation_review import (
    CitationSupport,
    apply_citation_review,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)


@contextmanager
def translate_domain_errors() -> Iterator[None]:
    """保留錯誤因果；內容規則仍由根裁決。"""
    try:
        yield
    except domain_errors.DuplicateNameError as error:
        raise errors.JobDescriptionNameConflictError(str(error)) from error
    except domain_errors.DutyNotFoundError as error:
        raise errors.DutyNotFoundError(str(error)) from error
    except domain_errors.TaskNotFoundError as error:
        raise errors.TaskNotFoundError(str(error)) from error
    except domain_errors.KnowledgeNotFoundError as error:
        raise errors.KnowledgeNotFoundError(str(error)) from error
    except domain_errors.SkillNotFoundError as error:
        raise errors.SkillNotFoundError(str(error)) from error
    except domain_errors.InvalidTaskReferenceError as error:
        raise errors.InvalidTaskReferenceError(str(error)) from error


def save_and_commit(
    job_description: JobDescription,
    *,
    uow: JobDescriptionUnitOfWork,
    correlation_id: str | None = None,
    restore: RestoreMetadata | None = None,
    before: CitationSupport | None = None,
    actor: EditingActor = "human",
    confirmed_ids: frozenset[UUID] = frozenset(),
) -> JobDescriptionResult:
    """由本次交易內容組完整結果，確認提交後才交付呼叫用例。"""
    if restore is not None:
        for citation in job_description.citations:
            # 舊引用可已撤回，但固定原件遺失或損毀不能當成可恢復內容。
            uow.citation_sources.read(source=citation.source)
    if before is not None and restore is None:
        apply_citation_review(
            job_description, before=before, actor=actor, confirmed_ids=confirmed_ids
        )
    version = uow.job_descriptions.save(
        job_description, correlation_id=correlation_id, restore=restore
    )
    result = JobDescriptionResult.from_job_description(job_description, version=version)
    uow.commit()
    return result
