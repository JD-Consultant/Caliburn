"""Memory 的模型來源只改明定引用欄位，正文與發布身分保持原樣。"""

import json
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

import pytest

from caliburn.bundles.memory.projections import (
    ToolRejection,
    handoff_changes,
    historical_interview,
    item_view,
    map_items,
)
from caliburn.modules.memory.application.results import MemoryInterviewMessage
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.work_memory import WorkMemory


def test_situation_sources_use_persistent_refs_without_rewriting_content() -> None:
    root = WorkMemory.create(workspace_id=uuid4())
    item_id = root.create_situation(
        content=MemoryContent(
            title="盤點 message_73",
            description="依原記錄第 2 則核對",
            body="保留 message_73、I42.3 與訪談序號 2 原文。",
        ),
        interview_message_ids=(UUID(int=1), UUID(int=2)),
    )
    item = root.get_situation(item_id=item_id)

    result = item_view(
        item, root.items, {UUID(int=1): "message_93", UUID(int=2): "message_8"}
    )

    assert result == {
        "title": "盤點 message_73",
        "description": "依原記錄第 2 則核對",
        "body": "保留 message_73、I42.3 與訪談序號 2 原文。",
        "interview_references": ["message_93", "message_8"],
    }
    assert map_items(root.items, "situation") == {
        "items": [
            {"target_title": "盤點 message_73", "description": "依原記錄第 2 則核對"}
        ]
    }


def test_handoff_diff_reports_actual_source_change_using_persistent_refs() -> None:
    root = WorkMemory.create(workspace_id=uuid4())
    content = MemoryContent(
        title="盤點", description="本人核對", body="原文 message_6 不變。"
    )
    item_id = root.create_situation(
        content=content, interview_message_ids=(UUID(int=1),)
    )
    root.create_understanding(
        content=MemoryContent(title="盤點責任", description="核對", body="本人處理"),
        situation_ids=(item_id,),
    )
    baseline = root.publish(
        covered_through_message_id=UUID(int=1), published_at=datetime.now(UTC)
    )
    root.revise_situation(
        item_id=item_id, content=content, interview_message_ids=(UUID(int=2),)
    )

    changes = handoff_changes(
        baseline, root, {UUID(int=1): "message_93", UUID(int=2): "message_8"}
    )

    assert len(changes) == 1
    assert changes[0]["target_title"] == "盤點"
    assert changes[0]["affected_understanding_titles"] == ["盤點責任"]
    assert "-訪談引用：message_93" in str(changes[0]["diff"])
    assert "+訪談引用：message_8" in str(changes[0]["diff"])
    assert "原文 message_6 不變。" in str(changes[0]["diff"])


def test_required_answer_keeps_question_and_owner_order_in_shared_projection() -> None:
    turn_id = uuid4()
    question = MemoryInterviewMessage(
        UUID(int=2), turn_id, "consultant", "question", "原題 message_42？", None
    )
    answer = MemoryInterviewMessage(
        UUID(int=1), turn_id, "employee", "answer", "略過", question.message_id
    )

    projected = historical_interview(
        (answer.message_id, answer.message_id),
        messages=(question, answer),
        refs={question.message_id: "message_93", answer.message_id: "message_8"},
    )

    assert len(projected) == 1
    assert cast(dict[str, Any], projected[0])["role"] == "user"
    material = json.loads(cast(dict[str, Any], projected[0])["content"])
    assert material == {
        "source": "interview",
        "messages": [
            {
                "ref": "message_93",
                "speaker": "consultant",
                "kind": "question",
                "text": "原題 message_42？",
                "reply_to": None,
                "supporting_question": True,
            },
            {
                "ref": "message_8",
                "speaker": "employee",
                "kind": "answer",
                "text": "略過",
                "reply_to": "message_93",
                "supporting_question": False,
            },
        ],
    }


def test_required_answer_with_missing_question_rejects_incomplete_context() -> None:
    answer = MemoryInterviewMessage(
        UUID(int=1), uuid4(), "employee", "answer", "略過", UUID(int=2)
    )

    with pytest.raises(ToolRejection) as rejected:
        historical_interview(
            (answer.message_id,),
            messages=(answer,),
            refs={answer.message_id: "message_8", UUID(int=2): "message_93"},
        )

    assert rejected.value.code == "source_not_available"
