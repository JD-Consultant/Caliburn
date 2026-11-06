"""依固定輪前版本及持久來源恢復本輪內容；已回退可安全重入。"""

from collections.abc import Callable
from uuid import UUID

from pydantic import ConfigDict, PositiveInt, validate_call

from caliburn.modules.job_description.application.errors import (
    JobDescriptionConcurrencyError,
    JobDescriptionHistoryDataError,
)
from caliburn.modules.job_description.application.history_types import (
    CorrelationId,
    RestoreMetadata,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.persistence import (
    JobDescriptionHistoryReader,
    JobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.application.transaction_retry import (
    retry_transaction,
)
from caliburn.modules.job_description.application.writing import save_and_commit
from caliburn.shared.application.base_dto import BaseDTO


class RestoreTurnChangesInput(BaseDTO):
    job_description_id: UUID
    base_version: PositiveInt
    correlation_id: CorrelationId
    completed_version: PositiveInt | None = None


@validate_call(config=ConfigDict(strict=True))
@retry_transaction
def restore_turn_changes(
    *,
    workspace_id: UUID,
    input: RestoreTurnChangesInput,
    uow_factory: Callable[[], JobDescriptionUnitOfWork],
) -> JobDescriptionResult:
    """鎖根後核對本輪完整版本區段，恢復內容及標記共同提交。

    呼叫端先封鎖並等待本輪在途寫入，提供固定輪前版本及唯一 Turn 來源。
    已回退或本輪沒有寫入時不增版；其他來源的後續／交錯修改明確拒絕。
    不以工具回覆中的最後版本判斷寫入完成，涵蓋提交後尚未保存回覆的取消。
    完成輪可提供固定 completed_version 上界，禁止連同其後同來源寫入撤回。
    """
    with uow_factory() as uow:
        loaded = uow.job_descriptions.get_for_update(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
        )
        baseline = uow.history.get(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
            version=input.base_version,
        )
        writes = uow.history.list(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
            correlation_id=input.correlation_id,
            page_size=1,
        ).items
        reversals = uow.history.list(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
            reverts_correlation_id=input.correlation_id,
            page_size=1,
        ).items
        latest_write = writes[0] if writes else None
        if reversals:
            reversal = reversals[0]
            if reversal.restored_from_version != input.base_version or (
                latest_write is not None and latest_write.version > reversal.version
            ):
                raise JobDescriptionConcurrencyError(
                    "本輪恢復基準或後續寫入不符，未修改"
                )
            return JobDescriptionResult.from_job_description(
                loaded.job_description, version=loaded.version
            )
        if latest_write is None or latest_write.version <= input.base_version:
            return JobDescriptionResult.from_job_description(
                loaded.job_description, version=loaded.version
            )
        if (
            input.completed_version is not None
            and latest_write.version > input.completed_version
        ):
            raise JobDescriptionConcurrencyError("本輪保存超過固定完成版本，未恢復")
        loaded.require_version(expected_version=latest_write.version)
        _require_only_turn_changes(
            history=uow.history,
            workspace_id=workspace_id,
            input=input,
            current_version=loaded.version,
        )
        return save_and_commit(
            baseline.job_description,
            uow=uow,
            restore=RestoreMetadata(
                target_version=input.base_version,
                reverts_correlation_id=input.correlation_id,
            ),
        )


def _require_only_turn_changes(
    *,
    history: JobDescriptionHistoryReader,
    workspace_id: UUID,
    input: RestoreTurnChangesInput,
    current_version: int,
) -> None:
    """逐頁驗證輪前至目前的連續版本，不能只檢查最後一筆來源。"""
    expected_version = current_version
    page_token = None
    while expected_version > input.base_version:
        page = history.list(
            workspace_id=workspace_id,
            job_description_id=input.job_description_id,
            page_size=100,
            page_token=page_token,
        )
        for entry in page.items:
            if entry.version != expected_version:
                raise JobDescriptionHistoryDataError("取消所需的 JD 歷史版本不連續")
            if entry.correlation_id != input.correlation_id or entry.kind != "edited":
                raise JobDescriptionConcurrencyError("輪前版本之後包含其他修改，未恢復")
            expected_version -= 1
            if expected_version == input.base_version:
                return
        if page.next_page_token is None:
            raise JobDescriptionHistoryDataError("取消所需的 JD 歷史版本不完整")
        page_token = page.next_page_token
