"""Plan 窗口測例核對本輪訪談材料，保留完整歷史前綴的獨立斷言。"""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import Engine

from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def assert_turn_input(
    items: list[dict[str, Any]],
    *,
    engine: Engine,
    workspace_id: UUID,
    turn_id: UUID,
    text: str,
    memory_projected: bool = True,
) -> None:
    """原文及 metadata 必須完整且唯一；短碼沿公開映射核回正式 UUID。"""
    assert len(items) == (2 if memory_projected else 3)
    assert all(set(item) == {"role", "content"} for item in items)
    assert all(item["role"] == "user" for item in items)
    if not memory_projected:
        assert items[0] == {"role": "user", "content": text}
        items = items[1:]
    original = json.loads(items[0]["content"])
    navigation = json.loads(items[1]["content"])
    reference = original["ref"]
    assert original == (
        {"data_kind": "employee_input", "ref": reference, "text": text}
        if memory_projected
        else {"data_kind": "employee_input_reference", "ref": reference}
    )
    assert set(navigation) == {"data_kind", "first_ref", "last_ref", "scope"}
    assert navigation["data_kind"] == "interview_navigation"
    assert navigation["last_ref"] == reference
    assert isinstance(navigation["scope"], str) and navigation["scope"]

    messages = SqlAlchemyInterviewQueries(engine).list_messages(
        workspace_id=workspace_id
    )
    (employee,) = [
        message
        for message in messages
        if message.turn_id == turn_id
        and message.speaker == "employee"
        and message.kind == "text"
    ]
    assert employee.text == text
    references = SqlAlchemyModelReferences(create_session_factory(engine))
    resolved = references.resolve_refs(
        workspace_id, [navigation["first_ref"], reference]
    )
    assert resolved[navigation["first_ref"]] == ReferenceTarget(
        "message", messages[0].message_id
    )
    assert resolved[reference] == ReferenceTarget("message", employee.message_id)
