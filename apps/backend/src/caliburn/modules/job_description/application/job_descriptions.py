"""JD 建立及基本資料修改；單次交易完成後交付完整內容與版本。"""

from collections.abc import Callable
from typing import Self
from uuid import UUID

from pydantic import ConfigDict, PositiveInt, model_validator, validate_call

from caliburn.modules.job_description.application.citation_inputs import (
    CitationChange,
    ConfirmCitationInput,
    EditingActor,
)
from caliburn.modules.job_description.application.citations import (
    apply_citation_changes,
)
from caliburn.modules.job_description.application.history_types import CorrelationId
from caliburn.modules.job_description.application.input_text import StorableText
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionRepository,
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.transaction_retry import (
    retry_transaction,
)
from caliburn.modules.job_description.application.writing import (
    save_and_commit,
)
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.shared.application.base_dto import BaseDTO


class UpdateJobDescriptionInput(BaseDTO):
    job_description_id: UUID
    expected_version: PositiveInt
    citations: tuple[CitationChange, ...] = ()
    correlation_id: CorrelationId | None = None
    job_title: StorableText | None = None
    organization_unit: StorableText | None = None
    reports_to: StorableText | None = None
    purpose: StorableText | None = None
    baseline_competency_level: int | None = None

    @model_validator(mode="after")
    def _require_patch(self) -> Self:
        if not self.model_fields_set.intersection(
            {
                "job_title",
                "organization_unit",
                "reports_to",
                "purpose",
                "baseline_competency_level",
                "citations",
            }
        ):
            raise ValueError("至少須提供一個可修改欄位")
        return self


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def create_job_description(
    *,
    workspace_id: UUID,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    correlation_id: CorrelationId | None = None,
) -> JobDescriptionResult:
    """建立空 JD；確認提交及正常退出後才交付保存結果。"""
    with uow_factory() as uow:
        result = initialize_job_description(
            workspace_id=workspace_id,
            repository=uow.job_descriptions,
            correlation_id=correlation_id,
        )
        uow.commit()
    return result


def initialize_job_description(
    *,
    workspace_id: UUID,
    repository: JobDescriptionRepository,
    correlation_id: CorrelationId | None = None,
) -> JobDescriptionResult:
    """在呼叫者既有交易新增空 JD 及首版快照；不提交或管理交易生命週期。"""
    job_description = JobDescription.create(workspace_id=workspace_id)
    version = repository.add(job_description, correlation_id=correlation_id)
    return JobDescriptionResult.from_job_description(job_description, version=version)


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def update_job_description(
    *,
    workspace_id: UUID,
    input: UpdateJobDescriptionInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """原版本有效才套用明示 patch；省略保留原值，None 清空可選欄位。"""
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        job_description = loaded.job_description
        loaded.require_version(expected_version=input.expected_version)
        current_level = job_description.baseline_competency_level
        job_description.update_details(
            job_title=input.job_title
            if "job_title" in input.model_fields_set
            else job_description.job_title,
            organization_unit=input.organization_unit
            if "organization_unit" in input.model_fields_set
            else job_description.organization_unit,
            reports_to=input.reports_to
            if "reports_to" in input.model_fields_set
            else job_description.reports_to,
            purpose=input.purpose
            if "purpose" in input.model_fields_set
            else job_description.purpose,
            baseline_competency_level=input.baseline_competency_level
            if "baseline_competency_level" in input.model_fields_set
            else (current_level.value if current_level is not None else None),
        )
        apply_citation_changes(
            job_description,
            target_kind="job_description",
            target_id=job_description.id,
            changes=input.citations,
            uow=uow,
        )
        result = save_and_commit(
            job_description,
            uow=uow,
            before=loaded.citation_support,
            actor=actor,
            correlation_id=input.correlation_id,
            confirmed_ids=frozenset(
                change.citation_id
                for change in input.citations
                if isinstance(change, ConfirmCitationInput)
            ),
        )
    return result
