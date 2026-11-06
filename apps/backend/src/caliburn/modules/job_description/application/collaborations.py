"""JD 協作追加、局部編修、排序與刪除的單次保存。"""

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
)
from caliburn.shared.application.base_dto import BaseDTO


class UpdateCollaborationInput(BaseDTO):
    job_description_id: UUID
    collaboration_id: UUID
    expected_version: PositiveInt
    citations: tuple[CitationChange, ...] = ()
    correlation_id: CorrelationId | None = None
    collaborator_name: StorableText | None = None
    scope: StorableText | None = None
    placement: PlacementInput | None = None

    @model_validator(mode="after")
    def _require_patch(self) -> Self:
        if not self.model_fields_set.intersection(
            {"collaborator_name", "scope", "placement", "citations"}
        ):
            raise ValueError("至少須提供一個可修改欄位")
        if (
            "collaborator_name" in self.model_fields_set
            and self.collaborator_name is None
        ):
            raise ValueError("協作對象不可清空")
        if "placement" in self.model_fields_set and self.placement is None:
            raise ValueError("排序意圖不可為 null")
        return self


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def update_collaboration(
    *,
    workspace_id: UUID,
    input: UpdateCollaborationInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        job_description = loaded.job_description
        collaboration = job_description.get_collaboration(
            collaboration_id=input.collaboration_id
        )
        loaded.require_version(expected_version=input.expected_version)
        job_description.update_collaboration(
            collaboration_id=collaboration.id,
            collaborator_name=input.collaborator_name
            if input.collaborator_name is not None
            else collaboration.collaborator_name,
            scope=input.scope
            if "scope" in input.model_fields_set
            else collaboration.scope,
        )
        if input.placement is not None:
            job_description.move_collaboration(
                collaboration_id=collaboration.id, before_id=input.placement.before_id
            )
        apply_citation_changes(
            job_description,
            target_kind="collaboration",
            target_id=input.collaboration_id,
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
def add_collaboration(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    expected_version: PositiveInt,
    collaborator_name: StorableText,
    scope: StorableText | None = None,
    correlation_id: CorrelationId | None = None,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
    citations: tuple[CitationChange, ...] = (),
) -> JobDescriptionResult:
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
        )
        job_description = loaded.job_description
        loaded.require_version(expected_version=expected_version)
        target_id = job_description.add_collaboration(
            collaborator_name=collaborator_name, scope=scope
        )
        apply_citation_changes(
            job_description,
            target_kind="collaboration",
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
def delete_collaboration(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    expected_version: PositiveInt,
    collaboration_id: UUID,
    correlation_id: CorrelationId | None = None,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
        )
        job_description = loaded.job_description
        job_description.get_collaboration(collaboration_id=collaboration_id)
        loaded.require_version(expected_version=expected_version)
        job_description.remove_collaboration(collaboration_id=collaboration_id)
        result = save_and_commit(
            job_description,
            uow=uow,
            before=loaded.citation_support,
            actor=actor,
            correlation_id=correlation_id,
        )
    return result
