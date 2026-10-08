"""Offline counterexamples for bounded carrier, exact prompt and submitted facts."""

import asyncio
import importlib.util
import json
import sys
from argparse import Namespace
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx2
import pytest

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "apps/api/src"))
spec = importlib.util.spec_from_file_location(
    "priority_probe_core", HERE / "priority-probe-core.py"
)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def prior():
    return {
        "spent_usd": "1.2",
        "occupied_usd": "1.5",
        "retained_reservations": {"first": "0.1", "second": "0.2"},
        "generations": 25,
        "compacts": 1,
        "outbound": 50,
        "counted_input": 120000,
        "stop_reason": None,
    }


def test_exact_single_bullet_is_replaced_and_rest_is_preserved():
    source = (ROOT / "apps/api/src/caliburn/agents/job_consultant/instructions.py").read_bytes()
    changed = core.replace_candidate(source)
    assert len(changed) == len(source) + 156
    assert changed != source
    assert changed.replace(core.AFTER, core.BEFORE, 1) == source
    assert len(core.BEFORE) == 315 and len(core.AFTER) == 471


def test_carrier_retains_both_unknown_reserves_and_does_not_reset_counters():
    guard = core.carried_guard(prior(), now=datetime(2026, 10, 7, 7, tzinfo=UTC), clock=lambda: 100)
    assert guard.occupied == Decimal("1.5")
    assert guard.attempts == {"first": Decimal("0.1"), "second": Decimal("0.2")}
    assert guard.generations == 25
    assert guard.limit == Decimal("2.0")
    assert guard.max_generations == 281
    assert guard.max_outbound == 650


@pytest.mark.parametrize(
    ("key", "attribute", "global_limit"),
    [
        ("generations", "max_generations", 3000),
        ("outbound", "max_outbound", 7000),
        ("counted_input", "max_counted_input", 180000000),
        ("compacts", "max_compacts", 32),
    ],
)
def test_probe_increment_cannot_extend_original_global_counter_cap(key, attribute, global_limit):
    state = {**prior(), key: global_limit - 1}
    guard = core.carried_guard(state, now=datetime(2026, 10, 7, 7, tzinfo=UTC))
    assert getattr(guard, key) == global_limit - 1
    assert getattr(guard, attribute) == global_limit


@pytest.mark.parametrize(
    ("key", "global_limit"),
    [("generations", 3000), ("outbound", 7000), ("counted_input", 180000000), ("compacts", 32)],
)
@pytest.mark.parametrize("overage", [0, 1])
def test_exhausted_original_global_counter_rejects_probe_before_outbound(
    key, global_limit, overage
):
    state = {**prior(), key: global_limit + overage}
    with pytest.raises(ValueError, match="Cumulative counter exhausted"):
        core.carried_guard(state, now=datetime(2026, 10, 7, 7, tzinfo=UTC))


def test_unused_last_selection_cannot_be_claimed_as_an_original():
    selected = {"answer": "只可在送出後算原話", "actually_submitted": False}
    originals = [
        {
            "speaker": "employee",
            "interview_text": selected["answer"],
            "source_id": "earlier",
        }
    ]
    assert core.eligible_sources(selected, originals) == []


def test_only_matching_submitted_answer_is_eligible():
    selected = {
        "answer": "已送出答案",
        "actually_submitted": True,
        "prior_source_ids": ["old"],
    }
    originals = [
        {"speaker": "employee", "interview_text": "已送出答案", "source_id": "old"},
        {"speaker": "employee", "interview_text": "已送出答案", "source_id": "new"},
        {
            "speaker": "consultant",
            "interview_text": "已送出答案",
            "source_id": "consultant",
        },
    ]
    assert core.eligible_sources(selected, originals) == ["new"]


def test_duplicate_or_missing_bullet_fails_closed():
    with pytest.raises(ValueError):
        core.replace_candidate(b"no bullet")
    with pytest.raises(ValueError):
        core.replace_candidate(core.BEFORE + core.BEFORE)


def test_absolute_deadline_and_usd8_cannot_be_extended():
    with pytest.raises(ValueError):
        core.carried_guard(prior(), now=core.DEADLINE)
    state = {**prior(), "spent_usd": "7.6", "occupied_usd": "7.9"}
    assert core.carried_guard(state, now=datetime(2026, 10, 7, 7, tzinfo=UTC)).limit == Decimal(8)


def test_forty_five_minutes_starts_once_and_never_extends_absolute_deadline():
    clock = [100.0]
    guard = core.carried_guard(
        prior(), now=datetime(2026, 10, 7, 7, tzinfo=UTC), clock=lambda: clock[0]
    )
    assert guard.seconds == 2700
    assert guard.started is None
    clock[0] = 1000.0
    guard.check({"model": "gpt-6-luna"})
    assert guard.started == 1000
    clock[0] = 3700.0
    with pytest.raises(RuntimeError, match="deadline"):
        guard.check({"model": "gpt-6-luna"})
    near = core.carried_guard(prior(), now=datetime(2026, 10, 7, 8, 25, 34, tzinfo=UTC))
    assert near.seconds == 300


def test_instruction_freeze_accepts_actual_strip_constant():
    source = (
        ROOT / "apps/api/src/caliburn/agents/job_consultant/reference_instructions.py"
    ).read_bytes()
    value = core.constant(source, "OCCUPATION_REFERENCE_INSTRUCTIONS")
    assert "公版" in value
    assert value == value.strip()


def test_additional_counters_are_finite_and_count_call_cost_is_admitted():
    guard = core.carried_guard(prior(), now=datetime(2026, 10, 7, 7, tzinfo=UTC), clock=lambda: 100)
    guard.outbound = guard.max_outbound
    with pytest.raises(RuntimeError, match="outbound"):
        guard.outbound_attempt({"model": "gpt-6-luna"})
    guard = core.carried_guard(prior(), now=datetime(2026, 10, 7, 7, tzinfo=UTC), clock=lambda: 100)
    guard.spent = guard.limit - sum(guard.attempts.values())
    with pytest.raises(RuntimeError, match="Count-call"):
        guard.reserve_count()
    assert guard.attempts == {"first": Decimal("0.1"), "second": Decimal("0.2")}


class FakeCountTransport(httpx2.AsyncBaseTransport):
    def __init__(self, tokens):
        self.tokens = tokens
        self.calls = []

    async def handle_async_request(self, request):
        self.calls.append(request.url.path)
        assert request.url.path == "/v1/responses/input_tokens"
        return httpx2.Response(200, json={"input_tokens": self.tokens})


def count_transport_fixture(tokens):
    directory = core.OUTPUT_ROOT / ("priority-probe-count-test-" + uuid4().hex)
    directory.mkdir(parents=True)
    guard = core.carried_guard(prior(), now=datetime(2026, 10, 7, 7, tzinfo=UTC), clock=lambda: 100)
    inner = FakeCountTransport(tokens)
    journal = directory / "trace.jsonl"
    transport = core.ProbeTransport(guard, inner, journal)
    payload = {
        "model": "gpt-6-luna",
        "input": [{"role": "user", "content": "synthetic count boundary"}],
        "reasoning": {"effort": "high"},
        "service_tier": "default",
        "max_output_tokens": 16384,
    }
    return guard, inner, transport, payload, journal


def test_successful_remote_count_crossing_cap_is_preserved_and_blocks_generation():
    guard, inner, transport, payload, journal = count_transport_fixture(2)
    guard.counted_input = guard.max_counted_input - 1

    async def scenario():
        async with httpx2.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="counted input token limit"):
                await client.post("https://api.openai.com/v1/responses/input_tokens", json=payload)
            with pytest.raises(RuntimeError, match="counted input token limit"):
                await client.post("https://api.openai.com/v1/responses", json=payload)

    asyncio.run(scenario())
    records = (
        [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        if journal.exists()
        else []
    )
    counts = [record for record in records if record["event"] == "count"]
    assert inner.calls == ["/v1/responses/input_tokens"]
    assert guard.generations == prior()["generations"]
    assert guard.outbound == prior()["outbound"] + 1
    assert (
        guard.state()["counted_input"],
        [record["input_tokens"] for record in counts],
        [record["counted_input"] for record in counts],
    ) == (guard.max_counted_input + 1, [2], [guard.max_counted_input + 1])
    assert guard.stop_reason == "batch counted input token limit reached"
    assert guard.spent == Decimal(prior()["spent_usd"]) + Decimal("0.0001")
    assert guard.attempts == {"first": Decimal("0.1"), "second": Decimal("0.2")}
    with pytest.raises(RuntimeError, match="counted input token limit"):
        guard.count(payload, 2)
    assert guard.counted_input == guard.max_counted_input + 1


def test_normal_remote_count_is_counted_and_recorded_once():
    guard, inner, transport, payload, journal = count_transport_fixture(2)

    async def scenario():
        async with httpx2.AsyncClient(transport=transport) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses/input_tokens", json=payload
            )
            assert response.status_code == 200 and response.json()["input_tokens"] == 2

    asyncio.run(scenario())
    records = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    assert inner.calls == ["/v1/responses/input_tokens"]
    assert guard.counted_input == prior()["counted_input"] + 2
    assert [record["input_tokens"] for record in records if record["event"] == "count"] == [2]
    assert guard.stop_reason is None


@pytest.mark.parametrize("tokens", [True, -1, "2", 1.5, None])
def test_invalid_remote_count_is_rejected_without_count_or_generation(tokens):
    guard, inner, transport, payload, journal = count_transport_fixture(tokens)

    async def scenario():
        async with httpx2.AsyncClient(transport=transport) as client:
            with pytest.raises(RuntimeError, match="invalid count"):
                await client.post("https://api.openai.com/v1/responses/input_tokens", json=payload)
            with pytest.raises(RuntimeError, match="no matching input count"):
                await client.post("https://api.openai.com/v1/responses", json=payload)

    asyncio.run(scenario())
    records = (
        [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
        if journal.exists()
        else []
    )
    assert inner.calls == ["/v1/responses/input_tokens"]
    assert guard.counted_input == prior()["counted_input"]
    assert guard.generations == prior()["generations"]
    assert all(record["event"] != "count" for record in records)


def test_no_keyword_or_fixed_turn_can_select_a_private_answer():
    policy = core.read_json(HERE / "reply-policy.json")
    question = "在什麼地方做？"
    with pytest.raises(ValueError):
        core.validate_selection(
            {"answer_kind": "target_answer"}, question, policy, "warehouse_environment"
        )
    decision = {
        "answer_kind": "target_answer",
        "question_quote": question,
        "reason": "已中立詢問場所",
        "review_method": "semantic_review",
    }
    assert (
        core.validate_selection(decision, question, policy, "warehouse_environment")
        == policy["answers"]["warehouse_environment"]["target_answer"]
    )
    decision["question_quote"] = "另一題"
    with pytest.raises(ValueError):
        core.validate_selection(decision, question, policy, "warehouse_environment")


def test_schedule_stays_24_initial_and_48_max_with_no_oracle_in_public_cases():
    cases = core.build_cases()
    schedule = core.next_schedule()
    assert len(cases) == 6 and len(schedule) == 24
    assert (
        sum(
            dict(zip(core.CASE_KEYS, cases, strict=True))[t["case_key"]]["max_turns"]
            for t in schedule
        )
        == 48
    )
    policy = core.read_json(HERE / "reply-policy.json")
    public = json.dumps(cases, ensure_ascii=False)
    assert all(a["target_answer"] not in public for a in policy["answers"].values())
    assert all("criteria" not in case for case in cases)


def test_private_answer_and_labels_are_blocked_until_answer_is_submitted():
    arguments = {
        "expected_instructions": "method",
        "private_answers": ["private"],
        "disclosed": set(),
    }
    with pytest.raises(ValueError):
        core.inspect_public_request({"instructions": "method", "input": "private"}, **arguments)
    core.inspect_public_request({"instructions": "method", "input": "visible"}, **arguments)
    arguments["disclosed"].add("private")
    core.inspect_public_request({"instructions": "method", "input": "private"}, **arguments)
    with pytest.raises(ValueError):
        core.inspect_public_request({"input": "warehouse_errors"}, **arguments)
    with pytest.raises(ValueError):
        core.inspect_public_request({"instructions": "other"}, **arguments)


def test_quality_gate_requires_complete_study_four_locked_hashes_and_both_reserves():
    # Python 3.14's Windows mode=0o700 tmp fixture hits the sandbox ACL. This
    # small, owned artifact uses normal mkdir permissions and is retained.
    tmp_path = core.OUTPUT_ROOT / ("priority-probe-offline-test-" + uuid4().hex)
    tmp_path.mkdir(parents=True)
    ledger = tmp_path / "ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "guard": prior(),
                "completed_cases": core.STUDY_CASES,
                "all_scheduled_cases": core.STUDY_CASES,
            }
        ),
        encoding="utf-8",
    )
    reviews = []
    for index in range(4):
        review = tmp_path / f"review{index}.json"
        review.write_text("{}", encoding="utf-8")
        reviews.append({"path": str(review), "sha256": core.file_hash(review), "locked": True})
    lock = tmp_path / "lock.json"
    data = {
        "all_quality_locked": True,
        "ledger_sha256": core.file_hash(ledger),
        "case_ids": core.STUDY_CASES,
        "reviews": reviews,
        "inherited_guard": prior(),
    }
    lock.write_text(json.dumps(data), encoding="utf-8")
    assert core.carrier(ledger, lock) == prior()
    data["reviews"][0]["locked"] = False
    lock.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        core.carrier(ledger, lock)
    data["reviews"][0]["locked"] = True
    data["inherited_guard"]["retained_reservations"] = {"first": "0.1"}
    lock.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        core.carrier(ledger, lock)


def test_actual_prepare_freezes_sources_without_credentials_or_database(monkeypatch):
    runner = core.load_module("priority_probe_offline_runner", HERE / "priority-probe-run.py")
    driver = runner.shared()

    def blocked(*args, **kwargs):
        pytest.fail("Offline preparation tried credential or database access")

    monkeypatch.setattr(driver, "database_settings", blocked)
    monkeypatch.setattr(driver, "read_openai_api_key", blocked)
    monkeypatch.setattr(driver.psycopg, "connect", blocked)
    monkeypatch.setattr(driver, "create_engine", blocked)
    monkeypatch.setattr(driver.subprocess, "run", blocked)
    monkeypatch.setattr(runner, "owned_database", blocked)
    monkeypatch.setattr(runner, "shared", lambda: driver)
    parent = core.OUTPUT_ROOT / ("priority-probe-offline-carrier-" + uuid4().hex)
    parent.mkdir(parents=True)
    ledger = parent / "mock-ledger.json"
    ledger.write_text(
        json.dumps(
            {
                "guard": prior(),
                "completed_cases": core.STUDY_CASES,
                "all_scheduled_cases": core.STUDY_CASES,
            }
        ),
        encoding="utf-8",
    )
    reviews = []
    for index in range(4):
        review = parent / f"mock-review-{index}.json"
        review.write_text("{}", encoding="utf-8")
        reviews.append({"path": str(review), "sha256": core.file_hash(review), "locked": True})
    lock = parent / "mock-lock.json"
    lock.write_text(
        json.dumps(
            {
                "all_quality_locked": True,
                "ledger_sha256": core.file_hash(ledger),
                "case_ids": core.STUDY_CASES,
                "reviews": reviews,
                "inherited_guard": prior(),
            }
        ),
        encoding="utf-8",
    )
    args = Namespace(
        ledger=str(ledger),
        quality_lock=str(lock),
        name="priority-probe-offline-prepare-" + uuid4().hex,
        offline_only=True,
    )
    runner.prepare(args)
    output = runner.output_path(args.name)
    manifest = core.read_json(output / "manifest.json")
    assert manifest["offline_only"] is True and len(manifest["files"]) > 300
    for path in (
        "docs/guides/2026-09-09-complete-work-analysis-guide.md",
        "docs/guides/2026-09-09-customized-jd-depth-and-interview-calibration.md",
        "docs/guides/2026-09-09-jd-field-and-writing-guide.md",
        "apps/api/alembic.ini",
        "apps/api/pyproject.toml",
    ):
        assert manifest["files"][path] == core.file_hash(ROOT / path)
    migration = driver.migration_config()
    assert migration.config_file_name is None
    assert migration.get_main_option("script_location") == "caliburn:migrations"
    assert (
        manifest["instructions"]["B1"].encode().replace(core.AFTER, core.BEFORE)
        == manifest["instructions"]["B0"].encode()
    )
    for arm in ("B0", "B1"):
        method = (
            manifest["instructions"][arm]
            + "\n\n"
            + manifest["common_focus"]
            + "\n\n"
            + manifest["reference_instructions"]
        )
        core.inspect_public_request(
            {"instructions": method, "input": manifest["cases"]},
            expected_instructions=method,
            private_answers=[
                value["target_answer"] for value in manifest["reply_policy"]["answers"].values()
            ],
            disclosed=set(),
            private_criteria=tuple(
                text for value in manifest["assessments"].values() for text in value["criteria"]
            ),
        )
    runner.verify(manifest)
    with pytest.raises(ValueError, match="Offline preparation"):
        runner.execute(args)
    assert not (output / "started.json").exists()
    runner.save_new(
        parent / "priority-probe-offline-evidence.json",
        {
            "preparation": str(output),
            "frozen_files": len(manifest["files"]),
            "provider_calls": 0,
            "credential_read": False,
            "database_connected": False,
            "execute_blocked": True,
        },
    )


def test_only_exact_owned_container_can_supply_database_settings(monkeypatch):
    runner = core.load_module("priority_probe_database_test", HERE / "priority-probe-run.py")
    driver = runner.shared()
    value = {
        "Id": "13cf811f4c8bf4ff395339fbdf89e6f444971d3fd718fddb84862c68580c07ee",
        "Name": "/caliburn-intplan-postgres-20261007",
        "State": {"Running": True},
        "Config": {
            "Env": [
                "POSTGRES_USER=intplan_test",
                "POSTGRES_DB=caliburn_intplan_test",
                "POSTGRES_PASSWORD=offline-fixture",
            ]
        },
        "NetworkSettings": {"Ports": {"5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55447"}]}},
    }
    calls = []

    def inspect(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(stdout=json.dumps([value]))

    monkeypatch.setattr(driver.subprocess, "run", inspect)
    database = runner.owned_database(driver, "priority_probe_offline")
    assert database.schema == "priority_probe_offline"
    assert "127.0.0.1:55447/caliburn_intplan_test" in database.url
    assert calls == [["docker", "inspect", value["Id"]]]
    value["Name"] = "/another-container"
    with pytest.raises(ValueError, match="identity mismatch"):
        runner.owned_database(driver, "priority_probe_offline")


def test_private_quality_criteria_and_before_jd_do_not_enter_public_cases_or_request():
    public = json.dumps(core.build_cases(), ensure_ascii=False)
    for label in (
        "warehouse_environment",
        "warehouse_errors",
        "warehouse_load",
        "unknown_is_not_unexplored",
        "refused",
        "excluded",
        "B0",
        "B1",
    ):
        assert label not in public
    policy = core.read_json(HERE / "reply-policy.json")
    assessments = core.build_assessments(policy)
    original = core.read_json(HERE.parent / "jd-condition-exploration-2026-10-07/cases.json")
    original_by_id = {case["case_id"]: case for case in original["cases"]}
    for key in core.CASE_KEYS[:4]:
        assert assessments[key]["criteria"] == original_by_id[key]["criteria"]
    assert assessments["refused"]["criteria"] != assessments["warehouse_errors"]["criteria"]
    assert assessments["excluded"]["criteria"] != assessments["warehouse_errors"]["criteria"]
    private_criteria = tuple(text for value in assessments.values() for text in value["criteria"])
    assert all(text not in public for text in private_criteria)
    arguments = {
        "expected_instructions": "method",
        "private_answers": [],
        "disclosed": set(),
        "private_criteria": private_criteria,
    }
    core.inspect_public_request({"instructions": "method", "input": "公開原話"}, **arguments)
    with pytest.raises(ValueError, match="assessment"):
        core.inspect_public_request(
            {"instructions": "method", "input": private_criteria[0]}, **arguments
        )
    before = {"work": {"tasks": [{"task_id": "same-id", "description": "既有工作"}]}}
    final = {"work": {"tasks": [{"task_id": "same-id", "description": "既有工作；已確認條件"}]}}
    quality = core.quality_bundle(
        opaque_id="anonymous",
        starting_formal_jd=before,
        starting_sources={"entries": ["before citation"]},
        formal_jd=final,
        assessment=assessments["warehouse_environment"],
        interviews={"messages": []},
        trial_replies=[],
        fixed_sources={"entries": ["final citation"]},
    )
    assert quality["starting_formal_jd"] == before and quality["formal_jd"] == final
    assert (
        quality["assessment"]["target"]
        == policy["answers"]["warehouse_environment"]["target_answer"]
    )
    assert quality["assessment"]["criteria"] == assessments["warehouse_environment"]["criteria"]
    assert quality["starting_fixed_source_contents"]["entries"] == ["before citation"]
    assert not {"arm", "repeat", "case_key", "case_id", "trial"} & quality.keys()
    quality_json = json.dumps(quality, ensure_ascii=False)
    assert all(
        label not in quality_json for label in ("warehouse_environment", "B0", "B1", "c01-r1")
    )


def test_answer_packet_contains_original_frozen_neutral_disclosure_policy():
    policy = core.read_json(HERE / "reply-policy.json")
    question = "所以你都是在冷藏區做嗎？"
    packet = core.answer_review_packet(
        opaque_id="anonymous",
        question_quote=question,
        originals=[{"speaker": "employee", "interview_text": "我負責收貨和上架。"}],
        policy=policy,
        case_key="warehouse_environment",
    )
    assert packet["answer_policy_rule"] == policy["rule"]
    assert packet["question_quote"] == question
    assert (
        packet["answer_options"]["target_answer"]
        == policy["answers"]["warehouse_environment"]["target_answer"]
    )
    assert not {"arm", "repeat", "case_key", "criteria"} & packet.keys()
