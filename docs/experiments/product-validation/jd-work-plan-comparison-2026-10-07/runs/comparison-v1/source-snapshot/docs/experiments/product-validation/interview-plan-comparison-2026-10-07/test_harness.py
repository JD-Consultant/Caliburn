"""Offline counterexamples for the finite paid experiment, never product tests."""

import asyncio
from decimal import Decimal

import httpx2
import pytest
from conditional_answers import Employee
from guard import BatchGuard, GuardedTransport


def count_payload():
    return {
        "model": "gpt-6-luna",
        "input": [{"role": "user", "content": "hello"}],
        "instructions": "same",
        "tools": [{"name": "revise_jd_profile"}],
    }


def test_compact_is_counted_reserved_and_original_passes(tmp_path):
    payload = count_payload()
    guard = BatchGuard(limit=Decimal(2))
    guard.count(payload, 45000)
    original = {
        "id": "cmp",
        "object": "response.compaction",
        "output": [{"type": "compaction", "encrypted_content": "opaque-original"}],
        "usage": {"input_tokens": 45000, "output_tokens": 100, "total_tokens": 45100},
    }

    async def reply(request):
        return httpx2.Response(200, json=original)

    async def run():
        transport = GuardedTransport(
            guard, httpx2.MockTransport(reply), tmp_path / "trace.jsonl"
        )
        async with httpx2.AsyncClient(transport=transport) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses/compact",
                json={
                    "model": payload["model"],
                    "input": payload["input"],
                    "service_tier": "default",
                },
            )
            assert response.json() == original

    asyncio.run(run())
    assert guard.spent > 0
    assert not guard.attempts
    assert "opaque-original" not in (tmp_path / "trace.jsonl").read_text()


def test_compact_has_no_matching_count_is_refused():
    guard = BatchGuard(limit=Decimal(2))
    with pytest.raises(RuntimeError, match="matching"):
        guard.admit_compact(
            {"model": "gpt-6-luna", "input": [], "service_tier": "default"}
        )


def test_unknown_compact_usage_keeps_full_reservation():
    guard = BatchGuard(limit=Decimal(2))
    payload = count_payload()
    guard.count(payload, 45000)
    attempt = guard.admit_compact(
        {
            "model": payload["model"],
            "input": payload["input"],
            "service_tier": "default",
        }
    )
    occupied = guard.occupied
    assert occupied >= Decimal("0.79")
    guard.settle(attempt, None)
    assert guard.occupied == occupied
    assert guard.stop_reason


def test_finite_generation_counter_includes_retry_attempts():
    guard = BatchGuard(limit=Decimal(2), max_generations=1)
    payload = count_payload() | {"service_tier": "default", "max_output_tokens": 16384}
    guard.count(payload, 10)
    guard.admit(payload)
    with pytest.raises(RuntimeError, match="generation"):
        guard.admit(payload)


def test_partial_gap_answers_only_after_real_related_topic_return():
    employee = Employee("warehouse")
    first = employee.answer("盤點出現差異時你怎麼處理、誰批准？")
    assert "想不清楚" in first
    assert "inventory-authority" in employee.gaps
    unrelated = employee.answer("收貨異常由誰批准？")
    assert "財務調帳" not in unrelated
    employee.answer("你怎麼帶新人？")
    answer = employee.answer("回到盤點，誰批准調帳？")
    assert "主管核准" in answer
    assert "inventory-authority" not in employee.gaps


def test_question_summary_does_not_release_hidden_annual_facts():
    employee = Employee("warehouse")
    answer = employee.answer("已了解全年盤點工作。\n\n請說收貨核對的步驟？")
    assert "十二月" not in answer
    assert employee.audit[-1]["fact_id"] == "receiving"


def test_known_refusal_does_not_reopen_specific_case():
    employee = Employee("course_admin")
    assert "不想談" in employee.answer("收到老師投訴或滿意度回饋時怎麼處理？")
    answer = employee.answer("請說被投訴老師的個案和學員姓名？")
    assert "沒有其他確定資料" in answer


def test_http_driver_finite_closure_reads_saved_formal_jd(tmp_path):
    from conditional_answers import CLOSURE
    from run_batch import journey

    submitted = []

    async def reply(request):
        path = request.url.path
        if request.method == "POST":
            body = __import__("json").loads(request.content)
            if path == "/api/job-files":
                return httpx2.Response(200, json={"job_file_id": "file"})
            submitted.append(body["text"])
            return httpx2.Response(202, json={"execution_id": "execution"})
        if path.endswith("/interviews"):
            return httpx2.Response(
                200,
                json={
                    "messages": [
                        {
                            "speaker": "consultant",
                            "interview_text": "請說收貨驗收的步驟？",
                        }
                    ]
                },
            )
        if path.endswith("/interview-plan"):
            return httpx2.Response(200, json={"job_file_id": "file", "plan": None})
        if "/consultant-turns/" in path:
            return httpx2.Response(
                200,
                json={"status": "completed", "candidate": None, "plan_preview": None},
            )
        return httpx2.Response(200, json={"formal_saved": True})

    async def run():
        async with httpx2.AsyncClient(
            base_url="http://127.0.0.1", transport=httpx2.MockTransport(reply)
        ) as client:
            result = await journey(
                client, tmp_path, Employee("warehouse"), 3, BatchGuard()
            )
        assert result["natural_completion_verified"] is False

    asyncio.run(run())
    assert len(submitted) == 3
    assert submitted[-1] == CLOSURE
    assert (tmp_path / "formal-jd.json").exists()
    assert "財務調帳" not in submitted[1]
    audit = __import__("json").loads(
        (tmp_path / "conditional-audit.json").read_text(encoding="utf-8")
    )
    assert len(audit["audit"]) == 1
    assert audit["audit"][0]["actually_submitted"] is True


def test_freeze_includes_canonical_and_runtime_packaged_json():
    from manifest import source_hashes

    hashes = source_hashes()
    assert (
        "apps/api/contracts/tools/edit-interview-plan-arguments.schema.json" in hashes
    )
    assert "apps/api/contracts/http/consultant-turn.schema.json" in hashes
    assert any(
        name.startswith("apps/api/src/caliburn/contracts/generated/")
        and name.endswith(".json")
        for name in hashes
    )
    assert (
        "docs/experiments/product-validation/data/full-interview-rag-2026-10-06/batch_guard.py"
        in hashes
    )


def test_semantic_review_known_compound_and_gap_conditions():
    employee = Employee("warehouse")
    decision = {
        "mode": "answer",
        "fact_ids": ["receiving", "supplier-returns"],
        "reason": "Both flows explicitly asked",
    }
    answer = employee.reviewed_answer("兩種退收貨的步驟", decision)
    assert "逐箱" in answer and "供應商退貨更精確" in answer
    answer = employee.reviewed_answer(
        "再確認收貨責任", decision | {"fact_ids": ["receiving"]}
    )
    assert "沒有其他" not in answer
    assert employee.audit[-1]["known_confirmation_ids"] == ["receiving"]
    with pytest.raises(ValueError, match="availability"):
        employee.reviewed_answer(
            "盤點誰調帳", decision | {"fact_ids": ["inventory-authority"]}
        )


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_no_private_fact_selected_immediately_before_closure(tmp_path, status):
    # The 3-turn HTTP seam above selects exactly one answer; 2 turns must select none.
    from run_batch import journey

    submitted = []

    async def reply(request):
        path = request.url.path
        if request.method == "POST":
            if path == "/api/job-files":
                return httpx2.Response(200, json={"job_file_id": "file"})
            submitted.append(__import__("json").loads(request.content)["text"])
            return httpx2.Response(202, json={"execution_id": "execution"})
        if path.endswith("/interviews"):
            return httpx2.Response(
                200,
                json={
                    "messages": [
                        {"speaker": "consultant", "interview_text": "收貨驗收怎麼做？"}
                    ]
                },
            )
        if "/consultant-turns/" in path:
            return httpx2.Response(200, json={"status": status})
        return httpx2.Response(200, json={"plan": None})

    async def run():
        async with httpx2.AsyncClient(
            base_url="http://127.0.0.1", transport=httpx2.MockTransport(reply)
        ) as client:
            result = await journey(
                client, tmp_path, Employee("warehouse"), 2, BatchGuard()
            )
            assert result["stop"] == (
                "terminal_failed" if status == "failed" else "common_bounded_closure"
            )
            assert result["closure_submitted"] is (status == "completed")

    asyncio.run(run())
    audit = __import__("json").loads(
        (tmp_path / "conditional-audit.json").read_text(encoding="utf-8")
    )
    assert audit["audit"] == []


def test_specific_case_refusal_allows_personal_data_process():
    employee = Employee("course_admin")
    review = {
        "mode": "answer",
        "fact_ids": ["sensitive-evaluation"],
        "reason": "Only anonymous process; refuses the specific complaint",
    }
    employee.reviewed_answer("投訴流程怎麼做", review)
    answer = employee.reviewed_answer(
        "不談個案，問個資保存流程", review | {"fact_ids": ["privacy"]}
    )
    assert "鎖櫃" in answer


def test_switch_before_partial_gap_does_not_unlock_return_fact():
    employee = Employee("warehouse")
    review = {
        "mode": "answer",
        "fact_ids": ["training"],
        "reason": "Actual training question",
    }
    employee.reviewed_answer("新人怎麼帶", review)
    employee.reviewed_answer("庫存差異", review | {"fact_ids": ["inventory-partial"]})
    with pytest.raises(ValueError, match="topic must follow"):
        employee.reviewed_answer(
            "回到庫存調帳", review | {"fact_ids": ["inventory-authority"]}
        )
    employee.reviewed_answer("再次確認帶新人", review)
    answer = employee.reviewed_answer(
        "回到庫存調帳", review | {"fact_ids": ["inventory-authority"]}
    )
    assert "財務調帳" in answer


def test_no_question_is_neutral_reminder_not_employee_unknown():
    employee = Employee("warehouse")
    answer = employee.reviewed_answer(
        "這次先不往下追問。",
        {"mode": "no_question", "fact_ids": [], "reason": "No actual question"},
    )
    assert answer == "可以依我已說過的工作範圍繼續訪談；我沒有新增事實。"
    assert not employee.disclosed
    assert employee.audit[-1]["driver_reminder"] is True


def test_compound_true_unknown_is_not_invitation_to_reask():
    employee = Employee("warehouse")
    answer = employee.reviewed_answer(
        "收貨怎麼核對？外箱破損怎麼處理？",
        {
            "mode": "answer",
            "fact_ids": ["receiving"],
            "reason": "Known receiving, damage detail unknown",
            "unknown_subtopics": ["外箱破損"],
            "omitted_subtopics": [],
        },
    )
    assert "關於你問的「外箱破損」" in answer
    assert "保留未知" in answer
    assert "之後再具體問" not in answer


def test_consecutive_no_question_closes_without_repeating_reminder(
    tmp_path, monkeypatch
):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    import run_batch
    from conditional_answers import CLOSURE, CONTINUE

    monkeypatch.setattr(run_batch, "HERE", tmp_path)
    submitted = []

    async def execute(*args, **kwargs):
        return SimpleNamespace(scalar_one=lambda: 0)

    @asynccontextmanager
    async def sessions():
        yield SimpleNamespace(execute=execute)

    app = SimpleNamespace(
        state=SimpleNamespace(database=SimpleNamespace(sessions=sessions))
    )

    async def reply(request):
        path = request.url.path
        if request.method == "POST":
            if path == "/api/job-files":
                return httpx2.Response(200, json={"job_file_id": "file"})
            submitted.append(__import__("json").loads(request.content)["text"])
            return httpx2.Response(202, json={"execution_id": "execution"})
        if path.endswith("/interviews"):
            messages = [
                {
                    "source_id": str(i),
                    "interview_sequence": i + 1,
                    "speaker": "employee",
                    "interview_text": text,
                }
                for i, text in enumerate(submitted)
            ]
            messages.append(
                {
                    "speaker": "consultant",
                    "interview_text": "已整理，這次先不往下追問。",
                }
            )
            return httpx2.Response(200, json={"messages": messages})
        if "/consultant-turns/" in path:
            return httpx2.Response(200, json={"status": "completed"})
        if path.endswith("/jd/sources"):
            return httpx2.Response(200, json={"revision_id": "rev", "references": []})
        return httpx2.Response(200, json={"plan": None})

    async def judge():
        while True:
            for path in tmp_path.glob("reviews/*/pending.json"):
                target = path.with_name("decision.json")
                if target.exists():
                    continue
                pending = __import__("json").loads(path.read_text(encoding="utf-8"))
                target.write_text(
                    __import__("json").dumps(
                        {
                            "question_id": pending["question_id"],
                            "fact_ids": [],
                            "mode": "no_question",
                            "reason": "No actual question",
                        }
                    ),
                    encoding="utf-8",
                )
            await asyncio.sleep(0.01)

    async def run():
        task = asyncio.create_task(judge())
        try:
            async with httpx2.AsyncClient(
                base_url="http://127.0.0.1", transport=httpx2.MockTransport(reply)
            ) as client:
                result = await run_batch.journey(
                    client, tmp_path, Employee("warehouse"), 6, BatchGuard(), app
                )
            assert result["stop"] == "closure_after_missing_active_progress"
            assert result["driver_reminders"] == 1
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(run())
    assert submitted[1:] == [CONTINUE, CLOSURE]


def test_fixed_source_chain_and_anonymous_bundle(tmp_path):
    from evidence import collect_sources, write_blind_bundle

    seen = []

    async def reply(request):
        assert request.url.params["revision_id"] == "fixed-revision"
        source = request.url.params.get("source_ref")
        seen.append(source)
        content = (
            {
                "kind": "work_understanding",
                "body": "original fixed body",
                "references": [{"source_ref": "situation_fixed"}],
            }
            if source is None
            else {
                "kind": "work_situation",
                "body": "fixed situation",
                "references": [{"source_ref": "interview_2"}],
            }
            if source == "situation_fixed"
            else {
                "kind": "interview",
                "speaker": "employee",
                "interview_text": "original employee",
            }
        )
        return httpx2.Response(
            200,
            json={
                "revision_id": "fixed-revision",
                "citation_id": "citation",
                "content": content,
            },
        )

    async def run():
        async with httpx2.AsyncClient(
            base_url="http://127.0.0.1", transport=httpx2.MockTransport(reply)
        ) as client:
            return await collect_sources(
                client,
                "/api/job-files/file",
                {
                    "revision_id": "fixed-revision",
                    "references": [{"citation_id": "citation"}],
                },
            )

    content = asyncio.run(run())
    assert seen == [None, "situation_fixed", "interview_2"]
    case = tmp_path / "warehouse-P2-private"
    case.mkdir()

    def save(name, value):
        (case / name).write_text(__import__("json").dumps(value), encoding="utf-8")

    save("fixed-source-contents.json", content)
    save(
        "formal-jd.json", {"profile": {"title": "warehouse"}, "work": {}, "sources": {}}
    )
    save(
        "formal-interviews.json",
        {
            "messages": [
                {
                    "source_id": "s",
                    "interview_sequence": 2,
                    "speaker": "employee",
                    "interview_text": "original employee",
                    "execution_id": "private-graph",
                }
            ]
        },
    )
    save("formal-plan.json", {"plan": "private plan"})
    opaque = write_blind_bundle(case, tmp_path / "blind", tmp_path / "private-map.json")
    raw = (tmp_path / "blind" / (opaque + ".json")).read_text(encoding="utf-8")
    assert "original fixed body" in raw and "original employee" in raw
    assert "P2" not in raw and "private plan" not in raw and "private-graph" not in raw


def test_pre_work_C_is_not_mid_work_adoption(tmp_path):
    from guard import digest
    from measurements import measure

    c = [{"type": "compaction", "encrypted_content": "original"}]
    rows = [
        {
            "event": "received",
            "attempt": "compact",
            "endpoint": "/v1/responses/compact",
            "role": "A",
            "time": "1",
            "output_item_sha256": [digest(item) for item in c],
        },
        {
            "event": "admitted",
            "attempt": "next",
            "endpoint": "/v1/responses",
            "role": "A",
            "time": "2",
            "input_item_sha256": [digest(item) for item in c],
            "input": [],
        },
    ]
    checkpoint = {
        "checkpoint_id": "c-id",
        "thread_id": "c-thread",
        "adopted": True,
        "preparation_policy": {"threshold_tokens": 128000},
        "compaction_item_sha256": [digest(item) for item in c],
    }
    (tmp_path / "provider-trace.jsonl").write_text(
        "\n".join(__import__("json").dumps(row) for row in rows)
    )
    (tmp_path / "checkpoint-witness.jsonl").write_text(
        __import__("json").dumps(checkpoint)
    )
    witness = measure(tmp_path)["A_compact_adoptions"][0]
    assert witness["boundary"] == "pre-work"
    assert witness["checkpoint_adopted"] is False
    assert witness["any_boundary_checkpoint_adopted"] is True


def test_mid_work_projection_uses_exact_C_checkpoint_and_next_item(tmp_path):
    from guard import digest
    from measurements import measure

    c = [{"type": "compaction", "encrypted_content": "original"}]
    plan = {"type": "message", "role": "user", "content": "current saved plan"}
    rows = [
        {
            "event": "received",
            "attempt": "compact",
            "endpoint": "/v1/responses/compact",
            "role": "A",
            "time": "1",
            "output_item_sha256": [digest(item) for item in c],
        },
        {
            "event": "admitted",
            "attempt": "next",
            "endpoint": "/v1/responses",
            "role": "A",
            "time": "2",
            "input_item_sha256": [digest(item) for item in c] + [digest(plan)],
            "input": [{"type": "compaction"}, plan],
        },
    ]
    checkpoint = {
        "checkpoint_id": "c-id",
        "thread_id": "c-thread",
        "adopted": True,
        "preparation_policy": None,
        "compaction_item_sha256": [digest(item) for item in c],
    }
    projection = {
        "input_binding": {
            "compact_position": {"thread_id": "c-thread", "checkpoint_id": "c-id"}
        },
        "projection": {"plan_item": plan},
    }
    (tmp_path / "provider-trace.jsonl").write_text(
        "\n".join(__import__("json").dumps(row) for row in rows)
    )
    path = tmp_path / "checkpoint-witness.jsonl"
    path.write_text(
        "\n".join(__import__("json").dumps(row) for row in [checkpoint, projection])
    )
    witness = measure(tmp_path)["A_compact_adoptions"][0]
    assert witness["boundary"] == "mid-work"
    assert witness["next_A_exact_saved_plan_item"] is True
    projection["input_binding"]["compact_position"]["checkpoint_id"] = "other-C"
    path.write_text(
        "\n".join(__import__("json").dumps(row) for row in [checkpoint, projection])
    )
    assert (
        measure(tmp_path)["A_compact_adoptions"][0][
            "exact_bound_plan_projection_checkpoint"
        ]
        is False
    )


def test_freeze_archives_exact_source_bytes_before_dispatch(tmp_path, monkeypatch):
    import manifest

    path = tmp_path / "original.py"
    path.write_bytes(b"original WIP bytes\r\n")
    monkeypatch.setattr(manifest, "ROOT", tmp_path)
    monkeypatch.setattr(manifest, "GUIDES", [])
    monkeypatch.setattr(
        manifest, "source_hashes", lambda: {"original.py": manifest.sha(path)}
    )
    phase = tmp_path / "batch"
    phase.mkdir()
    data = manifest.freeze("formal", phase / "manifest.json")
    assert (phase / "source-snapshot/original.py").read_bytes() == path.read_bytes()
    assert data["runtime"]["dependencies"]["openai"]
