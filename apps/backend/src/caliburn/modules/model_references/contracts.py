"""Bundle 共用的批次定位契約；UUID 與業務資格仍由來源 owner 管理。"""

from collections.abc import Collection
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

type ResourceKind = Literal[
    "message",
    "duty",
    "task",
    "outcome",
    "requirement",
    "knowledge",
    "skill",
    "collaboration",
    "condition",
    "occupation",
    "citation",
]


@dataclass(frozen=True, slots=True)
class ReferenceTarget:
    resource_kind: ResourceKind
    resource_id: UUID


class ModelReferenceError(ValueError):
    """模型定位拒絕；由 Bundle 轉成工具可修正的錯誤。"""

    def __init__(self, reference: str, message: str) -> None:
        self.reference = reference
        super().__init__(message)


class InvalidModelReferenceError(ModelReferenceError):
    """格式／種類／數字不合法；完整 UUID 亦不接受。"""


class UnknownModelReferenceError(ModelReferenceError):
    """此 Workspace 沒有符合完整短碼的映射。"""


class ModelReferenceAllocationError(RuntimeError):
    """並行刪除導致配置結果不完整；不回傳部分短碼或自動重試。"""


class ModelReferences(Protocol):
    """同步短交易；每次使用可信 runtime 的 Workspace，空批次回 {}。"""

    def get_or_create_refs(
        self, workspace_id: UUID, targets: Collection[ReferenceTarget]
    ) -> dict[ReferenceTarget, str]:
        """批次配置，重複目標折疊；映射提交完成才回傳。"""
        ...

    def resolve_refs(
        self, workspace_id: UUID, refs: Collection[str]
    ) -> dict[str, ReferenceTarget]:
        """批次全成或拒絕；呼叫者再核種類、存在性與來源資格。"""
        ...
