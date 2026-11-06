"""查讀及寫入結果，保留原話及業務版號。"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from caliburn.modules.memory.domain.snapshot import MemorySnapshot


@dataclass(frozen=True, slots=True)
class MemoryUpdateResult:
    version: int
    changed: bool
    item_id: UUID | None = None
    snapshot: MemorySnapshot | None = None


@dataclass(frozen=True, slots=True)
class MemoryInterviewMessage:
    message_id: UUID
    turn_id: UUID
    speaker: Literal["app", "employee", "consultant"]
    kind: Literal["text", "question", "answer"]
    text: str
    reply_to_message_id: UUID | None
