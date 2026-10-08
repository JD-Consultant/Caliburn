"""Finite isolated formal-HTTP probe. Dry-run/prepare never read credentials or DB.

Execute is a root-only explicit command after all study quality is locked. Private
answers are selected in anonymous external semantic review files, never by keywords.
All snapshots, traces, decisions and final originals stay in the approved C root.
"""

import argparse
import asyncio
import copy
import json
import platform
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any
from uuid import UUID, uuid4

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "apps/api/src"))
import importlib.util

spec = importlib.util.spec_from_file_location(
    "priority_probe_core", HERE / "priority-probe-core.py"
)
core = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = core
spec.loader.exec_module(core)


def save_new(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, default=str)
        stream.flush()


def shared() -> ModuleType:
    return core.load_module(
        "priority_probe_shared_driver",
        HERE.parent / "jd-analysis-followup-2026-10-06/run_comparison.py",
    )


def output_path(name: str) -> Path:
    if re.fullmatch(r"priority-probe-[a-z0-9_-]{1,48}", name) is None:
        raise ValueError("Invalid probe output name")
    return core.OUTPUT_ROOT / name


def owned_database(driver: ModuleType, schema: str) -> Any:
    """Only root execute inspects credentials of the exact owned test container."""
    container_id = "13cf811f4c8bf4ff395339fbdf89e6f444971d3fd718fddb84862c68580c07ee"
    inspected = driver.subprocess.run(
        ["docker", "inspect", container_id],
        check=True,
        capture_output=True,
        encoding="utf-8",
    )
    value = json.loads(inspected.stdout)[0]
    environment = dict(item.split("=", 1) for item in value["Config"]["Env"])
    ports = value["NetworkSettings"]["Ports"]["5432/tcp"]
    if (
        value["Id"] != container_id
        or value["Name"] != "/caliburn-intplan-postgres-20261007"
        or value["State"]["Running"] is not True
        or {(item["HostIp"], item["HostPort"]) for item in ports}
        != {("127.0.0.1", "55447")}
        or environment.get("POSTGRES_USER") != "intplan_test"
        or environment.get("POSTGRES_DB") != "caliburn_intplan_test"
    ):
        raise ValueError("Owned INTPLAN database identity mismatch")
    url = driver.URL.create(
        "postgresql",
        username="intplan_test",
        password=environment["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=55447,
        database="caliburn_intplan_test",
    ).render_as_string(hide_password=False)
    return driver.DatabaseSettings(url=url, schema=schema)


def dry_data(args: argparse.Namespace) -> dict[str, Any]:
    source = (
        ROOT / "apps/api/src/caliburn/agents/job_consultant/instructions.py"
    ).read_bytes()
    candidate = core.replace_candidate(source)
    gate = "missing ledger or quality lock"
    prior = None
    if args.ledger and args.quality_lock:
        try:
            prior = core.carrier(args.ledger, args.quality_lock)
            core.carried_guard(prior)
            gate = None
        except (ValueError, KeyError, FileNotFoundError) as error:
            gate = type(error).__name__ + ": " + str(error)
    return {
        "provider_calls": 0,
        "credential_read": False,
        "database_connected": False,
        "trials": len(core.next_schedule()),
        "max_effective_replies": 48,
        "prompt_byte_delta": len(candidate) - len(source),
        "paid_gate_failure": gate,
        "prior_guard": prior,
        "additional_limits": core.COUNTERS,
        "additional_usd": "0.50",
        "global_usd": "8.00",
        "absolute_deadline_utc": core.DEADLINE.isoformat(),
        "output_root": str(core.OUTPUT_ROOT),
    }


def prepare(args: argparse.Namespace) -> None:
    prior = core.carrier(args.ledger, args.quality_lock)
    core.carried_guard(prior)
    driver = shared()
    output = output_path(args.name)
    if output.resolve().parent != core.OUTPUT_ROOT.resolve():
        raise ValueError("Only a direct named probe directory is allowed")
    source = (ROOT / driver.PROMPT_PATH).read_bytes()
    prompts = {
        "B0": core.constant(source, "CONSULTANT_INSTRUCTIONS"),
        "B1": core.constant(core.replace_candidate(source), "CONSULTANT_INSTRUCTIONS"),
    }
    paths = [
        *HERE.glob("priority-probe-*.py"),
        *HERE.glob("priority-probe-*.md"),
        HERE / "2026-10-07-priority-candidate-protocol.md",
        HERE / "case-overrides.json",
        HERE / "reply-policy.json",
        HERE.parent / "jd-condition-exploration-2026-10-07/cases.json",
        Path(driver.__file__),
        ROOT / "apps/api/uv.lock",
        ROOT / "apps/api/pyproject.toml",
        ROOT / "apps/api/alembic.ini",
        ROOT / "docs/guides/2026-09-09-complete-work-analysis-guide.md",
        ROOT
        / "docs/guides/2026-09-09-customized-jd-depth-and-interview-calibration.md",
        ROOT / "docs/guides/2026-09-09-jd-field-and-writing-guide.md",
        ROOT / "apps/api/tests/unit/test_occupation_reference_client.py",
        core.INTPLAN / "guard.py",
        core.INTPLAN / "append_stream.py",
        core.INTPLAN / "evidence.py",
        HERE.parent / "full-interview-rag-2026-10-06/batch_guard.py",
        HERE.parent / "early-interview-recall-2026-10-05/study_guard.py",
        HERE.parent / "early-interview-recall-2026-10-05/study_manifest.py",
    ]
    paths += [
        p
        for p in (ROOT / "apps/api/src/caliburn").rglob("*")
        if p.suffix in {".py", ".json", ".html"}
    ]
    files = driver.freeze_files(paths, root=ROOT, output=output)
    common = core.constant(
        (
            ROOT
            / "apps/api/src/caliburn/agents/job_consultant/planning_instructions.py"
        ).read_bytes(),
        "FOCUS_INSTRUCTIONS",
    )
    reference = core.constant(
        (ROOT / driver.REFERENCE_PATH).read_bytes(), "OCCUPATION_REFERENCE_INSTRUCTIONS"
    )
    manifest = {
        "files": files,
        "instructions": prompts,
        "common_focus": common,
        "reference_instructions": reference,
        "tools": driver.consultant_tool_definitions(
            occupation_references_enabled=True, interview_plans_enabled=False
        ),
        "model": "gpt-6-luna",
        "effort": "high",
        "max_output_tokens": 16384,
        "provider": "https://api.openai.com",
        "service_tier": "default",
        "runtime": platform.python_version(),
        "cases": core.build_cases(),
        "schedule": core.next_schedule(),
        "reference_fixture": driver.reference_fixture(),
        "reply_policy": core.read_json(HERE / "reply-policy.json"),
        "assessments": core.build_assessments(
            core.read_json(HERE / "reply-policy.json")
        ),
        "ledger": str(Path(args.ledger).resolve()),
        "ledger_sha256": core.file_hash(args.ledger),
        "quality_lock": str(Path(args.quality_lock).resolve()),
        "quality_lock_sha256": core.file_hash(args.quality_lock),
        "prior_guard": prior,
        "additional_limits": core.COUNTERS,
        "max_effective_replies": 48,
        "absolute_deadline_utc": core.DEADLINE.isoformat(),
        "notes_enabled": False,
        "offline_only": args.offline_only,
        "scope": "same frozen public prefix/JD/empty Memory; semantic adaptive replies; formal HTTP JD/source reads",
    }
    save_new(output / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "prepared": str(output),
                "frozen_files": len(files),
                "provider_calls": 0,
                "credential_read": False,
                "database_connected": False,
            }
        )
    )


def verify(manifest: dict[str, Any]) -> None:
    core.verify_frozen(manifest)
    if (
        core.file_hash(manifest["ledger"]) != manifest["ledger_sha256"]
        or core.file_hash(manifest["quality_lock"]) != manifest["quality_lock_sha256"]
    ):
        raise ValueError("Study carrier or quality lock changed")
    if (
        core.carrier(manifest["ledger"], manifest["quality_lock"])
        != manifest["prior_guard"]
    ):
        raise ValueError("Carrier state changed")


async def wait_decision(
    output: Path,
    opaque: str,
    question: str,
    case: str,
    policy: dict[str, Any],
    guard: core.ProbeGuard,
) -> tuple[str | None, dict[str, Any], str]:
    path = output / "decisions" / (opaque + ".json")
    while not path.exists():
        guard.check({"model": "gpt-6-luna"})
        await asyncio.sleep(1)
    decision = core.read_json(path)
    answer = core.validate_selection(decision, question, policy, case)
    return answer, decision, core.file_hash(path)


def execute(args: argparse.Namespace) -> None:
    output = output_path(args.name)
    manifest = core.read_json(output / "manifest.json")
    if manifest.get("offline_only") is not False or args.offline_only:
        raise ValueError("Offline preparation can never be executed")
    verify(manifest)
    if platform.python_version() != manifest["runtime"]:
        raise ValueError("Frozen runtime changed")
    # One lease for all stages, permanently retained: no parallel/reset/re-execute.
    core.OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    save_new(
        core.OUTPUT_ROOT / "priority-probe-execution-lease.json",
        {
            "directory": str(output),
            "ledger_sha256": manifest["ledger_sha256"],
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    save_new(
        output / "started.json",
        {
            "deadline": manifest["absolute_deadline_utc"],
            "prior_guard": manifest["prior_guard"],
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    driver = shared()
    guard = core.carried_guard(
        manifest["prior_guard"], verify_frozen=lambda: verify(manifest)
    )
    stream = core.load_module(
        "priority_probe_owned_stream", core.INTPLAN / "append_stream.py"
    )
    core.existing.ObservedStream = stream.OwnedObservedStream
    database = owned_database(driver, "priority_probe_" + uuid4().hex)
    with driver.psycopg.connect(database.url, autocommit=True) as connection:
        connection.execute(
            driver.sql.SQL("CREATE SCHEMA {}").format(
                driver.sql.Identifier(database.schema)
            )
        )
    engine = driver.create_engine(
        database.sqlalchemy_url,
        connect_args={"options": f"-c search_path={database.schema}"},
    )
    try:
        with engine.begin() as connection:
            config = driver.migration_config()
            config.attributes.update(connection=connection, schema=database.schema)
            driver.command.upgrade(config, "head")
    finally:
        engine.dispose()
    save_new(
        output / "database.json",
        {
            "schema": database.schema,
            "database": "caliburn_intplan_test",
            "credential_saved": False,
        },
    )
    key = driver.read_openai_api_key(ROOT / "apps/api/.env")
    completed = []
    total_replies = 0
    with driver.test_client(database) as client:
        fixtures = []
        by_case = dict(zip(core.CASE_KEYS, manifest["cases"], strict=True))
        for trial in manifest["schedule"]:
            case = copy.deepcopy(by_case[trial["case_key"]])
            case["case_id"] = "合成職務"
            seeded = driver.seed_case(client, case, "訪談")
            fixtures.append({**seeded, **trial})
        save_new(output / "fixtures.json", fixtures)

        async def scenario() -> None:
            nonlocal total_replies

            async def api(method: str, path: str, **kwargs: Any) -> Any:
                # The portal owns this loop; avoid reentrant synchronous TestClient calls.
                async with driver.httpx2.AsyncClient(
                    transport=driver.httpx2.ASGITransport(app=client.app),
                    base_url="http://127.0.0.1:8100",
                    headers={"Origin": "http://127.0.0.1:8100"},
                ) as http:
                    response = await http.request(method, path, **kwargs)
                    response.raise_for_status()
                    return response.json()

            dsn = driver.make_conninfo(
                database.url, options=f"-c search_path={database.schema}"
            )
            async with driver.AsyncPostgresSaver.from_conn_string(
                dsn, serde=driver.create_graph_serializer()
            ) as saver:
                await saver.setup()
                transport = core.ProbeTransport(
                    guard,
                    driver.httpx2.AsyncHTTPTransport(retries=0),
                    output / "provider-trace.jsonl",
                )
                sdk = driver.create_responses_client(
                    api_key=key,
                    timeout_seconds=120,
                    http_client=driver.httpx2.AsyncClient(
                        transport=transport,
                        timeout=120,
                        trust_env=False,
                        follow_redirects=False,
                    ),
                )

                def ref_response(request: Any) -> Any:
                    kind = (
                        "search"
                        if request.url.path.endswith(":search")
                        else "task"
                        if "/tasks/" in request.url.path
                        else "reference"
                    )
                    return driver.httpx2.Response(
                        200, json=manifest["reference_fixture"][kind]
                    )

                async with driver.httpx2.AsyncClient(
                    base_url="http://references.invalid",
                    transport=driver.httpx2.MockTransport(ref_response),
                ) as ref_transport:
                    reference = driver.OccupationReferenceClient(ref_transport)
                    settings = driver.ModelSettings(
                        api_key=key,
                        model=manifest["model"],
                        reasoning_effort=manifest["effort"],
                        max_output_tokens=manifest["max_output_tokens"],
                        max_attempts_per_request=1,
                    )
                    try:
                        for fixture in fixtures:
                            case = by_case[fixture["case_key"]]
                            directory = output / fixture["trial"]
                            directory.mkdir()
                            starting = {
                                section: await api(
                                    "GET",
                                    f"/api/job-files/{fixture['job_file_id']}/jd/{section}",
                                )
                                for section in ("profile", "work", "sources")
                            }
                            save_new(directory / "formal-jd-before.json", starting)
                            evidence = core.load_module(
                                "priority_probe_source_reader",
                                core.INTPLAN / "evidence.py",
                            )
                            async with driver.httpx2.AsyncClient(
                                transport=driver.httpx2.ASGITransport(app=client.app),
                                base_url="http://127.0.0.1:8100",
                                headers={"Origin": "http://127.0.0.1:8100"},
                            ) as source_client:
                                starting_sources = await evidence.collect_sources(
                                    source_client,
                                    f"/api/job-files/{fixture['job_file_id']}",
                                    starting["sources"],
                                )
                            save_new(
                                directory / "fixed-source-contents-before.json",
                                starting_sources,
                            )
                            guard.case = fixture["trial"]
                            # Process-only constant binding; original runner supplies same FOCUS.
                            driver.runner_module.CONSULTANT_INSTRUCTIONS = manifest[
                                "instructions"
                            ][fixture["arm"]]
                            if (
                                driver.runner_module.FOCUS_INSTRUCTIONS
                                != manifest["common_focus"]
                                or driver.runner_module.OCCUPATION_REFERENCE_INSTRUCTIONS
                                != manifest["reference_instructions"]
                            ):
                                raise ValueError("Frozen common method changed")
                            text = case["employee_input"]
                            selection = None
                            disclosed = set()
                            expected_instructions = (
                                manifest["instructions"][fixture["arm"]]
                                + "\n\n"
                                + manifest["common_focus"]
                                + "\n\n"
                                + manifest["reference_instructions"]
                            )
                            guard.inspect_request = partial(
                                core.inspect_public_request,
                                expected_instructions=expected_instructions,
                                private_answers=[
                                    item["target_answer"]
                                    for item in manifest["reply_policy"][
                                        "answers"
                                    ].values()
                                ],
                                disclosed=disclosed,
                                private_criteria=tuple(
                                    text
                                    for value in manifest["assessments"].values()
                                    for text in value["criteria"]
                                ),
                            )
                            trial_replies = []
                            for turn in range(1, case["max_turns"] + 1):
                                if total_replies >= 48:
                                    guard.refuse("Effective reply cap reached")
                                originals_before = (
                                    await api(
                                        "GET",
                                        f"/api/job-files/{fixture['job_file_id']}/interviews",
                                    )
                                )["messages"]
                                # Actual HTTP acceptance creates the original execution/capture.
                                accepted = await api(
                                    "POST",
                                    f"/api/job-files/{fixture['job_file_id']}/inputs",
                                    json={"command_id": str(uuid4()), "text": text},
                                )
                                if selection is not None:
                                    selection["actually_submitted"] = True
                                    disclosed.add(text)
                                    selection["prior_source_ids"] = [
                                        item["source_id"] for item in originals_before
                                    ]
                                save_new(
                                    directory / f"turn-{turn:02}-accepted.json",
                                    {
                                        "accepted": accepted,
                                        "text": text,
                                        "selection": selection,
                                    },
                                )
                                file_id = UUID(fixture["job_file_id"])
                                scope = driver.ExecutionScope(
                                    file_id,
                                    UUID(accepted["execution_id"]),
                                    driver.ExecutionKind.CONSULTANT_TURN,
                                )
                                async with (
                                    client.app.state.database.sessions.begin() as session
                                ):
                                    writer = await driver.executions.claim_writer(
                                        session, scope, writer_id=uuid4()
                                    )
                                exchange = await driver.runner_module.ConsultantRunner(
                                    client.app.state.database.sessions,
                                    saver,
                                    sdk,
                                    settings,
                                    occupation_references=reference,
                                    interview_plans_enabled=False,
                                ).run(writer)
                                if not hasattr(exchange, "consultant_reply"):
                                    raise RuntimeError(
                                        "Paused turn retained; no automatic retry"
                                    )
                                total_replies += 1
                                result = {
                                    "execution_id": accepted["execution_id"],
                                    "exchange": asdict(exchange),
                                }
                                save_new(
                                    directory / f"turn-{turn:02}-result.json", result
                                )
                                # Completed status and source originals are read through formal HTTP.
                                status = await api(
                                    "GET",
                                    f"/api/job-files/{fixture['job_file_id']}/consultant-turns/{accepted['execution_id']}",
                                )
                                if status["status"] != "completed":
                                    raise RuntimeError(
                                        "Runner return lacks formal HTTP completion"
                                    )
                                originals = (
                                    await api(
                                        "GET",
                                        f"/api/job-files/{fixture['job_file_id']}/interviews",
                                    )
                                )["messages"]
                                if selection is not None:
                                    selection["formal_source_ids"] = (
                                        core.eligible_sources(selection, originals)
                                    )
                                    if not selection["formal_source_ids"]:
                                        raise RuntimeError(
                                            "Submitted answer lacks formal original"
                                        )
                                    save_new(
                                        directory
                                        / f"turn-{turn:02}-submitted-selection.json",
                                        selection,
                                    )
                                trial_replies.append(result)
                                if turn == case["max_turns"]:
                                    break  # Never select an unused final answer.
                                opaque = uuid4().hex
                                question = exchange.consultant_reply.interview_text
                                save_new(
                                    output / "review-input" / (opaque + ".json"),
                                    core.answer_review_packet(
                                        opaque_id=opaque,
                                        question_quote=question,
                                        originals=originals,
                                        policy=manifest["reply_policy"],
                                        case_key=fixture["case_key"],
                                    ),
                                )
                                save_new(
                                    directory / f"turn-{turn:02}-review-map.json",
                                    {"opaque_id": opaque},
                                )
                                text, decision, decision_hash = await wait_decision(
                                    output,
                                    opaque,
                                    question,
                                    fixture["case_key"],
                                    manifest["reply_policy"],
                                    guard,
                                )
                                if text is None:
                                    break
                                selection = {
                                    **decision,
                                    "answer": text,
                                    "decision_sha256": decision_hash,
                                    "actually_submitted": False,
                                }
                            final = {
                                section: await api(
                                    "GET",
                                    f"/api/job-files/{fixture['job_file_id']}/jd/{section}",
                                )
                                for section in ["profile", "work", "sources"]
                            }
                            save_new(directory / "formal-jd.json", final)
                            save_new(
                                directory / "formal-interviews.json",
                                await api(
                                    "GET",
                                    f"/api/job-files/{fixture['job_file_id']}/interviews",
                                ),
                            )
                            evidence = core.load_module(
                                "priority_probe_source_reader",
                                core.INTPLAN / "evidence.py",
                            )
                            async with driver.httpx2.AsyncClient(
                                transport=driver.httpx2.ASGITransport(app=client.app),
                                base_url="http://127.0.0.1:8100",
                                headers={"Origin": "http://127.0.0.1:8100"},
                            ) as source_client:
                                source_bodies = await evidence.collect_sources(
                                    source_client,
                                    f"/api/job-files/{fixture['job_file_id']}",
                                    final["sources"],
                                )
                            save_new(
                                directory / "fixed-source-contents.json", source_bodies
                            )
                            quality_id = uuid4().hex
                            interviews = core.read_json(
                                directory / "formal-interviews.json"
                            )
                            save_new(
                                output / "blind-quality" / (quality_id + ".json"),
                                core.quality_bundle(
                                    opaque_id=quality_id,
                                    starting_formal_jd=starting,
                                    starting_sources=starting_sources,
                                    formal_jd=final,
                                    assessment=manifest["assessments"][
                                        fixture["case_key"]
                                    ],
                                    interviews=interviews,
                                    trial_replies=trial_replies,
                                    fixed_sources=source_bodies,
                                ),
                            )
                            save_new(
                                directory / "quality-map.json",
                                {"opaque_id": quality_id},
                            )
                            completed.append(
                                {
                                    "trial": fixture["trial"],
                                    "replies": len(trial_replies),
                                }
                            )
                    finally:
                        await sdk.close()

        try:
            client.portal.call(scenario)
        except BaseException as error:
            save_new(
                output / "failure.json",
                {
                    "error_type": type(error).__name__,
                    "guard": guard.state(),
                    "effective_replies": total_replies,
                },
            )
            raise
        finally:
            save_new(
                output / "final-ledger.json",
                {
                    "completed": completed,
                    "effective_replies": total_replies,
                    "guard": guard.state(),
                    "prior_guard": manifest["prior_guard"],
                    "absolute_deadline_utc": core.DEADLINE.isoformat(),
                },
            )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["dry-run", "prepare", "execute"])
    parser.add_argument("--ledger")
    parser.add_argument("--quality-lock")
    parser.add_argument("--name", default="priority-probe-01")
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args()
    if args.mode == "dry-run":
        print(json.dumps(dry_data(args), ensure_ascii=False))
    elif args.mode == "prepare":
        if not args.ledger or not args.quality_lock:
            raise ValueError("Explicit final ledger and quality lock required")
        prepare(args)
    else:
        execute(args)


if __name__ == "__main__":
    main()
