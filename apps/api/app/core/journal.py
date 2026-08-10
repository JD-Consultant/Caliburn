"""Shared conversation and OPKS-scheduling value types.

`TurnSpeaker`、`ConversationTurn`、`ActiveQuestion` 是主顧問對話的最小共同語言：
`task_analysis`（context packet）、`consultation`（durable turn）與 postgres adapter
都要用同一份定義，才能在同一份 conversation transcript 上達成共識。

`ScheduledOpks` 是主回合 receipt 凍結的唯一 OPKS child（ADR 0054 決定 7–8），
`task_analysis`（scheduler）與 `opks`（generation）共同消費同一個定義。
"""

from __future__ import annotations

from enum import StrEnum

from app.core.domain import DomainModel, Identifier, NonEmptyText, TaskId


class TurnSpeaker(StrEnum):
    EMPLOYEE = "employee"
    CONSULTANT = "consultant"


class ConversationTurn(DomainModel):
    turn_id: Identifier
    speaker: TurnSpeaker
    text: NonEmptyText


class ActiveQuestion(DomainModel):
    """產生 `support_links.question_turn_id` 的來源(§11.4);缺它短答無法解讀。"""

    turn_id: Identifier
    text: NonEmptyText


class ScheduledOpks(DomainModel):
    """主回合 receipt 凍結的唯一 child(決定 7–8)。

    child operation ID 由這兩個值推導,**不重複持久化**——多存一份 ID 就多一個
    會與推導結果不一致的真相。
    """

    task_id: TaskId
    analysis_input_digest: NonEmptyText
