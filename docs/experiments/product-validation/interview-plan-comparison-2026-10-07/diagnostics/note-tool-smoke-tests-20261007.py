"""Synthetic offline counterexamples for the isolated note-tool smoke driver."""

import importlib.util
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
C_ROOT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/"
    "01a11182-e198-7652-87d2-d90d10463ed1"
)


@pytest.fixture(scope="module")
def smoke():
    sys.path.insert(0, str(ROOT / "apps/api/src"))
    source = HERE / "note-tool-smoke-20261007.py"
    assert source.is_file(), "The bounded smoke driver must exist before verification"
    spec = importlib.util.spec_from_file_location("note_tool_smoke_offline", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def scratch():
    directory = C_ROOT / ("note-tool-smoke-offline-test-" + uuid4().hex)
    directory.mkdir()
    try:
        yield directory
    finally:
        assert directory.resolve().parent == C_ROOT.resolve()
        shutil.rmtree(directory)


@pytest.mark.parametrize("plan", [None, "", " ", "\n\t"])
def test_first_turn_rejects_missing_or_blank_plan_even_with_a_valid_edit(smoke, plan):
    with pytest.raises((ValueError, RuntimeError)):
        smoke.require_first_turn({"plan": plan}, 1)


def test_first_turn_rejects_text_without_any_valid_edit(smoke):
    with pytest.raises((ValueError, RuntimeError)):
        smoke.require_first_turn({"plan": "Synthetic pending work"}, 0)


def test_first_turn_accepts_nonblank_plan_with_a_valid_edit(smoke):
    smoke.require_first_turn({"plan": "Synthetic pending work"}, 1)


def capacity_inputs():
    from caliburn.adapters.openai_responses import ResponseRequest

    request = ResponseRequest(
        model="gpt-6-luna",
        instructions="Synthetic offline smoke",
        input_items=[],
        tools=[],
        reasoning_effort="high",
        max_output_tokens=100,
    )
    count = {"input_tokens": 2, "attempt_id": uuid4()}
    limits = {
        "model": "gpt-6-luna",
        "max_input_tokens": 200000,
        "context_window_tokens": 230000,
        "max_output_tokens": 100,
    }
    return request, count, limits


@pytest.mark.parametrize(
    ("owner", "plan_edited", "pending", "steps"),
    [
        (None, True, True, 1),
        ("turn-2", False, True, 1),
        ("turn-2", True, False, 1),
        ("turn-2", True, True, 0),
    ],
)
def test_capacity_keeps_native_policy_until_all_smoke_prerequisites(
    smoke, owner, plan_edited, pending, steps
):
    control = smoke.SmokeControl()
    control.owner = owner
    control.plan_edited = plan_edited
    control.pending = pending
    request, count, limits = capacity_inputs()
    original_threshold = smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS
    control.capacity(request, count, limits, completed_steps=steps)
    assert (
        smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS == original_threshold
    )
    assert control.trigger_count == 0


def test_control_triggers_native_boundary_then_matching_ack_disables_it(smoke):
    control = smoke.SmokeControl()
    control.owner = "turn-2"
    control.plan_edited = True
    request, count, limits = capacity_inputs()
    original_threshold = smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS

    with pytest.raises(smoke.capacity_module.CompactionRequiredError):
        control.capacity(request, count, limits, completed_steps=1)
    assert control.trigger_count == 1
    assert (
        smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS == original_threshold
    )

    control.observe_saved(
        "turn-2:compact:synthetic",
        {
            "adopted": True,
            "preparation_policy": None,
            "compaction_snapshot": {"id": "C"},
        },
    )
    assert control.pending is False
    control.capacity(request, count, limits, completed_steps=2)
    assert control.trigger_count == 1


def test_second_controlled_boundary_without_native_ack_fails_closed(smoke):
    control = smoke.SmokeControl()
    control.owner = "turn-2"
    control.plan_edited = True
    request, count, limits = capacity_inputs()
    with pytest.raises(smoke.capacity_module.CompactionRequiredError):
        control.capacity(request, count, limits, completed_steps=1)
    with pytest.raises(RuntimeError, match="already requested without native adoption"):
        control.capacity(request, count, limits, completed_steps=2)
    assert control.trigger_count == 1
    assert control.pending is True


def projected_control(smoke):
    control = smoke.SmokeControl()
    control.expected_plan = "Synthetic saved pending work"
    control.compact_items = [
        {"type": "compaction", "encrypted_content": "opaque-synthetic-C"}
    ]
    control.projection = {
        "plan_item": {
            "role": "developer",
            "content": json.dumps({"plan": "Synthetic saved pending work"}),
        }
    }
    return control


def test_next_a_preserves_complete_native_c_and_exact_saved_plan(smoke):
    control = projected_control(smoke)
    payload = {
        "input": deepcopy([*control.compact_items, control.projection["plan_item"]])
    }
    control.check_next_a(payload)
    assert control.next_a is True


def test_next_a_rejects_loss_of_opaque_c_bytes(smoke):
    control = projected_control(smoke)
    payload = {
        "input": deepcopy([*control.compact_items, control.projection["plan_item"]])
    }
    payload["input"][0].pop("encrypted_content")
    with pytest.raises(RuntimeError, match="complete C plus exact saved plan"):
        control.check_next_a(payload)
    assert control.next_a is False


def test_next_a_rejects_projection_that_changed_the_actual_saved_plan(smoke):
    control = projected_control(smoke)
    control.projection["plan_item"]["content"] = json.dumps(
        {"plan": "Synthetic changed plan"}
    )
    payload = {
        "input": deepcopy([*control.compact_items, control.projection["plan_item"]])
    }
    with pytest.raises(RuntimeError, match="differs from actual saved candidate"):
        control.check_next_a(payload)
    assert control.next_a is False


def test_capacity_preserves_limits_and_restores_threshold_after_failure(
    smoke, monkeypatch
):
    control = smoke.SmokeControl()
    control.owner = "turn-2"
    control.plan_edited = True
    request, count, limits = capacity_inputs()
    original_threshold = smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS
    observed = []

    def reject(request_value, count_value, limits_value, *, completed_steps):
        observed.append(
            (
                request_value,
                count_value,
                limits_value,
                completed_steps,
                smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS,
            )
        )
        raise RuntimeError("Synthetic native capacity failure")

    monkeypatch.setattr(smoke, "original_capacity", reject)
    with pytest.raises(RuntimeError, match="Synthetic native capacity failure"):
        control.capacity(request, count, limits, completed_steps=1)
    assert len(observed) == 1
    assert observed[0][:4] == (request, count, limits, 1)
    assert observed[0][2] is limits
    assert observed[0][4] == 1
    assert (
        smoke.capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS == original_threshold
    )


@pytest.mark.parametrize(
    ("thread", "values"),
    [
        (
            "turn-2:prepare:synthetic",
            {
                "adopted": True,
                "preparation_policy": None,
                "compaction_snapshot": {"id": "C"},
            },
        ),
        (
            "turn-1:compact:synthetic",
            {
                "adopted": True,
                "preparation_policy": None,
                "compaction_snapshot": {"id": "C"},
            },
        ),
        (
            "turn-2:compact:synthetic",
            {
                "adopted": False,
                "preparation_policy": None,
                "compaction_snapshot": {"id": "C"},
            },
        ),
        (
            "turn-2:compact:synthetic",
            {
                "adopted": True,
                "preparation_policy": "first_request_fit",
                "compaction_snapshot": {"id": "C"},
            },
        ),
        (
            "turn-2:compact:synthetic",
            {"adopted": True, "compaction_snapshot": {"id": "C"}},
        ),
        (
            "turn-2:compact:synthetic",
            {"adopted": True, "preparation_policy": None, "compaction_snapshot": None},
        ),
    ],
)
def test_preparation_wrong_owner_and_incomplete_ack_cannot_consume_control(
    smoke, thread, values
):
    control = smoke.SmokeControl()
    control.owner = "turn-2"
    control.plan_edited = True
    request, count, limits = capacity_inputs()
    with pytest.raises(smoke.capacity_module.CompactionRequiredError):
        control.capacity(request, count, limits, completed_steps=1)
    control.observe_saved(thread, values)
    assert control.pending is True
    assert control.trigger_count == 1


@pytest.mark.parametrize(
    "name",
    [
        "note-smoke-../escape",
        "note-smoke-a/b",
        "note-smoke-a\\b",
        "../note-smoke-a",
        "C:/note-smoke-a",
        "priority-probe-a",
        "note-smoke-",
        "note-smoke-" + "a" * 49,
    ],
)
def test_output_path_rejects_names_that_escape_isolated_smoke_scope(smoke, name):
    with pytest.raises(ValueError):
        smoke.output_path(name)


def test_output_path_is_inside_the_approved_isolated_c_root(smoke):
    assert smoke.output_path("note-smoke-synthetic") == (
        C_ROOT / "caliburn-intplan-comparison/note-tool-smoke/note-smoke-synthetic"
    )


def synthetic_database_driver(port):
    from sqlalchemy.engine import URL

    container_id = "13cf811f4c8bf4ff395339fbdf89e6f444971d3fd718fddb84862c68580c07ee"
    inspected = [
        {
            "Id": container_id,
            "Name": "/caliburn-intplan-postgres-20261007",
            "State": {"Running": True},
            "Config": {
                "Env": [
                    "POSTGRES_USER=intplan_test",
                    "POSTGRES_DB=caliburn_intplan_test",
                    "POSTGRES_PASSWORD=synthetic-offline-only",
                ]
            },
            "NetworkSettings": {
                "Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": str(port)}]}
            },
        }
    ]

    def inspect(command, **kwargs):
        assert command == ["docker", "inspect", container_id]
        return SimpleNamespace(stdout=json.dumps(inspected))

    return SimpleNamespace(
        subprocess=SimpleNamespace(run=inspect),
        URL=URL,
        DatabaseSettings=lambda **kwargs: SimpleNamespace(**kwargs),
    )


def test_database_seam_accepts_only_the_owned_isolated_port_without_connecting(smoke):
    result = smoke.owned_database(synthetic_database_driver(55447), "synthetic_smoke")
    assert result.schema == "synthetic_smoke"
    assert "127.0.0.1:55447/caliburn_intplan_test" in result.url


def test_database_seam_refuses_the_other_database_port_without_connecting(smoke):
    with pytest.raises(ValueError, match="identity mismatch"):
        smoke.owned_database(synthetic_database_driver(55441), "synthetic_smoke")


def synthetic_prior():
    return {
        "spent_usd": "1.2",
        "occupied_usd": "1.6",
        "retained_reservations": {"first": "0.1", "second": "0.2", "third": "0.1"},
        "generations": 25,
        "compacts": 2,
        "outbound": 50,
        "counted_input": 120000,
        "stop_reason": None,
    }


def accounting_files(directory, ledger_guard, stop_guard):
    ledger = directory / "synthetic-ledger.json"
    stop = directory / "synthetic-stop.json"
    ledger.write_text(json.dumps({"guard": ledger_guard}), encoding="utf-8")
    stop.write_text(
        json.dumps({"last_current_journal_guard": stop_guard}), encoding="utf-8"
    )
    return ledger, stop


def test_prior_accounting_keeps_three_reservations_and_all_cumulative_counters(
    smoke, scratch
):
    prior = synthetic_prior()
    ledger, stop = accounting_files(scratch, prior, prior)
    assert smoke.load_prior(ledger, stop) == prior


@pytest.mark.parametrize(
    "counter", ["generations", "compacts", "outbound", "counted_input"]
)
def test_prior_accounting_cannot_restore_an_older_lower_counter(
    smoke, scratch, counter
):
    prior = synthetic_prior()
    reduced = deepcopy(prior)
    reduced[counter] -= 1
    ledger, stop = accounting_files(scratch, reduced, prior)
    with pytest.raises((ValueError, RuntimeError)):
        smoke.load_prior(ledger, stop)


def test_prior_accounting_cannot_restore_older_lower_spending(smoke, scratch):
    prior = synthetic_prior()
    reduced = {**prior, "spent_usd": "1.1", "occupied_usd": "1.5"}
    ledger, stop = accounting_files(scratch, reduced, prior)
    with pytest.raises((ValueError, RuntimeError)):
        smoke.load_prior(ledger, stop)


def test_prior_accounting_cannot_drop_the_third_unknown_reservation(smoke, scratch):
    prior = synthetic_prior()
    reduced = deepcopy(prior)
    reduced["retained_reservations"].pop("third")
    reduced["occupied_usd"] = "1.5"
    ledger, stop = accounting_files(scratch, reduced, prior)
    with pytest.raises((ValueError, RuntimeError)):
        smoke.load_prior(ledger, stop)


def test_prior_accounting_validates_occupied_total_before_acceptance(smoke, scratch):
    broken = {**synthetic_prior(), "occupied_usd": "0.1"}
    ledger, stop = accounting_files(scratch, broken, broken)
    with pytest.raises((ValueError, RuntimeError)):
        smoke.load_prior(ledger, stop)
