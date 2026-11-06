"""JD 條件追加、編修、分類更正、排序及刪除的單次保存。"""

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
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.shared.application.base_dto import BaseDTO


class UpdateConditionInput(BaseDTO):
    job_description_id: UUID
    condition_id: UUID
    expected_version: PositiveInt
    citations: tuple[CitationChange, ...] = ()
    correlation_id: CorrelationId | None = None
    text: StorableText | None = None
    kind: ConditionKind | None = None
    placement: PlacementInput | None = None

    @model_validator(mode="after")
    def _require_patch(self) -> Self:
        fields = self.model_fields_set.intersection(
            {"text", "kind", "placement", "citations"}
        )
        if not fields:
            raise ValueError("至少須提供一個可修改欄位")
        if any(getattr(self, field) is None for field in fields):
            raise ValueError("條件欄位不可清空")
        return self


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def add_condition(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    expected_version: PositiveInt,
    kind: ConditionKind,
    text: StorableText,
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
        target_id = job_description.add_condition(kind=kind, text=text)
        apply_citation_changes(
            job_description,
            target_kind="condition",
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
def update_condition(
    *,
    workspace_id: UUID,
    input: UpdateConditionInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """內容、分類與新分類內的位置共同保存；分類及錨點規則由根維護。"""
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        job_description = loaded.job_description
        condition = job_description.get_condition(condition_id=input.condition_id)
        loaded.require_version(expected_version=input.expected_version)
        if input.text is not None:
            job_description.update_condition(condition_id=condition.id, text=input.text)
        if input.kind is not None:
            job_description.reclassify_condition(
                condition_id=condition.id, kind=input.kind
            )
        if input.placement is not None:
            job_description.move_condition(
                condition_id=condition.id, before_id=input.placement.before_id
            )
        apply_citation_changes(
            job_description,
            target_kind="condition",
            target_id=input.condition_id,
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
def delete_condition(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    expected_version: PositiveInt,
    condition_id: UUID,
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
        job_description.get_condition(condition_id=condition_id)
        loaded.require_version(expected_version=expected_version)
        job_description.remove_condition(condition_id=condition_id)
        result = save_and_commit(
            job_description,
            uow=uow,
            before=loaded.citation_support,
            actor=actor,
            correlation_id=correlation_id,
        )
    return result
