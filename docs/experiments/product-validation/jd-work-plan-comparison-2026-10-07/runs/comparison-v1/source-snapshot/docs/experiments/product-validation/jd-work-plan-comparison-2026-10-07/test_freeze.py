"""Offline source/capability/accounting isolation checks."""

import json
import sys
from decimal import Decimal
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from controls import BatchGuard
from frozen_manifest import ROOT, arm_templates, database_locator, freeze, sha, verify
from runner import guard_from_ledger, run_case, write_blind_bundle


def test_plan_is_only_ordered_tool_difference_and_changes_is_identical():
    templates = arm_templates()
    common_tools = [
        tool
        for tool in templates["P2"]["tools"]
        if tool["name"] not in {"read_interview_plan", "edit_interview_plan"}
    ]
    assert common_tools == templates["P1"]["tools"]
    changes = [
        [
            tool
            for tool in templates[group]["tools"]
            if tool["name"] == "read_jd_changes"
        ]
        for group in ["P1", "P2"]
    ]
    assert changes[0] and changes[0] == changes[1]


def test_actual_p1_plan_data_and_drifted_tools_are_blocked():
    guard = BatchGuard(limit=Decimal(4))
    guard.templates = arm_templates()
    guard.group = "P1"
    payload = {
        "model": "gpt-6-luna",
        **guard.templates["P1"],
        "input": [
            {
                "role": "user",
                "content": '{"data_kind":"consultant_interview_plan","plan":"hidden"}',
            }
        ],
    }
    with pytest.raises(RuntimeError, match="Plan context"):
        guard.outbound_attempt(payload)
    assert guard.outbound == 0


def test_freeze_archives_new_material_and_verifies_exact_bytes(tmp_path):
    path = tmp_path / "manifest.json"
    data = freeze(
        path,
        limit_usd="4.00",
        authorization_reference="本輪使用者授權，root採US$4上界",
        database_url="postgresql://caliburn@127.0.0.1:55448/caliburn_workplan_test",
    )
    verify(data)
    for name in [
        "runner.py",
        "journey.py",
        "private_facts.json",
        "disclosure-policy.md",
        "blind-jd-rubric.md",
        "protocol.md",
    ]:
        relative = (HERE / name).relative_to(ROOT).as_posix()
        assert (
            sha(tmp_path / "source-snapshot" / relative)
            == data["source_sha256"][relative]
        )
    assert data["limits"]["batch_deadline"] is None
    assert "@" not in data["database"]
    data["source_sha256"][
        (HERE / "private_facts.json").relative_to(ROOT).as_posix()
    ] = "0" * 64
    with pytest.raises(RuntimeError, match="Frozen source"):
        verify(data)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://localhost/db_test",
        "postgresql://127.0.0.1/caliburn",
        "postgresql://8.8.8.8/db_test",
        "https://127.0.0.1/db_test",
    ],
)
def test_isolation_rejects_unapproved_database(url):
    with pytest.raises(ValueError, match="loopback"):
        database_locator(url)


def test_cumulative_accounting_never_resets_unknown_reserve(tmp_path):
    (tmp_path / "ledger.json").write_text(
        json.dumps(
            {
                "guard": {
                    "stop_reason": None,
                    "retained_reservations": {"unknown": "0.5"},
                }
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="unknown accounting"):
        guard_from_ledger(
            tmp_path,
            {
                "limits": {
                    "limit_usd": "4",
                    "max_generations": 2600,
                    "max_compacts": 32,
                    "max_outbound": 6000,
                    "max_counted_input": 150000000,
                },
                "arm_templates": arm_templates(),
            },
        )


def test_missing_ledger_with_prior_case_originals_cannot_restart_at_zero(tmp_path):
    case = tmp_path / "pilot" / "warehouse-r1-P1"
    case.mkdir(parents=True)
    (case / "provider-trace.jsonl").write_text(
        '{"event":"admitted"}\n', encoding="utf-8"
    )
    with pytest.raises(RuntimeError, match="missing"):
        guard_from_ledger(
            tmp_path,
            {
                "limits": {
                    "limit_usd": "4",
                    "max_generations": 2600,
                    "max_compacts": 32,
                    "max_outbound": 6000,
                    "max_counted_input": 150000000,
                },
                "arm_templates": arm_templates(),
            },
        )


def test_anonymous_bundle_has_public_edit_and_no_operational_arm_data(tmp_path):
    case = tmp_path / "warehouse-r1-P2"
    case.mkdir()

    def save(name, body):
        (case / name).write_text(json.dumps(body), encoding="utf-8")

    save(
        "formal-interviews.json",
        {
            "messages": [
                {
                    "source_id": "source",
                    "interview_sequence": 1,
                    "speaker": "employee",
                    "interview_text": "公开原話",
                }
            ]
        },
    )
    save("formal-jd.json", {"revision": "formal"})
    save("fixed-source-contents.json", {"formal_revision_id": "formal", "entries": []})
    save(
        "manual-edit.json",
        {
            "status": "saved",
            "public_initial": "公開初始原話",
            "required_text": "公開修訂",
            "diff": {"before_revision": "1", "after_revision": "2"},
            "decision": {"reason": "anonymous"},
        },
    )
    blind = tmp_path / "blind-input"
    write_blind_bundle(case, blind, tmp_path / "blind-map.json")
    bundle = json.loads(next(blind.glob("*.json")).read_text(encoding="utf-8"))
    assert bundle["public_manual_edit"]["status"] == "saved"
    assert not {"group", "arm", "plan", "cost", "guard", "decision"} & bundle.keys()
    assert "warehouse-r1-P2" not in json.dumps(bundle)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "tool_status,memory,reason",
    [
        ("rejected", {}, "Plan tool rejection"),
        ("updated", {"failed": 1}, "Memory settlement"),
    ],
)
async def test_formal_mechanism_failure_stops_even_with_nonempty_adopted_plan(
    tmp_path, monkeypatch, tool_status, memory, reason
):
    import runner

    async def observed_case(phase, profile, group, repeat, case, guard, frozen, turns):
        case.mkdir()
        (case / "result.json").write_text(
            json.dumps(
                {"turns": [{"status": "completed"}], "memory_settlement": memory}
            ),
            encoding="utf-8",
        )
        (case / "turn-01-result.json").write_text(
            json.dumps({"plan": {"plan": "非空工作計畫"}}), encoding="utf-8"
        )
        (case / "provider-trace.jsonl").write_text(
            json.dumps(
                {
                    "event": "admitted",
                    "role": "A",
                    "input": [
                        {
                            "type": "function_call",
                            "call_id": "edit",
                            "name": "edit_interview_plan",
                        },
                        {
                            "type": "function_call_output",
                            "call_id": "edit",
                            "output": json.dumps(
                                {"status": tool_status, "diff": "saved"}
                            ),
                        },
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )

    monkeypatch.setattr(runner.legacy, "run_case", observed_case)
    monkeypatch.setattr(runner, "write_blind_bundle", lambda *args: None)
    guard = BatchGuard(limit=Decimal(4))
    await run_case(
        "formal",
        "warehouse",
        "P2",
        1,
        tmp_path / "warehouse-r1-P2",
        guard,
        {"turn_limits": {"formal": 20}},
    )
    assert guard.stop_reason and reason in guard.stop_reason
