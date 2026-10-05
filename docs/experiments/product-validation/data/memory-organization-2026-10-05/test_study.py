"""Reject an outbound cap that differs from the experiment reservation."""

import asyncio
import importlib.util
from decimal import Decimal
from pathlib import Path

import httpx2
import pytest


def load_study():
    spec = importlib.util.spec_from_file_location(
        "organization_study", Path(__file__).with_name("study.py")
    )
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    return study


def test_budget_accepts_65th_call_but_still_enforces_money_and_time(
    tmp_path, monkeypatch
):
    study = load_study()
    (tmp_path / "tools.json").write_text("[]", encoding="utf-8")
    budget = study.Recorder(tmp_path).budget
    for index in range(65):
        budget.reserve(str(index), Decimal("0.0001"))
    assert budget.outbound_calls == 65
    with pytest.raises(ValueError, match="estimated_budget_limit"):
        budget.reserve("over-budget", Decimal("0.10"))
    monkeypatch.setattr(study.time, "monotonic", lambda: budget.started + 1201)
    with pytest.raises(ValueError, match="time_limit"):
        budget.reserve("over-time", Decimal("0.0001"))


def test_settlement_releases_only_the_reserved_difference():
    study = load_study()
    budget = study.StudyBudget(max_outbound_calls=2)
    budget.reserve("generation", Decimal("0.04"))
    budget.reserve("count", Decimal("0.0001"))
    budget.settle("generation", Decimal("0.01"))
    assert budget.occupied == Decimal("0.0101")
    assert budget.pending == {"count": Decimal("0.0001")}
    with pytest.raises(ValueError, match="outbound_limit"):
        budget.reserve("third", Decimal("0.0001"))


@pytest.mark.asyncio
async def test_formal_loop_can_finish_on_step_17_with_study_settings(monkeypatch):
    study = load_study()
    monkeypatch.syspath_prepend(str(study.ROOT / "apps/api"))
    from caliburn.agent_execution.tool_steps import run_response_loop
    from langgraph.checkpoint.memory import InMemorySaver
    from tests.unit.test_response_loop import LoopProbe, initial_request, response_at

    model = study.study_model_settings()
    probe = LoopProbe(
        [response_at(index, tools=1) for index in range(1, 17)]
        + [response_at(17, final=True)]
    )
    result = await run_response_loop(
        InMemorySaver(),
        thread_id="study-17-steps",
        request=initial_request(),
        runtime=probe.runtime(),
        max_tool_calls=model.max_tool_calls_per_step,
        max_model_steps=model.max_model_steps,
    )
    assert result["completed_steps"] == 17
    assert result["next_action"] == "deliver_answer"
    assert len(probe.effects) == 16


def test_reject_mismatched_output_cap_before_reserving(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "organization_study", Path(__file__).with_name("study.py")
    )
    study = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(study)
    (tmp_path / "tools.json").write_text("[]", encoding="utf-8")
    recorder = study.Recorder(tmp_path)
    recorder.counted = 10
    recorder.count_payload = {"model": "gpt-6-luna", "tools": []}
    request = httpx2.Request(
        "POST",
        "https://api.openai.com/v1/responses",
        json={**recorder.count_payload, "max_output_tokens": 123},
    )
    with pytest.raises(asyncio.CancelledError, match="output_cap_mismatch"):
        asyncio.run(recorder.request(request))
    assert recorder.budget.outbound_calls == 0
    assert not (tmp_path / "trace.jsonl").exists()
