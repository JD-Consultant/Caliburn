import json
from copy import deepcopy

import completion_batch as subject
import pytest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def incident(tmp_path, monkeypatch):
    prior = tmp_path / "prior"
    inherited = {
        "spent_usd": "0.10",
        "occupied_usd": "0.113296750",
        "retained_reservations": {"old": "0.013296750"},
        "generations": 10,
        "compacts": 0,
        "outbound": 20,
        "counted_input": 1000,
        "stop_reason": None,
    }
    state = {
        **inherited,
        "spent_usd": "0.12",
        "occupied_usd": "0.145158875",
        "retained_reservations": {"old": "0.013296750", "unlogged": "0.011862125"},
        "generations": 12,
        "outbound": 23,
        "counted_input": 30361,
    }
    write(prior / "batch-state.json", {"guard": state, "all_scheduled_cases": subject.SCHEDULED})
    write(
        prior / "manifest.json",
        {"source_sha256": {}, "continuation": {"prior_accounting": inherited}},
    )
    complete = {"closure_submitted": True, "turns": [{"turn": 20, "status": "completed"}]}
    write(prior / subject.SCHEDULED[0] / "result.json", complete)
    rows = [
        {
            "event": "admitted",
            "time": "1",
            "case": subject.SCHEDULED[1],
            "attempt": "known",
            "endpoint": "/v1/responses",
            "outbound": 21,
            "generations": 11,
            "compacts": 0,
            "counted_input": 1000,
        },
        {
            "event": "received",
            "time": "2",
            "case": subject.SCHEDULED[1],
            "attempt": "known",
            "usage": {"input_tokens": 1},
            "spent_usd": "0.12",
            "outbound": 21,
            "generations": 11,
            "compacts": 0,
            "counted_input": 1000,
        },
        {"event": "count", "time": "3", "case": subject.SCHEDULED[1], "input_tokens": 29361},
    ]
    journal = prior / subject.SCHEDULED[1] / "provider-trace.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    status = tmp_path / "recovered-status.json"
    write(status, {"status": "failed"})
    metadata = tmp_path / "recovery.json"
    write(
        metadata,
        {
            "credential_read": False,
            "provider_calls": 0,
            "prior_server_closed": True,
            "prior_process_exit_code": 1,
            "resource_interruption": "artifact_disk_full",
            "recovered_turn_status": "failed",
            "closure_submitted": False,
            "execution_status_counts": {"completed": 13, "failed": 2},
            "recovery_server_closed": True,
        },
    )
    evidence = {
        str(path.resolve()): {"copy": str(path), "sha256": subject.file_hash(path)}
        for path in [
            prior / "batch-state.json",
            prior / "manifest.json",
            prior / subject.SCHEDULED[0] / "result.json",
            journal,
        ]
    }
    audit = {
        "version": 1,
        "resource_interruption": "artifact_disk_full",
        "prior_batch_path": str(prior.resolve()),
        "prior_accounting": state,
        "journal_known_counters": {
            "generations": 11,
            "compacts": 0,
            "outbound": 22,
            "counted_input": 30361,
        },
        "conservative_unjournaled_counter_delta": {
            "generations": 1,
            "compacts": 0,
            "outbound": 1,
            "counted_input": 0,
        },
        "unjournaled_reservations": {"unlogged": "0.011862125"},
        "reserve_basis": {"counted_input": 29361, "max_output_tokens": 16384},
        "last_received_spent_usd": "0.12",
        "journal_attempts": {"admitted": 1, "received": 1},
        "missing_case_completion": {
            subject.SCHEDULED[1]: {
                "closure_submitted": False,
                "turns": [{"turn": 12, "status": "failed"}],
                "source": str(status),
                "source_sha256": subject.file_hash(status),
            }
        },
        "recovery_metadata": {"path": str(metadata), "sha256": subject.file_hash(metadata)},
        "original_evidence": evidence,
        "absolute_deadline_utc": subject.DEADLINE.isoformat(),
    }
    target = tmp_path / "disk-audit.json"
    write(target, audit)
    monkeypatch.setattr(subject, "DISK_AUDIT", target, raising=False)
    return prior, audit, target


def test_disk_full_recovery_preserves_completed_case_and_all_consumption(incident):
    prior, audit, _ = incident
    accounting, note, todo = subject.read_prior(prior, current_sources={})
    assert accounting == audit["prior_accounting"]
    assert todo == subject.SCHEDULED[1:]
    assert note["retained_completed_cases"] == subject.SCHEDULED[:1]
    assert note["disk_recovery"]["unjournaled_reservations"] == {"unlogged": "0.011862125"}


@pytest.mark.parametrize(
    "change",
    [
        {"prior_batch_path": "different"},
        {"absolute_deadline_utc": "2026-10-07T05:00:00+00:00"},
        {
            "conservative_unjournaled_counter_delta": {
                "generations": 0,
                "compacts": 0,
                "outbound": 1,
                "counted_input": 0,
            }
        },
        {"unjournaled_reservations": {}},
        {"reserve_basis": {"counted_input": 29360, "max_output_tokens": 16384}},
        {"last_received_spent_usd": "0.11"},
        {"missing_case_completion": {}},
    ],
)
def test_disk_recovery_contradictions_fail_closed(incident, change):
    prior, audit, target = incident
    write(target, {**audit, **change})
    with pytest.raises(ValueError):
        subject.read_prior(prior, current_sources={})


def test_changed_original_ledger_cannot_be_repaired_by_audit(incident):
    prior, _, _ = incident
    with (prior / subject.SCHEDULED[1] / "provider-trace.jsonl").open("a") as output:
        output.write('{"incomplete":')
    with pytest.raises(ValueError):
        subject.read_prior(prior, current_sources={})


def test_current_original_sources_must_equal_prior_frozen_sources(incident):
    prior, _, _ = incident
    with pytest.raises(ValueError, match="source changed"):
        subject.read_prior(prior, current_sources={"changed": "sha"})


@pytest.mark.parametrize(
    "change",
    [
        {"provider_calls": 1},
        {"credential_read": True},
        {"recovery_server_closed": False},
        {"prior_server_closed": False},
        {"execution_status_counts": {"active": 1}},
    ],
)
def test_non_readonly_or_live_recovery_cannot_open_paid_gate(incident, change):
    prior, audit, target = incident
    metadata = audit["recovery_metadata"]["path"]
    value = json.loads(open(metadata, encoding="utf-8").read())
    write(subject.Path(metadata), {**value, **change})
    updated = deepcopy(audit)
    updated["recovery_metadata"]["sha256"] = subject.file_hash(subject.Path(metadata))
    write(target, updated)
    with pytest.raises(ValueError):
        subject.read_prior(prior, current_sources={})


def test_output_binding_keeps_source_root_and_routes_only_driver_artifacts_to_c():
    from types import SimpleNamespace

    driver = SimpleNamespace(
        __file__=str(subject.HERE / "run_batch.py"), HERE=subject.HERE, ROOT=subject.ROOT
    )
    guard = SimpleNamespace(__file__=str(subject.HERE / "guard.py"))
    subject.bind_output_routes(driver, guard, runtime="3.14.7")
    assert driver.HERE == subject.ARTIFACT_ROOT
    assert driver.ROOT == subject.ROOT
    assert subject.HERE.drive.lower() == "s:"
    assert subject.ARTIFACT_ROOT.drive.lower() == "c:"


@pytest.mark.parametrize("runtime,changed", [("3.14.8", False), ("3.14.7", True)])
def test_changed_runtime_or_imported_driver_fails_before_paid_run(runtime, changed):
    from types import SimpleNamespace

    driver = SimpleNamespace(
        __file__=str(subject.HERE / "run_batch.py"), HERE=subject.HERE, ROOT=subject.ROOT
    )
    guard = SimpleNamespace(__file__=str(subject.HERE / "guard.py"))
    if changed:
        driver.__file__ = str(subject.ARTIFACT_ROOT / "run_batch.py")
    with pytest.raises(RuntimeError, match="source changed"):
        subject.bind_output_routes(driver, guard, runtime=runtime)


def test_frozen_supplement_and_prior_evidence_changes_fail_before_dispatch(tmp_path):

    extra = tmp_path / "completion.py"
    extra.write_text("original", encoding="utf-8")
    prior = tmp_path / "ledger.json"
    prior.write_text("ledger", encoding="utf-8")
    data = {
        "supplement_source_sha256": {str(extra): subject.file_hash(extra)},
        "continuation": {"prior_evidence_sha256": {str(prior): subject.file_hash(prior)}},
    }
    subject.verify_sources(data, lambda _: None)
    extra.write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="supplement source changed"):
        subject.verify_sources(data, lambda _: None)
    extra.write_text("original", encoding="utf-8")
    prior.write_text("changed", encoding="utf-8")
    with pytest.raises(RuntimeError, match="accounting evidence changed"):
        subject.verify_sources(data, lambda _: None)


@pytest.mark.asyncio
async def test_actual_entry_dry_run_never_reads_credential_or_starts_case(
    incident, monkeypatch, capsys
):
    import sys

    sys.path.insert(0, str(subject.HERE))
    import run_batch

    prior_path, _, _ = incident
    original_read = subject.read_prior
    monkeypatch.setattr(
        subject, "read_prior", lambda _: original_read(prior_path, current_sources={})
    )
    monkeypatch.setattr(run_batch, "HERE", subject.HERE)
    monkeypatch.setattr(sys, "argv", ["completion_batch.py", "--dry-run"])

    def forbidden(*args, **kwargs):
        raise AssertionError("Paid operation in dry run")

    monkeypatch.setattr(run_batch, "read_openai_api_key", forbidden)
    monkeypatch.setattr(run_batch, "run_case", forbidden)
    await subject.main()
    output = json.loads(capsys.readouterr().out)
    assert output["credential_read"] is False and output["provider_calls"] == 0
    assert output["remaining_cases"] == subject.SCHEDULED[1:]
    assert output["deadline"] == "2026-10-07T04:30:34+00:00"
    assert run_batch.ROOT == subject.ROOT


@pytest.mark.asyncio
async def test_live_prior_server_rejects_entry_before_credential_or_case(incident, monkeypatch):
    import socket
    import sys

    sys.path.insert(0, str(subject.HERE))
    import run_batch

    prior_path, _, _ = incident
    original_read = subject.read_prior
    monkeypatch.setattr(
        subject, "read_prior", lambda _: original_read(prior_path, current_sources={})
    )
    monkeypatch.setattr(run_batch, "HERE", subject.HERE)
    monkeypatch.setattr(sys, "argv", ["completion_batch.py", "--dry-run"])

    class LiveProbe:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def settimeout(self, timeout):
            pass

        def connect_ex(self, address):
            return 0

    monkeypatch.setattr(socket, "socket", lambda: LiveProbe())
    with pytest.raises(RuntimeError, match="server is still active"):
        await subject.main()


def test_freeze_saves_exact_supplement_source_and_prior_bytes(incident, tmp_path):
    prior_path, _, _ = incident
    _, note, _ = subject.read_prior(prior_path, current_sources={})
    destination = tmp_path / "new-batch/manifest.json"
    destination.parent.mkdir()
    data = subject.freeze_supplement(destination, note, lambda phase, path: {"source_sha256": {}})
    assert data["absolute_deadline_utc"] == subject.DEADLINE.isoformat()
    assert data["limits"] == subject.LIMITS
    assert data["continuation"]["prior_accounting"]["retained_reservations"] == {
        "old": "0.013296750",
        "unlogged": "0.011862125",
    }
    assert data["output_routes"]["source_here"] == str(subject.HERE)
    for relative, expected in data["supplement_source_sha256"].items():
        assert subject.file_hash(destination.parent / "source-snapshot" / relative) == expected
    for original, copied in data["prior_evidence_snapshot"].items():
        assert subject.file_hash(subject.Path(copied)) == subject.file_hash(subject.Path(original))


@pytest.mark.asyncio
async def test_case_exception_saves_aggregate_state_and_keeps_unknown_reserves(
    incident, tmp_path, monkeypatch
):
    import sys

    sys.path.insert(0, str(subject.HERE))
    import run_batch

    prior_path, _, _ = incident
    original_read = subject.read_prior
    state, note, _ = original_read(prior_path, current_sources={})
    monkeypatch.setattr(subject, "read_prior", lambda _: (state, note, subject.SCHEDULED[1:2]))
    monkeypatch.setattr(subject, "ARTIFACT_ROOT", tmp_path)
    monkeypatch.setattr(run_batch, "HERE", subject.HERE)
    monkeypatch.setattr(sys, "argv", ["completion_batch.py", "--batch-name", "fixture-batch"])
    monkeypatch.setattr(subject, "verify_sources", lambda *args: None)

    def fixture_freeze(destination, note, base_freeze):
        write(destination, {"fixture": True})
        return {"fixture": True}

    monkeypatch.setattr(subject, "freeze_supplement", fixture_freeze)

    async def stopped(*args):
        raise RuntimeError("Fixture resource interruption")

    monkeypatch.setattr(run_batch, "run_case", stopped)
    with pytest.raises(RuntimeError, match="Fixture resource"):
        await subject.main()
    saved = subject.read_json(tmp_path / "fixture-batch/batch-state.json")
    assert saved["guard"]["spent_usd"] == state["spent_usd"]
    assert saved["guard"]["retained_reservations"] == state["retained_reservations"]
    assert saved["all_scheduled_cases"] == subject.SCHEDULED
    assert saved["completed_cases"] == subject.SCHEDULED[:1]
