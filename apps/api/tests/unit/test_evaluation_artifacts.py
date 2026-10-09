"""A completed candidate artifact survives failure of optional diagnostics."""

import asyncio
import json
import sys
from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.settings import ModelSettings
from evaluations import authorized_consultant_comparison as authorized
from evaluations import consultant_comparison as comparison


@pytest.mark.parametrize("failure_stage", ["refresh", "read", "save"])
@pytest.mark.parametrize("entry", ["scripted", "authorized"])
def test_candidate_result_is_saved_before_diagnostics(monkeypatch, tmp_path, failure_stage, entry):
    case_path = tmp_path / "case.json"
    case_path.write_text(
        json.dumps(
            {
                "case": {"name": "synthetic", "inputs": ["synthetic"], "criteria": []},
                "candidates": [{"name": "baseline"}, {"name": "variant"}],
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "comparison"
    candidate = destination / "baseline"
    result = {"job_file_id": str(uuid4()), "all_inputs_completed": True, "turns": []}
    driven = []
    observed = []

    @asynccontextmanager
    async def lifespan(app):
        yield

    async def drive_case(*args, **kwargs):
        driven.append("completed")
        return result.copy()

    def observe(stage):
        # This is the key ordering assertion: formal output precedes every diagnostic operation.
        observed.append(stage)
        assert json.loads((candidate / "result.json").read_text(encoding="utf-8")) == result
        if failure_stage == stage:
            raise RuntimeError("synthetic-sensitive-exception-message")
        return []

    original_save = comparison.save_new

    def save(path, value):
        if path.name == "diagnostics.json":
            observe("save")
        original_save(path, value)

    monkeypatch.setattr(
        comparison,
        "create_app",
        lambda *args, **kwargs: SimpleNamespace(router=SimpleNamespace(lifespan_context=lifespan)),
    )
    monkeypatch.setattr(comparison, "drive_case", drive_case)
    monkeypatch.setattr(
        comparison, "refresh_diagnostics", lambda *args, **kwargs: observe("refresh")
    )
    monkeypatch.setattr(comparison, "read_diagnostics", lambda *args, **kwargs: observe("read"))
    monkeypatch.setattr(comparison, "save_new", save)
    monkeypatch.setattr(comparison, "save_source_snapshot", lambda _: {})
    monkeypatch.setattr(
        comparison,
        "prepare_isolated_database",
        lambda url: DatabaseSettings(url=url, schema="eval_synthetic"),
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "comparison",
            str(case_path),
            "--scripted",
            "--database-url",
            "postgresql://localhost/synthetic_test",
            "--output",
            str(destination),
        ],
    )
    if entry == "scripted":
        assert comparison.main() == 1
    else:
        monkeypatch.setattr(authorized, "save_source_snapshot", lambda _: {})
        monkeypatch.setattr(
            authorized, "prepare_isolated_database", comparison.prepare_isolated_database
        )
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            outcomes = runner.run(
                authorized.run_authorized_comparison(
                    comparison.ConsultantComparison.model_validate_json(case_path.read_bytes()),
                    database_url="postgresql://localhost/synthetic_test",
                    model=ModelSettings(api_key="synthetic-never-used"),
                    create_guarded_client=lambda _: None,
                    authorization_reference="offline synthetic fixture",
                    guard_version="synthetic",
                    declared_cost_limits={"max_batch_cost_usd": "0"},
                    output_directory=destination,
                )
            )
        assert len(outcomes) == 1
        assert outcomes[0].result == result
        assert not outcomes[0].diagnostics_available
    assert driven == ["completed"]
    assert json.loads((candidate / "result.json").read_text(encoding="utf-8")) == result
    failure = json.loads((candidate / "diagnostics-failure.json").read_text(encoding="utf-8"))
    assert failure == {"stage": failure_stage, "error_type": "RuntimeError"}
    assert not (candidate / "failure.json").exists()
    assert not (candidate / "diagnostics.json").exists()
    assert (
        observed
        == ["refresh", "read", "save"][: ["refresh", "read", "save"].index(failure_stage) + 1]
    )


@pytest.mark.parametrize("cancellation", ["raw", "scope"])
async def test_obtained_formal_result_is_saved_before_cancellation_leaves_lifespan(
    monkeypatch, tmp_path, cancellation
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    import anyio

    from caliburn.app_composition import AppComposition
    from caliburn.settings import Settings
    from evaluations.consultant_cases import EvaluationCase

    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=1))
    release = Event()
    occupied = loop.run_in_executor(None, release.wait)
    obtained = asyncio.Event()
    exits = []
    scope = anyio.CancelScope()
    result = {"job_file_id": str(uuid4()), "all_inputs_completed": True}

    @asynccontextmanager
    async def lifespan(app):
        try:
            yield
        finally:
            exits.append((tmp_path / "result.json").exists())

    async def drive(*args, **kwargs):
        obtained.set()
        return result

    async def run():
        with scope:
            await comparison.run_candidate(
                Settings(
                    database=DatabaseSettings(
                        url="postgresql://localhost/synthetic_test", schema="eval_synthetic"
                    ),
                    model=ModelSettings(api_key="synthetic"),
                ),
                AppComposition(),
                EvaluationCase(name="synthetic", inputs=("synthetic",)),
                output_directory=tmp_path,
            )

    monkeypatch.setattr(
        comparison,
        "create_app",
        lambda *args, **kwargs: SimpleNamespace(router=SimpleNamespace(lifespan_context=lifespan)),
    )
    monkeypatch.setattr(comparison, "drive_case", drive)
    task = asyncio.create_task(run())
    try:
        await asyncio.wait_for(obtained.wait(), 2)
        await asyncio.sleep(0)
        if cancellation == "raw":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
        else:
            scope.cancel()
        await asyncio.sleep(0)
        assert not task.done(), "Cancellation must wait for the already obtained formal result"
        assert not exits
        release.set()
        if cancellation == "raw":
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await task
            assert scope.cancelled_caught
        assert exits == [True]
        assert json.loads((tmp_path / "result.json").read_text(encoding="utf-8")) == result
        assert not (tmp_path / "diagnostics.json").exists()
    finally:
        release.set()
        await occupied
        await asyncio.gather(task, return_exceptions=True)
