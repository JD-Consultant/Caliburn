"""Internal Python persistence body, separate from issued-reference API results.

The SQL row owns operation/document/base/result identity. This versioned body owns
the original fixed error/action semantics. It is never exposed as a Web/tool DTO.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from jd_relational.result_transport import validate_result


CommandKind = Literal["jd_create_task", "jd_revise_work", "jd_set_text", "jd_insert_item",
                      "jd_delete_item", "jd_move_item", "jd_set_task_capability",
                      "jd_replace_selection",
                      # Manual-only; the model is never given these.
                      "restore_revision", "undo_ai_turn"]
FailureCode = Literal["invalid_input", "target_missing", "stale_view", "relationship_conflict",
                      "dependent_items", "save_failed"]


class ReceiptError(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    code: FailureCode
    message: str = Field(min_length=1, max_length=2048)


class ReceiptReinstatement(BaseModel):
    """Which saved revision an undo or restore actually put back, and whose turn.

    The employee's request carries a run or a target, but the request itself is
    not kept -- only its digest is. Without this, history can say a manual
    revision happened but not that it took back a particular AI turn, or where
    that turn began. It records what the server proved, never what was asked.
    """
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    reinstated_revision_id: str = Field(min_length=36, max_length=36)
    undone_ai_run_id: str | None = None


class ReceiptBody(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
    # Version 1 rows predate reinstatement provenance and simply have none;
    # they stay readable exactly as written.
    format_version: Literal[1, 2]
    command_kind: CommandKind
    error: ReceiptError | None
    next_action: Literal["continue", "correct_arguments", "reread_current", "resolve_dependencies", "stop"]
    reinstated: ReceiptReinstatement | None = None

    @model_validator(mode="after")
    def version_owns_its_shape(self):
        # A version 1 row was written before reinstatement existed, so one
        # appearing there is a rewritten row, not a readable older receipt.
        if self.format_version == 1 and self.reinstated is not None:
            raise ValueError("invalid_receipt_version")
        return self


ERRORS = {
    "invalid_input": ("本次內容不符合編輯規則；請依工具說明修正。", "correct_arguments"),
    "target_missing": ("編輯目標已不存在；請重新讀取目前 JD。", "reread_current"),
    "stale_view": ("JD 已有較新版本；本次內容未套用，請重新讀取。", "reread_current"),
    "relationship_conflict": ("任務或引用關係不符；請讀取相關內容後修正。", "correct_arguments"),
    "dependent_items": ("此項目仍被引用；請確認受影響的工作後處理關係。", "resolve_dependencies"),
    "save_failed": ("本次修改未保存；請保留輸入並停止寫入。", "stop"),
}


def body_for(command_kind: str, status: str, reinstated: dict | None = None) -> ReceiptBody:
    if status not in {*ERRORS, "committed", "no_change"}:
        raise ValueError("invalid_terminal_status")
    message, action = ERRORS[status] if status in ERRORS else (None, "continue")
    if reinstated is not None and (message or command_kind not in {"restore_revision", "undo_ai_turn"}):
        # Only a command that really put a saved revision back may claim one,
        # and only when it succeeded.
        raise ValueError("invalid_reinstatement")
    return ReceiptBody(format_version=2, command_kind=command_kind,
                       error=ReceiptError(code=status, message=message) if message else None,
                       next_action=action,
                       reinstated=ReceiptReinstatement(**reinstated) if reinstated else None)


@dataclass(frozen=True)
class SavedOperation:
    document_id: str
    operation_id: UUID
    request_digest: str
    origin: str
    ai_run_id: str | None
    base_revision_id: UUID | None
    result_revision_id: UUID | None
    status: str
    body: ReceiptBody
    created_at: datetime

    @classmethod
    def from_row(cls, row) -> "SavedOperation":
        body = ReceiptBody.model_validate(row["receipt"], strict=True)
        # Validate result consistency with the shared contract; these IDs are
        # local validation placeholders, never issued refs or API output.
        validate_result({"status": row["status"],
            "effect": "changed" if row["status"] == "committed" else "unchanged",
            "receipt_durability": "confirmed", "operation_ref": str(row["operation_id"]),
            "result_revision_ref": str(row["result_revision_id"]) if row["result_revision_id"] else None,
            "change_ref": str(row["operation_id"]) if row["status"] == "committed" else None,
            "error": {**body.error.model_dump(), "related_refs": []} if body.error else None,
            "next_action": body.next_action})
        return cls(**{name: row[name] for name in cls.__dataclass_fields__ if name != "body"}, body=body)


@dataclass(frozen=True)
class WriteObservation:
    """Only receipt!=None establishes a confirmed terminal observation."""
    document_id: str
    operation_id: UUID
    receipt: SavedOperation | None
    unresolved_effect: Literal["unchanged", "unknown"] | None = None

    def __post_init__(self):
        if self.unresolved_effect not in {None, "unchanged", "unknown"}:
            raise ValueError("invalid_observation")
        if (self.receipt is None) != (self.unresolved_effect is not None):
            raise ValueError("invalid_observation")
        if self.receipt and (self.document_id != self.receipt.document_id or self.operation_id != self.receipt.operation_id):
            raise ValueError("invalid_observation_scope")

    @property
    def confirmed(self) -> bool:
        return self.receipt is not None

    @property
    def status(self) -> str:
        return self.receipt.status if self.receipt else "outcome_unknown" if self.unresolved_effect == "unknown" else "save_failed"

    @property
    def next_action(self) -> str:
        return self.receipt.body.next_action if self.receipt else "reconcile_operation"
