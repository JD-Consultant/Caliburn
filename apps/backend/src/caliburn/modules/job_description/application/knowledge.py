"""知識建立、局部編修、相對排序與刪除；全部透過 JD 根保存。"""

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
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.placement import PlacementInput
from caliburn.modules.job_description.application.transaction_retry import (
    retry_transaction,
)
from caliburn.modules.job_description.application.writing import (
    save_and_commit,
    translate_domain_errors,
)
from caliburn.shared.application.base_dto import BaseDTO


class UpdateKnowledgeInput(BaseDTO):
    job_description_id: UUID
    knowledge_id: UUID
    expected_version: PositiveInt
    citations: tuple[CitationChange, ...] = ()
    correlation_id: CorrelationId | None = None
    name: StorableText | None = None
    description: StorableText | None = None
    placement: PlacementInput | None = None

    @model_validator(mode="after")
    def _require_patch(self) -> Self:
        if not self.model_fields_set.intersection(
            {"name", "description", "placement", "citations"}
        ):
            raise ValueError("至少須提供一個可修改欄位")
        if "name" in self.model_fields_set and self.name is None:
            raise ValueError("知識名稱不可清空")
        if "placement" in self.model_fields_set and self.placement is None:
            raise ValueError("排序意圖不可為 null")
        return self


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def add_knowledge(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    expected_version: PositiveInt,
    name: StorableText,
    description: StorableText | None = None,
    correlation_id: CorrelationId | None = None,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
    citations: tuple[CitationChange, ...] = (),
) -> JobDescriptionResult:
    """原 JD 版本有效才新增；回傳完整 JD 及本次版本。"""
    with uow_factory() as uow, translate_domain_errors():
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
        )
        job_description = loaded.job_description
        loaded.require_version(expected_version=expected_version)
        target_id = job_description.add_knowledge(
            name=name,
            description=description,
        )
        apply_citation_changes(
            job_description,
            target_kind="knowledge",
            target_id=target_id,
            changes=citations,
            uow=uow,
        )
        result = save_and_commit(
            job_description,
            uow=uow,
            before=loaded.citation_support,
            actor=actor,
            correlation_id=correlation_id,
            confirmed_ids=frozenset(
                change.citation_id
                for change in citations
                if isinstance(change, ConfirmCitationInput)
            ),
        )
    return result


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def update_knowledge(
    *,
    workspace_id: UUID,
    input: UpdateKnowledgeInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """先確認目標身分與版本，再由根驗證名稱與局部修改。"""
    with uow_factory() as uow, translate_domain_errors():
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        job_description = loaded.job_description
        knowledge = job_description.get_knowledge(knowledge_id=input.knowledge_id)
        loaded.require_version(expected_version=input.expected_version)
        job_description.update_knowledge(
            knowledge_id=knowledge.id,
            name=input.name if input.name is not None else knowledge.name.value,
            description=input.description
            if "description" in input.model_fields_set
            else knowledge.description,
        )
        if input.placement is not None:
            job_description.move_knowledge(
                knowledge_id=knowledge.id, before_id=input.placement.before_id
            )
        apply_citation_changes(
            job_description,
            target_kind="knowledge",
            target_id=input.knowledge_id,
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


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def delete_knowledge(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    knowledge_id: UUID,
    expected_version: PositiveInt,
    correlation_id: CorrelationId | None = None,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """由根維護刪除後的分類或引用；完整結果只在提交成功後交付。"""
    with uow_factory() as uow, translate_domain_errors():
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
        )
        job_description = loaded.job_description
        job_description.get_knowledge(knowledge_id=knowledge_id)
        loaded.require_version(expected_version=expected_version)
        job_description.remove_knowledge(knowledge_id=knowledge_id)
        result = save_and_commit(
            job_description,
            uow=uow,
            before=loaded.citation_support,
            actor=actor,
            correlation_id=correlation_id,
        )
    return result
