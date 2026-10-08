"""In-memory official-HTTP seam: no database, key, sockets or provider."""

import copy
import sys
from pathlib import Path
from uuid import uuid4

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from controls import BatchGuard
from events import manual_command, manual_pending
from journey import journey
from materials import CUES, MANUAL_TEXT, Employee


class Response:
    def __init__(self, value):
        self.value = value

    def raise_for_status(self):
        pass

    def json(self):
        return copy.deepcopy(self.value)


class Product:
    def __init__(self, questions):
        self.questions = questions
        self.messages = []
        self.inputs = []
        self.file_id = str(uuid4())
        self.revision = str(uuid4())

    async def post(self, path, json):
        if path == "/api/job-files":
            return Response({"job_file_id": self.file_id})
        self.inputs.append(json)
        source = str(uuid4())
        self.messages.append(
            {
                "speaker": "employee",
                "interview_text": json["text"],
                "source_id": source,
                "interview_sequence": len(self.messages) + 1,
            }
        )
        index = len(self.inputs) - 1
        self.messages.append(
            {
                "speaker": "consultant",
                "interview_text": self.questions[min(index, len(self.questions) - 1)],
                "source_id": str(uuid4()),
                "interview_sequence": len(self.messages) + 1,
            }
        )
        return Response(
            {
                "command_id": json["command_id"],
                "source_id": source,
                "execution_id": str(uuid4()),
            }
        )

    async def get(self, path):
        if "/consultant-turns/" in path:
            return Response({"status": "completed"})
        if path.endswith("/interviews"):
            return Response({"messages": self.messages})
        if path.endswith("/interview-plan"):
            return Response({"plan": None})
        if path.endswith("/jd/sources"):
            return Response({"revision_id": self.revision, "references": []})
        return Response({"revision_id": self.revision, "tasks": []})


def review_answer(pending, *ids, mode="answer"):
    return {
        "question_id": pending["question_id"],
        "fact_ids": list(ids),
        "mode": mode,
        "reason": "匿名逐題相關性裁決",
        "subquestions": [
            {
                "quote": pending["actual_question"],
                "mode": mode,
                "fact_ids": list(ids),
                "reason": "當下實際問題",
            }
        ],
    }


@pytest.mark.asyncio
async def test_selected_cue_becomes_visible_only_on_formal_source(tmp_path):
    product = Product(["盤點如何？", "帶教如何？", "盤點誰批准調帳？", "還有嗎？"])
    choices = iter([("inventory-partial",), ("training",), ("inventory-authority",)])

    async def review(pending):
        assert not {"group", "arm", "plan", "cost"} & pending.keys()
        return review_answer(pending, *next(choices))

    result = await journey(
        product, tmp_path, Employee("warehouse"), 5, BatchGuard(), review=review
    )
    assert result["closure_submitted"]
    cue = CUES["warehouse"]["text"]
    assert sum(cue in item["text"] for item in product.inputs) == 1
    import json

    state = json.loads(
        (tmp_path / "conditional-audit.json").read_text(encoding="utf-8")
    )
    assert "inventory-authority" in state["disclosed"]
    assert all(
        item["formally_visible"]
        and item["accepted_source_id"] == item["formal_source_ids"][0]
        for item in state["audit"]
    )


@pytest.mark.asyncio
async def test_closure_does_not_release_unused_cue_or_last_answer(tmp_path):
    product = Product(["盤點如何？", "帶教如何？"])
    seen = []

    async def review(pending):
        seen.append(pending)
        return review_answer(pending, "inventory-partial")

    await journey(
        product, tmp_path, Employee("warehouse"), 3, BatchGuard(), review=review
    )
    assert len(seen) == 1
    assert all(CUES["warehouse"]["text"] not in item["text"] for item in product.inputs)


@pytest.mark.asyncio
async def test_no_question_reminder_cannot_repeat_contiguously(tmp_path):
    product = Product(["目前整理完了。"])

    async def review(pending):
        return review_answer(pending, mode="no_question")

    result = await journey(
        product, tmp_path, Employee("warehouse"), 8, BatchGuard(), review=review
    )
    assert len(product.inputs) == 3
    assert result["driver_reminders"] == 1
    assert result["stop"] == "closure_after_missing_active_progress"


def test_manual_noop_and_public_revision_command():
    task = str(uuid4())
    pending = manual_pending(
        "warehouse", {"revision_id": str(uuid4()), "tasks": [{"task_id": task}]}, "q"
    )
    assert not {"arm", "plan", "private_facts", "profile"} & pending.keys()
    assert (
        manual_command(
            pending, {"question_id": "q", "action": "no_op", "reason": "公開語意已等價"}
        )
        is None
    )
    command = manual_command(
        pending,
        {
            "question_id": "q",
            "action": "revise_task",
            "task_id": task,
            "description": MANUAL_TEXT["warehouse"] + "。保留收貨異常表。",
            "reason": "局部修訂公開初始分工",
        },
    )
    assert command["expected_revision_id"] == pending["current_jd"]["revision_id"]
    assert command["change"]["changes"][0]["field"] == "description"


def test_manual_create_preserves_no_invented_area_identity():
    pending = manual_pending(
        "course_admin", {"revision_id": str(uuid4()), "tasks": []}, "q"
    )
    command = manual_command(
        pending,
        {
            "question_id": "q",
            "action": "create_task",
            "title": "臨時缺課處理",
            "description": MANUAL_TEXT["course_admin"],
            "reason": "沒有相應task",
        },
    )
    assert command["change"]["area_id"] is None


@pytest.mark.asyncio
async def test_manual_event_uses_official_http_after_tenth_completed_turn(tmp_path):
    class ManualProduct(Product):
        def __init__(self):
            super().__init__(["還有其他確定資料嗎？"])
            self.tasks = []
            self.manual_at = None

        async def post(self, path, json):
            if path.endswith("/jd/tasks"):
                assert json["expected_revision_id"] == self.revision
                self.manual_at = len(self.inputs)
                self.revision = str(uuid4())
                self.tasks.append(
                    {
                        "task_id": str(uuid4()),
                        "description": json["change"]["description"],
                    }
                )
                return Response({"revision_id": self.revision, "tasks": self.tasks})
            return await super().post(path, json)

        async def get(self, path):
            if path.endswith("/jd/work"):
                return Response({"revision_id": self.revision, "tasks": self.tasks})
            return await super().get(path)

    product = ManualProduct()

    async def review(pending):
        if pending["review_kind"] == "manual_jd_edit":
            return {
                "question_id": pending["question_id"],
                "action": "create_task",
                "title": "收貨差異",
                "description": pending["required_text"],
                "reason": "無相關task，按公開初始語意建立",
            }
        return review_answer(pending, mode="unknown")

    await journey(
        product, tmp_path, Employee("warehouse"), 12, BatchGuard(), review=review
    )
    assert product.manual_at == 10
    import json

    event = json.loads((tmp_path / "manual-edit.json").read_text(encoding="utf-8"))
    assert event["status"] == "saved"
    assert event["after"]["revision_id"] == event["http_result"]["revision_id"]
    assert len(product.inputs) == 12
