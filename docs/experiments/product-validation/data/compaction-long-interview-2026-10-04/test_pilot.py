"""Research guard: a wrong request or exceeded allowance must never reach the network."""

import importlib.util
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("compaction_pilot", HERE / "pilot.py")
assert spec is not None and spec.loader is not None
pilot = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = pilot
spec.loader.exec_module(pilot)


def request(text="原始員工輸入"):
    return pilot.ResponseRequest(
        model="gpt-6-luna",
        instructions="分析",
        input_items=[{"role": "user", "content": text}],
        tools=[],
        reasoning_effort="high",
        max_output_tokens=16_384,
    )


def test_generation_requires_the_exact_counted_context():
    guard = pilot.PilotAllowance()
    guard.record_count(request().count_payload(), 8000)
    with pytest.raises(pilot.PilotStop):
        guard.admit("/v1/responses", request("不同輸入").create_payload())
    assert guard.generation_calls == 0


def test_aggregate_input_limit_prevents_the_next_generation():
    guard = pilot.PilotAllowance(max_input_tokens=10_000)
    guard.record_count(request().count_payload(), 6000)
    guard.admit("/v1/responses", request().create_payload())
    with pytest.raises(pilot.PilotStop):
        guard.admit("/v1/responses", request().create_payload())
    assert guard.generation_calls == 1
    assert guard.admitted_input_tokens == 6000


def test_compaction_and_count_calls_cannot_escape_the_allowance():
    guard = pilot.PilotAllowance(max_outbound_calls=1)
    guard.admit("/v1/responses/input_tokens", request().count_payload())
    with pytest.raises(pilot.PilotStop):
        guard.admit("/v1/responses/input_tokens", request().count_payload())
    with pytest.raises(pilot.PilotStop):
        pilot.PilotAllowance().admit("/v1/responses/compact", {"model": "gpt-6-luna"})


def test_count_unknown_and_cost_reservation_stop_before_send():
    guard = pilot.PilotAllowance(max_estimated_usd=pilot.Decimal("0.001"))
    with pytest.raises(pilot.PilotStop):
        guard.record_count(request().count_payload(), None)
    guard.record_count(request().count_payload(), 8000)
    with pytest.raises(pilot.PilotStop):
        guard.admit("/v1/responses", request().create_payload())
    assert guard.generation_calls == 0


def test_pilot_does_not_replace_the_runners_step_capacity_policy():
    guard = pilot.PilotAllowance()
    guard.record_count(request().count_payload(), 130_000)
    guard.admit("/v1/responses", request().create_payload())
    assert guard.admitted_input_tokens == 130_000


@pytest.mark.parametrize(
    "suffix",
    ["?hostaddr=192.0.2.1", "?service=outside", "?options=-c%20search_path%3Dcaliburn"],
)
def test_connection_overrides_are_rejected_before_creating_a_schema(suffix):
    with pytest.raises(ValueError):
        pilot.validate_database_url(
            "postgresql://caliburn:synthetic@127.0.0.1:55441/caliburn_docker_test" + suffix
        )


def test_environment_cannot_override_the_approved_destination(monkeypatch):
    monkeypatch.setenv("PGHOSTADDR", "192.0.2.1")
    with pytest.raises(ValueError):
        pilot.validate_database_url(
            "postgresql://caliburn:synthetic@127.0.0.1:55441/caliburn_docker_test"
        )
