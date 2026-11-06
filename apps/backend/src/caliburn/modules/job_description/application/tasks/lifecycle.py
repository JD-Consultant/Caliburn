"""Task 建立、局部編修與刪除；完整 JD 是唯一保存單位。"""

from collections.abc import Callable
from uuid import UUID

from pydantic import ConfigDict, PositiveInt, validate_call

from caliburn.modules.job_description.application.citation_inputs import (
    ConfirmCitationInput,
    EditingActor,
)
from caliburn.modules.job_description.application.citations import (
    apply_citation_changes,
)
from caliburn.modules.job_description.application.errors import (
    InvalidJobDescriptionInputError,
)
from caliburn.modules.job_description.application.history_types import CorrelationId
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    ExistingDefinitionInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.application.tasks.patching import (
    apply_task_changes,
)
from caliburn.modules.job_description.application.transaction_retry import (
    retry_transaction,
)
from caliburn.modules.job_description.application.writing import (
    save_and_commit,
    translate_domain_errors,
)


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def add_task(
    *,
    workspace_id: UUID,
    input: AddTaskInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """原 JD 版本有效後，原子加入 Task、自有記載及明示新建的 K/S。"""
    with uow_factory() as uow, translate_domain_errors():
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        job_description = loaded.job_description
        loaded.require_version(expected_version=input.expected_version)
        target_id = job_description.add_task(
            name=input.name,
            description=input.description,
            duty_id=input.duty_id,
            competency_level=input.competency_level,
            outcomes=input.outcomes,
            requirements=input.requirements,
            knowledge=tuple(
                entry.id
                if isinstance(entry, ExistingDefinitionInput)
                else (entry.name, entry.description)
                for entry in input.knowledge
            ),
            skills=tuple(
                entry.id
                if isinstance(entry, ExistingDefinitionInput)
                else (entry.name, entry.description)
                for entry in input.skills
            ),
        )
        apply_citation_changes(
            job_description,
            target_kind="task",
            target_id=target_id,
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
def update_task(
    *,
    workspace_id: UUID,
    input: UpdateTaskInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """先核任務身分與 JD 版本；省略欄位保留，None 清空可選欄位。"""
    with uow_factory() as uow, translate_domain_errors():
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        job_description = loaded.job_description
        task = job_description.get_task(task_id=input.task_id)
        loaded.require_version(expected_version=input.expected_version)
        input.validate_changes()
        if input.duty_scopes:
            if (
                input.placement is None
                or input.placement.destination_duty_id == task.duty_id
            ):
                raise InvalidJobDescriptionInputError(
                    "職責範圍伴隨修改只適用實際跨職責移動"
                )
            allowed_duties = {task.duty_id, input.placement.destination_duty_id} - {
                None
            }
            if any(
                change.duty_id not in allowed_duties for change in input.duty_scopes
            ):
                raise InvalidJobDescriptionInputError("只能修改移動來源或目的職責範圍")
            for change in input.duty_scopes:
                duty = job_description.get_duty(duty_id=change.duty_id)
                job_description.update_duty(
                    duty_id=duty.id, name=duty.name.value, scope=change.scope
                )
        current_level = task.competency_level
        job_description.update_task(
            task_id=task.id,
            name=input.name if input.name is not None else task.name.value,
            description=input.description
            if "description" in input.model_fields_set
            else task.description,
            competency_level=input.competency_level
            if "competency_level" in input.model_fields_set
            else (current_level.value if current_level is not None else None),
        )
        if input.placement is not None:
            job_description.move_task(
                task_id=task.id,
                destination_duty_id=input.placement.destination_duty_id,
                before_id=input.placement.before_id,
            )
        apply_task_changes(job_description, task_id=task.id, changes=input.changes)
        apply_citation_changes(
            job_description,
            target_kind="task",
            target_id=input.task_id,
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
def delete_task(
    *,
    workspace_id: UUID,
    job_description_id: UUID,
    task_id: UUID,
    expected_version: PositiveInt,
    correlation_id: CorrelationId | None = None,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
    actor: EditingActor = "human",
) -> JobDescriptionResult:
    """刪除任務及自有記載；共享 K/S 保留於 JD。"""
    with uow_factory() as uow, translate_domain_errors():
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=job_description_id,
        )
        job_description = loaded.job_description
        job_description.get_task(task_id=task_id)
        loaded.require_version(expected_version=expected_version)
        job_description.remove_task(task_id=task_id)
        result = save_and_commit(
            job_description,
            uow=uow,
            before=loaded.citation_support,
            actor=actor,
            correlation_id=correlation_id,
        )
    return result
