"""把訊息 UUID 批次交給共用持久 mapping；不保存第二套 alias。"""

from collections.abc import Collection
from uuid import UUID

from caliburn.modules.model_references import ModelReferences, ReferenceTarget


def message_refs(
    *,
    workspace_id: UUID,
    message_ids: Collection[UUID],
    references: ModelReferences,
) -> dict[UUID, str]:
    """僅轉明定身分欄位；同步短交易提交後才交付模型 ref。"""
    targets = tuple(
        ReferenceTarget("message", message_id) for message_id in message_ids
    )
    return {
        target.resource_id: ref
        for target, ref in references.get_or_create_refs(workspace_id, targets).items()
    }
