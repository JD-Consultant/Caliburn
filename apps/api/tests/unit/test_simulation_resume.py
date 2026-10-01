"""Resume the paid journey without replaying inputs or earlier journey operations."""

import argparse
import asyncio
import json
from pathlib import Path

import httpx2
import pytest

from scripts import simulate_interview as simulation


def completed_turn() -> dict:
    return {"turn": 1, "status": "completed", "employee": "第一句", "consultant": "請補充"}


def options(output: Path) -> argparse.Namespace:
    return argparse.Namespace(
        output=output,
        human_edit_at=1,
        cancel_during=1,
        kill_during=0,
        retry_failed=0,
        think_seconds=0,
        restart_command="",
    )


@pytest.mark.parametrize("first_status", ["active", "completed"])
async def test_resume_waits_original_execution_without_replaying_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, first_status: str
) -> None:
    output = tmp_path / "result.json"
    output.with_suffix(".progress.jsonl").write_text(json.dumps(completed_turn()) + "\n")
    requests: list[httpx2.Request] = []
    messages = [
        {"speaker": "app", "interview_text": "開場"},
        {"speaker": "employee", "interview_text": "第一句"},
        {"speaker": "consultant", "interview_text": "請補充"},
        {"speaker": "employee", "interview_text": "第二句"},
        {"speaker": "consultant", "interview_text": "已了解"},
    ]

    def transport(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        assert request.method == "GET", "Resume must not send another input or repeat an edit"
        if request.url.path.endswith("/interviews"):
            return httpx2.Response(200, json={"messages": messages})
        assert request.url.path.endswith("/consultant-turns/original")
        status = first_status if len(requests) == 1 else "completed"
        return httpx2.Response(
            200,
            json={
                "turn": {
                    "job_file_id": "job",
                    "execution_id": "original",
                    "input_text": "第二句",
                    "status": status,
                }
            },
        )

    async def no_employee_request(*_args: object) -> None:
        pytest.fail("No paid employee request after reaching the last requested turn")

    monkeypatch.setattr(simulation, "employee_reply", no_employee_request)
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(transport), base_url="http://test"
    ) as http:
        backend = simulation.Backend(http)
        backend.file_id = "job"
        resume = await simulation.prepare_resume(backend, output, "original")
        turns = await simulation.run_interview(
            backend,
            None,
            {"opening": "unused", "correction": {"turn": 99}},
            2,
            options(output),
            [],
            resume=resume,
        )
    assert [turn["turn"] for turn in turns] == [1, 2]
    assert turns[1]["employee"] == "第二句"
    assert turns[1]["consultant"] == "已了解"
    assert turns[1]["resumed"] is True
    assert len(output.with_suffix(".progress.jsonl").read_text(encoding="utf-8").splitlines()) == 2


async def test_resume_rejects_progress_from_different_interviews(tmp_path: Path) -> None:
    output = tmp_path / "result.json"
    output.with_suffix(".progress.jsonl").write_text(json.dumps(completed_turn()) + "\n")

    def transport(request: httpx2.Request) -> httpx2.Response:
        assert request.method == "GET"
        if request.url.path.endswith("/interviews"):
            return httpx2.Response(
                200,
                json={
                    "messages": [
                        {"speaker": "employee", "interview_text": "不是這份訪談"},
                    ]
                },
            )
        return httpx2.Response(
            200,
            json={
                "turn": {
                    "job_file_id": "job",
                    "execution_id": "original",
                    "input_text": "第二句",
                }
            },
        )

    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(transport), base_url="http://test"
    ) as http:
        backend = simulation.Backend(http)
        backend.file_id = "job"
        with pytest.raises(ValueError, match="history"):
            await simulation.prepare_resume(backend, output, "original")


@pytest.mark.parametrize(
    "restarting,code,recovers", [(False, 500, False), (True, 503, True), (True, 404, False)]
)
async def test_server_error_retry_is_limited_to_known_restart(
    monkeypatch: pytest.MonkeyPatch, restarting: bool, code: int, recovers: bool
) -> None:
    calls = 0

    def transport(_request: httpx2.Request) -> httpx2.Response:
        nonlocal calls
        calls += 1
        return httpx2.Response(code if calls == 1 else 200, json={"status": "completed"})

    async def no_wait(_seconds: float) -> None:
        pass

    monkeypatch.setattr(asyncio, "sleep", no_wait)
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(transport), base_url="http://test"
    ) as http:
        backend = simulation.Backend(http)
        if restarting:
            backend.expect_restart()
        if recovers:
            assert await backend.wait_for_turn("original") == "completed"
            assert calls == 2
        else:
            with pytest.raises(httpx2.HTTPStatusError):
                await backend.wait_for_turn("original")
            assert calls == 1


async def test_expired_restart_window_does_not_hide_server_error() -> None:
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(lambda _: httpx2.Response(500)), base_url="http://test"
    ) as http:
        backend = simulation.Backend(http)
        backend.expect_restart(seconds=0)
        with pytest.raises(TimeoutError):
            await backend.wait_for_turn("original")


async def test_restart_does_not_start_another_request_after_grace_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    now = 100.0
    requests = 0

    def transport(_request: httpx2.Request) -> httpx2.Response:
        nonlocal now, requests
        requests += 1
        now = 189.0
        return httpx2.Response(503 if requests == 1 else 200, json={"status": "completed"})

    async def advance(seconds: float) -> None:
        nonlocal now
        now += seconds

    monkeypatch.setattr(simulation, "time", SimpleNamespace(monotonic=lambda: now))
    monkeypatch.setattr(asyncio, "sleep", advance)
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(transport), base_url="http://test"
    ) as http:
        backend = simulation.Backend(http)
        backend.expect_restart()
        with pytest.raises(TimeoutError):
            await backend.wait_for_turn("original")
    assert requests == 1


def test_journey_events_survive_before_final_report(tmp_path: Path) -> None:
    from scripts.interview_progress import JourneyEvents

    output = tmp_path / "result.json"
    events = JourneyEvents(output)
    events.append({"event": "input_accepted", "turn": 25, "execution_id": "original"})
    assert not output.exists()
    assert JourneyEvents(output)[0]["execution_id"] == "original"


async def test_restart_turn_timeout_never_resends_unknown_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    requests = []

    def transport(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        if request.method == "POST":
            return httpx2.Response(200, json={"execution_id": "original"})
        return httpx2.Response(200, json={"messages": []})

    async def no_wait(_seconds: float) -> None:
        pass

    monkeypatch.setattr(simulation, "TURN_TIMEOUT_SECONDS", 0)
    monkeypatch.setattr(asyncio, "sleep", no_wait)
    monkeypatch.setattr(simulation.subprocess, "run", lambda *_args, **_kwargs: None)
    config = options(tmp_path / "result.json")
    config.human_edit_at = config.cancel_during = 0
    config.kill_during = 1
    config.retry_failed = 3
    async with httpx2.AsyncClient(
        transport=httpx2.MockTransport(transport), base_url="http://test"
    ) as http:
        turns = await simulation.run_interview(
            simulation.Backend(http),
            None,
            {"opening": "原句", "correction": {"turn": 99}},
            1,
            config,
            [],
        )
    assert turns[0]["status"] == "timeout"
    assert len([r for r in requests if r.method == "POST"]) == 1


def test_resume_deadline_does_not_reset_elapsed_time() -> None:
    from datetime import UTC, datetime, timedelta

    from scripts.interview_progress import seconds_until

    with pytest.raises(ValueError, match="passed"):
        seconds_until(datetime.now(UTC) - timedelta(seconds=1))
    with pytest.raises(ValueError, match="timezone"):
        seconds_until(datetime(2027, 1, 1))
