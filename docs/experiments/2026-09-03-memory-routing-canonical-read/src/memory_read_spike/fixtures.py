"""Frozen synthetic conversation and focused Memory fixtures."""

from __future__ import annotations

import json
from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from pydantic import BaseModel, ConfigDict

from memory_read_spike.scope import TrustedReadScope, issue_message_ref


class SemanticMemoryFixture(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_id: str
    title: str
    content: str
    message_refs: tuple[str, ...]


def load_canonical_rounds() -> tuple[tuple[HumanMessage, AIMessage], ...]:
    fixture_path = (
        Path(__file__).resolve().parents[2]
        / "cases"
        / "long-thread-routing-v1.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    return tuple(
        (
            HumanMessage(id=item["human_id"], content=item["human"]),
            AIMessage(id=item["assistant_id"], content=item["assistant"]),
        )
        for item in payload["rounds"]
    )


def semantic_memory_fixtures(
    scope: TrustedReadScope,
) -> tuple[SemanticMemoryFixture, ...]:
    ref = lambda message_id: issue_message_ref(scope, message_id)
    return (
        SemanticMemoryFixture(
            memory_id="memory-a",
            title="A 案：餐飲預約網站",
            content=(
                "餐飲預約網站服務三間分店；預約表單以常見過敏原選項加其他補充"
                "記錄過敏資訊。驗收包含行動版 Safari 與尖峰時段重複訂位檢查。"
            ),
            message_refs=(ref("h-002"), ref("h-003"), ref("h-004"), ref("h-005")),
        ),
        SemanticMemoryFixture(
            memory_id="memory-b",
            title="B 案：健身房會員網站",
            content=(
                "單一場館的健身房會員網站；目前有效資料來源是櫃台每日匯出的 CSV。"
                "驗收包含大量會員名單匯入與重複會員編號提示。"
            ),
            message_refs=(ref("h-009"), ref("h-010"), ref("h-012"), ref("h-013"), ref("h-014")),
        ),
        SemanticMemoryFixture(
            memory_id="memory-common",
            title="共同穩定工作模式",
            content=(
                "不同網站案件都會進行需求訪談、前端實作、資料串接、測試與客戶"
                "驗收，並先做可操作版本再逐步調整。"
            ),
            message_refs=(ref("h-017"), ref("h-018"), ref("h-034")),
        ),
    )
