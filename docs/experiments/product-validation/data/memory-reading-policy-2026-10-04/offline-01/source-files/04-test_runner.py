"""Offline failure-boundary checks: no real credential or provider access."""

import asyncio
import json
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace

import analyze
import experiment
import pytest
from openai.types.responses import Response


def failed_response():
    return Response.model_validate(
        {
            "id": "resp_offline_failure",
            "created_at": 0,
            "model": experiment.MODEL,
            "object": "response",
            "output": [],
            "parallel_tool_calls": True,
            "tool_choice": "auto",
            "tools": [],
            "status": "failed",
            "service_tier": "default",
            "usage": {
                "input_tokens": 100,
                "input_tokens_details": {"cached_tokens": 0, "cache_write_tokens": 0},
                "output_tokens": 10,
                "output_tokens_details": {"reasoning_tokens": 5},
                "total_tokens": 110,
            },
        }
    )


def test_failed_provider_response_stops_batch_before_next_cell(monkeypatch, tmp_path):
    calls = []
    material = json.loads(
        (Path(__file__).parent / "live-01/materials.json").read_text(encoding="utf-8")
    )
    schedule = [
        {"arm": "raw", "case_id": "failure", "repeat": repeat} for repeat in (1, 2)
    ]
    monkeypatch.setattr(
        experiment,
        "materials_and_manifest",
        lambda _: (
            material,
            [{"case_id": "failure", "prompt": "離線測試"}],
            {"schedule": schedule},
        ),
    )
    monkeypatch.setattr(
        experiment, "read_openai_api_key", lambda _: "offline-not-a-key"
    )

    @asynccontextmanager
    async def offline_client(**_):
        yield object()

    async def count(_, request):
        calls.append("count")
        return SimpleNamespace(input_tokens=100)

    async def create(_, request):
        calls.append("create")
        return failed_response()

    # Only replace the external boundary; exercise the real runner and ledger.
    monkeypatch.setattr(experiment, "create_responses_client", offline_client)
    monkeypatch.setattr(experiment, "count_response_input", count)
    monkeypatch.setattr(experiment, "create_response", create)

    async def no_wait(_):
        return None

    monkeypatch.setattr(experiment.asyncio, "sleep", no_wait)
    asyncio.run(experiment.run(tmp_path))
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert len(result["results"]) == 1
    assert calls == ["count", "create"]
    assert result["outbound_calls"] == 2
    assert result["pending"] == {"count-failure-raw-1-1": "0.0001"}
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["reason"] == "response_failed"


def test_preprocessing_groups_actual_after_event_not_nonexistent_event_id(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(analyze, "__file__", str(tmp_path / "study/analyze.py"))
    source = tmp_path / "compaction-long-interview-2026-10-04"
    for name, event_id in (("main-02", "e012"), ("main-03", "e052")):
        directory = source / name
        directory.mkdir(parents=True)
        payload = (
            failed_response()
            .model_copy(update={"status": "completed"})
            .model_dump(mode="json")
        )
        (directory / "trace.jsonl").write_text(
            json.dumps(
                {
                    "phase": "memory",
                    "event": "response",
                    "path": "/v1/responses",
                    "after_event": event_id,
                    "payload": payload,
                }
            )
            + "\n",
            encoding="utf-8",
        )
    result = analyze.memory_preprocessing()
    assert result["batches"] == {"main-02/e012": 1, "main-03/e052": 1}
    assert result["generation_responses"] == 2
    assert result["input_tokens"] == 200


@pytest.mark.parametrize("exhausted", ("amount", "time"))
def test_manifest_lower_limit_stops_before_first_count(
    monkeypatch, tmp_path, exhausted
):
    material = json.loads(
        (Path(__file__).parent / "live-01/materials.json").read_text(encoding="utf-8")
    )
    monkeypatch.setattr(
        experiment,
        "materials_and_manifest",
        lambda _: (
            material,
            [{"case_id": "budget", "prompt": "離線測試"}],
            {
                "schedule": [{"arm": "raw", "case_id": "budget", "repeat": 1}],
                "max_estimated_usd": "0.000099" if exhausted == "amount" else "0.10",
                "max_seconds": 1200,
                "prior_occupied_usd": "1.024756355",
            },
        ),
    )
    monkeypatch.setattr(
        experiment, "read_openai_api_key", lambda _: "offline-not-a-key"
    )

    @asynccontextmanager
    async def offline_client(**_):
        yield object()

    async def count(_, request):
        return SimpleNamespace(input_tokens=100)

    async def create(_, request):
        return failed_response()

    monkeypatch.setattr(experiment, "create_responses_client", offline_client)
    monkeypatch.setattr(experiment, "count_response_input", count)
    monkeypatch.setattr(experiment, "create_response", create)
    if exhausted == "time":
        original_budget = experiment.Budget

        def elapsed_budget(**limits):
            budget = original_budget(**limits)
            budget.started -= 1201
            return budget

        monkeypatch.setattr(experiment, "Budget", elapsed_budget)
    asyncio.run(experiment.run(tmp_path))
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert result["outbound_calls"] == 0
    assert result["cumulative_occupied_usd"] == "1.024756355"
    failure = json.loads((tmp_path / "failure.json").read_text(encoding="utf-8"))
    assert failure["reason"] == (
        "estimated_budget_limit" if exhausted == "amount" else "time_limit_before_wait"
    )


@pytest.mark.parametrize("select_prompt", [False, True], ids=["shared", "per_cell"])
def test_cell_prompt_selection_preserves_inputs_and_separate_results(
    monkeypatch, tmp_path, select_prompt
):
    """Catch wrong prompt routing or overwriting paired cells, not model quality."""
    from copy import deepcopy

    payloads = []
    window = [{"role": "user", "content": "同一份合成材料"}]
    schedule = [
        {
            "arm": "raw_memory",
            "case_id": "probe",
            "repeat": 1,
            "prompt_variant": variant,
            "cell_id": f"probe-{variant}-1",
        }
        for variant in ("original", "candidate")
    ]
    prepared = (
        {"slots": {}},
        [{"case_id": "probe", "prompt": "同一個合成問題"}],
        {"schedule": schedule, "max_estimated_usd": "0.10", "max_seconds": 1200},
    )
    monkeypatch.setattr(
        experiment, "read_openai_api_key", lambda _: "offline-not-a-key"
    )

    @asynccontextmanager
    async def offline_client(**_):
        yield object()

    async def count(_, request):
        return SimpleNamespace(input_tokens=100)

    async def create(_, request):
        payloads.append(request.create_payload())
        response = failed_response().model_dump(mode="json")
        response.update(
            status="completed",
            output=[
                {
                    "type": "function_call",
                    "id": "fc_offline",
                    "call_id": "call_offline",
                    "name": "submit_jd_review",
                    "arguments": json.dumps(
                        {"changes": [], "questions": [], "note": "離線"}
                    ),
                    "status": "completed",
                }
            ],
        )
        return Response.model_validate(response)

    monkeypatch.setattr(experiment, "create_responses_client", offline_client)
    monkeypatch.setattr(experiment, "count_response_input", count)
    monkeypatch.setattr(experiment, "create_response", create)

    async def no_wait(_):
        pass

    monkeypatch.setattr(experiment.asyncio, "sleep", no_wait)
    prompts = {"original": "原指引", "candidate": "新指引"}
    instructions = (
        (lambda cell: prompts[cell["prompt_variant"]]) if select_prompt else "共同指引"
    )
    asyncio.run(
        experiment.run(
            tmp_path,
            prepared=prepared,
            context_builder=lambda *_: deepcopy(window),
            instructions=instructions,
        )
    )
    assert [p["instructions"] for p in payloads] == (
        ["原指引", "新指引"] if select_prompt else ["共同指引", "共同指引"]
    )
    assert [p["input"] for p in payloads] == [window, window]
    result = json.loads((tmp_path / "result.json").read_text(encoding="utf-8"))
    assert [cell["cell_id"] for cell in result["results"]] == [
        "probe-original-1",
        "probe-candidate-1",
    ]
    for cell_id in ("probe-original-1", "probe-candidate-1"):
        assert (
            json.loads(
                (tmp_path / f"result-{cell_id}.json").read_text(encoding="utf-8")
            )["status"]
            == "completed"
        )
