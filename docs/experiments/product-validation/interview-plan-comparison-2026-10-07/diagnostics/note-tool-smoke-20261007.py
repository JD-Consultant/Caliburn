"""Two public HTTP Turns through the repaired production note tool. Root launches.

No study cases, private answers, background Memory, alternative prompt or seeded
plan. Offline preparation imports code only; provider/DB/key access is execute-only.
"""

import argparse
import ast
import asyncio
import copy
import json
import platform
import re
import sys
from dataclasses import asdict
from datetime import UTC, datetime, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

HERE = Path(__file__).resolve().parent
ROOT = next(path for path in HERE.parents if (path / "AGENTS.md").is_file())
sys.path.insert(0, str(ROOT / "apps/api/src"))
import importlib.util

PRIORITY = (
    ROOT / "docs/experiments/product-validation/data/jd-question-selection-2026-10-07"
)
spec = importlib.util.spec_from_file_location(
    "note_smoke_priority", PRIORITY / "priority-probe-run.py"
)
priority = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = priority
spec.loader.exec_module(priority)
core = priority.core
import caliburn.agent_execution.request_capacity as capacity_module

original_capacity = capacity_module.require_request_capacity
OUTPUT_ROOT = core.ARTIFACT_ROOT / "note-tool-smoke"
STOP_PATH = (
    core.ARTIFACT_ROOT / "operational-evidence/stop-20261007-0455/stop-metadata.json"
)
COUNTERS = {"generations": 20, "outbound": 60, "counted_input": 3000000, "compacts": 2}
INPUTS = (
    "我在行政部門負責月報彙整，也整理新人資料。兩項工作的交接和責任界線還沒說清楚。先聊月報彙整；新人資料整理先留在訪談筆記，等之後再談。",
    "月報這一項，我先把各項明細互相比對，把差異整理出來交主管，由主管決定怎麼處理，我不決定差異的調整。新人資料整理的審核由誰接手仍沒說清楚；先更新月報部分，保留新人資料這個未知，再繼續訪談。",
)
owned_database = priority.owned_database
save_new = priority.save_new


def output_path(name):
    if re.fullmatch(r"note-smoke-[a-z0-9_-]{1,48}", name) is None:
        raise ValueError("Invalid smoke name")
    return OUTPUT_ROOT / name


def load_prior(path, stop_path=STOP_PATH):
    value = core.read_json(path)
    prior = value.get("guard", value)
    core.validate_accounting(prior)
    latest = core.read_json(stop_path)["last_current_journal_guard"]
    for key in ("spent_usd", "occupied_usd"):
        if Decimal(prior[key]) != Decimal(str(latest[key])):
            raise ValueError("Prior differs from latest stopped journal")
    if {
        key: Decimal(value) for key, value in prior["retained_reservations"].items()
    } != {
        key: Decimal(str(value))
        for key, value in latest["retained_reservations"].items()
    } or any(prior[key] != latest[key] for key in COUNTERS):
        raise ValueError("Prior consumption/reservations must not reset")
    if prior.get("stop_reason") is not None:
        raise ValueError("Accounting carrier has a budget stop")
    return prior


def require_first_turn(view, valid_edits):
    plan = view.get("plan")
    if not isinstance(plan, str) or not plan.strip() or valid_edits < 1:
        raise RuntimeError(
            "First HTTP Turn has no adopted nonempty successfully edited plan; stop"
        )


class SmokeControl:
    """One controlled complete-Step boundary; only a real native saver ack disarms."""

    def __init__(self):
        self.owner = None
        self.plan_edited = False
        self.pending = True
        self.trigger_count = 0
        self.expected_plan = None
        self.compact_items = None
        self.projection = None
        self.next_a = False
        self.native_thread = None
        self.completed_steps = 0

    def capacity(self, request, count, limits, *, completed_steps):
        threshold = capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS
        controlled = bool(
            self.owner and self.plan_edited and self.pending and completed_steps > 0
        )
        if controlled and self.trigger_count:
            raise RuntimeError(
                "Controlled boundary already requested without native adoption"
            )
        if controlled:
            capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS = 1
        try:
            original_capacity(request, count, limits, completed_steps=completed_steps)
        except capacity_module.CompactionRequiredError:
            if controlled:
                self.trigger_count += 1
                self.completed_steps = completed_steps
            raise
        finally:
            capacity_module.MID_WORK_COMPACTION_THRESHOLD_TOKENS = threshold

    def observe_saved(self, thread_id, values):
        if (
            self.owner
            and isinstance(thread_id, str)
            and thread_id.startswith(self.owner + ":compact:")
            and values.get("adopted") is True
            and "preparation_policy" in values
            and values["preparation_policy"] is None
            and values.get("compaction_snapshot") is not None
            and self.plan_edited
            and self.trigger_count == 1
        ):
            self.pending = False
            self.native_thread = thread_id

    def check_next_a(self, payload):
        if self.compact_items is None or self.projection is None or self.next_a:
            return
        expected = [*self.compact_items, self.projection["plan_item"]]
        if payload.get("input") != expected:
            raise RuntimeError(
                "First A after native C differs from complete C plus exact saved plan"
            )
        projected = json.loads(self.projection["plan_item"]["content"])
        if projected.get("plan") != self.expected_plan:
            raise RuntimeError(
                "Native C projection differs from actual saved candidate"
            )
        self.next_a = True


class SmokeGuard(core.ProbeGuard):
    def check(self, payload):
        remaining = (core.DEADLINE - self.utc_clock()).total_seconds()
        if remaining <= 0:
            self.refuse("absolute deadline reached")
        if self.started is None:
            self.seconds = min(600, remaining)
        core.existing.BatchGuard.check(self, payload)

    def outbound_attempt(self, payload):
        core.existing.BatchGuard.outbound_attempt(self, payload)
        if payload.get("model") != "gpt-6-luna":
            self.refuse("Unapproved smoke model")
        if "instructions" in payload:
            if (
                payload["instructions"] != self.expected_instructions
                or payload.get("tools") != self.expected_tools
            ):
                self.refuse("Production instruction/tool bundle differs from freeze")
            if payload.get("reasoning", {}).get("effort") != "high":
                self.refuse("Unapproved smoke effort")


def carried_guard(prior, verify_frozen=lambda: None):
    core.validate_accounting(prior)
    guard = SmokeGuard(
        limit=min(Decimal(8), Decimal(prior["occupied_usd"]) + Decimal(1)),
        seconds=600,
        verify_frozen=verify_frozen,
        max_generations=prior["generations"] + COUNTERS["generations"],
        max_outbound=prior["outbound"] + COUNTERS["outbound"],
        max_counted_input=prior["counted_input"] + COUNTERS["counted_input"],
        max_compacts=prior["compacts"] + COUNTERS["compacts"],
    )
    guard.spent = Decimal(prior["spent_usd"])
    guard.attempts = {
        key: Decimal(value) for key, value in prior["retained_reservations"].items()
    }
    for key in COUNTERS:
        setattr(guard, key, prior[key])
    guard.utc_clock = lambda: datetime.now(UTC)
    guard.case = "public-note-availability-smoke"
    return guard


def observed_saver_class():
    """Execute only the exact existing helper class, avoiding private-case imports."""
    from caliburn.adapters.job_file_checkpointer import JobFilePostgresSaver
    from caliburn.adapters.response_serialization import compaction_input_items

    source = core.INTPLAN / "run_batch.py"
    node = next(
        node
        for node in ast.parse(source.read_text(encoding="utf-8")).body
        if isinstance(node, ast.ClassDef) and node.name == "ObservedSaver"
    )
    namespace = {
        "REAL_SAVER": JobFilePostgresSaver,
        "datetime": datetime,
        "timezone": timezone,
        "json": json,
        "role": core.existing.role,
        "digest": core.existing.digest,
        "public": core.existing.public,
        "compaction_input_items": compaction_input_items,
    }
    exec(  # noqa: S102 - exact frozen local helper class; no imported private-case module
        compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"),
        namespace,
    )
    return namespace["ObservedSaver"]


def prepare(args):
    driver = priority.shared()
    prior = load_prior(args.prior, args.stop_metadata)
    output = output_path(args.name)
    paths = [
        *HERE.glob("note-tool-smoke-*.py"),
        Path(priority.__file__),
        Path(core.__file__),
        Path(driver.__file__),
        core.INTPLAN / "run_batch.py",
        core.INTPLAN / "guard.py",
        core.INTPLAN / "append_stream.py",
        core.INTPLAN / "evidence.py",
        PRIORITY.parent / "full-interview-rag-2026-10-06/batch_guard.py",
        PRIORITY.parent / "early-interview-recall-2026-10-05/study_guard.py",
        PRIORITY.parent / "early-interview-recall-2026-10-05/study_manifest.py",
        ROOT / "apps/api/pyproject.toml",
        ROOT / "apps/api/uv.lock",
        ROOT / "apps/api/alembic.ini",
    ]
    paths += [
        path
        for path in (ROOT / "apps/api/src/caliburn").rglob("*")
        if path.suffix in {".py", ".json", ".html"}
    ]
    files = driver.freeze_files(paths, root=ROOT, output=output)
    instructions = "\n\n".join(
        [
            core.constant(
                (ROOT / driver.PROMPT_PATH).read_bytes(), "CONSULTANT_INSTRUCTIONS"
            ),
            core.constant(
                (
                    ROOT
                    / "apps/api/src/caliburn/agents/job_consultant/planning_instructions.py"
                ).read_bytes(),
                "FOCUS_INSTRUCTIONS",
            ),
            core.constant(
                (
                    ROOT
                    / "apps/api/src/caliburn/agents/job_consultant/planning_instructions.py"
                ).read_bytes(),
                "INTERVIEW_PLAN_INSTRUCTIONS",
            ),
        ]
    )
    manifest = {
        "files": files,
        "instructions": instructions,
        "tools": driver.consultant_tool_definitions(
            occupation_references_enabled=False, interview_plans_enabled=True
        ),
        "inputs": INPUTS,
        "prior_guard": prior,
        "prior_path": str(Path(args.prior).resolve()),
        "prior_sha256": core.file_hash(args.prior),
        "stop_metadata": str(Path(args.stop_metadata).resolve()),
        "stop_sha256": core.file_hash(args.stop_metadata),
        "model": "gpt-6-luna",
        "effort": "high",
        "max_output_tokens": 16384,
        "provider": "https://api.openai.com",
        "service_tier": "default",
        "runtime": platform.python_version(),
        "notes_enabled": True,
        "background_memory": 0,
        "additional_counters": COUNTERS,
        "additional_usd": "1.00",
        "global_usd": "8.00",
        "minutes_since_first_outbound": 10,
        "absolute_deadline": core.DEADLINE.isoformat(),
        "offline_only": args.offline_only,
    }
    save_new(output / "manifest.json", manifest)
    print(
        json.dumps(
            {
                "prepared": str(output),
                "files": len(files),
                "provider_calls": 0,
                "credential_read": False,
                "database_connected": False,
            }
        )
    )


def verify(manifest):
    core.verify_frozen(manifest)
    if (
        core.file_hash(manifest["prior_path"]) != manifest["prior_sha256"]
        or core.file_hash(manifest["stop_metadata"]) != manifest["stop_sha256"]
    ):
        raise ValueError("Frozen latest accounting changed")
    if (
        load_prior(manifest["prior_path"], manifest["stop_metadata"])
        != manifest["prior_guard"]
    ):
        raise ValueError("Frozen accounting differs")
    if (
        manifest["inputs"] != list(INPUTS)
        or manifest["additional_counters"] != COUNTERS
        or manifest["runtime"] != platform.python_version()
    ):
        raise ValueError("Frozen smoke scope/runtime changed")


def execute(args):
    output = output_path(args.name)
    manifest = core.read_json(output / "manifest.json")
    verify(manifest)
    if manifest["offline_only"]:
        raise ValueError("Offline rehearsal is not executable")
    if datetime.now(UTC) >= core.DEADLINE:
        raise ValueError("Absolute deadline expired")
    # One non-resumable global lease; never reset consumed budget or unknown reserves.
    save_new(
        OUTPUT_ROOT / "paid-lease.json",
        {
            "output": str(output),
            "manifest_sha256": core.file_hash(output / "manifest.json"),
        },
    )
    guard = carried_guard(manifest["prior_guard"], lambda: verify(manifest))
    guard.expected_instructions = manifest["instructions"]
    guard.expected_tools = manifest["tools"]
    control = SmokeControl()
    driver = priority.shared()
    schema = "note_smoke_" + uuid4().hex[:16]
    database = owned_database(driver, schema)
    with driver.psycopg.connect(database.url, autocommit=True) as connection:
        connection.execute(
            driver.sql.SQL("CREATE SCHEMA {}").format(driver.sql.Identifier(schema))
        )
    engine = driver.create_engine(
        database.sqlalchemy_url, connect_args={"options": f"-c search_path={schema}"}
    )
    try:
        with engine.begin() as connection:
            config = driver.migration_config()
            config.attributes.update(connection=connection, schema=schema)
            driver.command.upgrade(config, "head")
    finally:
        engine.dispose()
    save_new(
        output / "database.json",
        {
            "schema": schema,
            "database": "caliburn_intplan_test",
            "host": "127.0.0.1",
            "port": 55447,
            "credential_saved": False,
        },
    )
    # Only root's explicit execute reaches this credential read.
    key = driver.read_openai_api_key(ROOT / "apps/api/.env")
    stream = core.load_module(
        "note_smoke_owned_stream", core.INTPLAN / "append_stream.py"
    )
    core.existing.ObservedStream = stream.OwnedObservedStream
    ObservedSaver = observed_saver_class()
    from caliburn.adapters.response_serialization import compaction_input_items

    class SmokeSaver(ObservedSaver):
        journal = output / "checkpoint-journal.jsonl"

        async def aput(self, config, checkpoint, metadata, new_versions):
            result = await super().aput(config, checkpoint, metadata, new_versions)
            values = checkpoint["channel_values"]
            thread = config.get("configurable", {}).get("thread_id")
            control.observe_saved(thread, values)
            if thread == control.native_thread and values.get("adopted") is True:
                control.compact_items = copy.deepcopy(
                    compaction_input_items(values["compaction_snapshot"])
                )
                path = output / "native-midwork-adopted.json"
                if not path.exists():
                    save_new(
                        path,
                        {
                            "thread_id": thread,
                            "checkpoint_id": checkpoint["id"],
                            "completed_steps": control.completed_steps,
                            "expected_plan": control.expected_plan,
                            "values": values,
                        },
                    )
            if (
                control.owner
                and isinstance(thread, str)
                and thread.startswith(control.owner + ":plan_projection:")
                and values.get("projection") is not None
            ):
                control.projection = copy.deepcopy(values["projection"])
                path = output / "native-plan-projection.json"
                if not path.exists():
                    save_new(
                        path,
                        {
                            "thread_id": thread,
                            "checkpoint_id": checkpoint["id"],
                            "values": values,
                        },
                    )
            return result

    valid_edits = {1: 0, 2: 0}
    turn_number = 0

    class SmokeRunner(driver.runner_module.ConsultantRunner):
        async def _tools(self, writer, context, role_history):
            tools = await super()._tools(writer, context, role_history)
            if tools.interview_plans is None:
                raise RuntimeError("Production note capability absent")
            original_execute = tools.interview_plans.execute

            async def observed_execute(prepared):
                result = await original_execute(prepared)
                if json.loads(result).get("status") == "updated":
                    saved = await tools.interview_plans.workflow.read_active(writer)
                    if saved is None or saved.body != prepared["change"]["next_plan"]:
                        raise RuntimeError(
                            "Successful edit lacks exact saved candidate"
                        )
                    valid_edits[turn_number] += 1
                    save_new(
                        output
                        / f"turn-{turn_number:02}-edit-{valid_edits[turn_number]:02}.json",
                        {
                            "prepared": prepared,
                            "result": result,
                            "actual_candidate": asdict(saved),
                        },
                    )
                    if turn_number == 2 and control.pending:
                        control.owner = role_history.response_thread_id
                        control.expected_plan = saved.body
                        control.plan_edited = bool(saved.body and saved.body.strip())
                return result

            tools.interview_plans.execute = observed_execute
            return tools

    class SmokeTransport(core.ProbeTransport):
        async def handle_async_request(self, request):
            self.actual_payload = json.loads(request.content)
            return await super().handle_async_request(request)

        def record(self, event, **fields):
            if (
                event == "admitted"
                and fields.get("endpoint") == "/v1/responses"
                and control.compact_items is not None
                and not control.next_a
            ):
                control.check_next_a(self.actual_payload)
                save_new(
                    output / "next-a-after-native-c.json",
                    {
                        "input_item_sha256": fields["input_item_sha256"],
                        "request": self.actual_payload,
                        "exact_complete_c_plus_saved_plan": True,
                    },
                )
            super().record(event, **fields)

    old_capacity = capacity_module.require_request_capacity
    from caliburn.agent_execution import tool_steps

    old_step_capacity = tool_steps.require_request_capacity
    capacity_module.require_request_capacity = control.capacity
    tool_steps.require_request_capacity = control.capacity
    completed = 0
    try:
        with driver.test_client(database) as client:

            async def scenario():
                nonlocal turn_number, completed
                async with driver.httpx2.AsyncClient(
                    transport=driver.httpx2.ASGITransport(app=client.app),
                    base_url="http://127.0.0.1:8100",
                    headers={"Origin": "http://127.0.0.1:8100"},
                ) as http:

                    async def api(method, path, **kwargs):
                        response = await http.request(method, path, **kwargs)
                        response.raise_for_status()
                        return response.json()

                    created = await api(
                        "POST",
                        "/api/job-files",
                        json={
                            "command_id": str(uuid4()),
                            "display_name": "行政合成職務",
                            "employee_name": "合成受訪者",
                        },
                    )
                    save_new(output / "created.json", created)
                    base = "/api/job-files/" + created["job_file_id"]
                    source_reader = core.load_module(
                        "note_smoke_sources", core.INTPLAN / "evidence.py"
                    )

                    async def snapshot(name):
                        jd = {
                            section: await api("GET", base + "/jd/" + section)
                            for section in ("profile", "work", "sources")
                        }
                        save_new(output / (name + "-formal-jd.json"), jd)
                        save_new(
                            output / (name + "-fixed-sources.json"),
                            await source_reader.collect_sources(
                                http, base, jd["sources"]
                            ),
                        )
                        save_new(
                            output / (name + "-interviews.json"),
                            await api("GET", base + "/interviews"),
                        )
                        view = await api("GET", base + "/interview-plan")
                        save_new(output / (name + "-formal-plan.json"), view)
                        return view

                    await snapshot("before")
                    dsn = driver.make_conninfo(
                        database.url, options=f"-c search_path={schema}"
                    )
                    async with driver.AsyncPostgresSaver.from_conn_string(
                        dsn, serde=driver.create_graph_serializer()
                    ) as native:
                        await native.setup()
                        saver = SmokeSaver(native)
                        transport = SmokeTransport(
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
                        settings = driver.ModelSettings(
                            api_key=key,
                            model=manifest["model"],
                            reasoning_effort=manifest["effort"],
                            max_output_tokens=manifest["max_output_tokens"],
                            max_attempts_per_request=1,
                        )
                        try:
                            for turn_number, text in enumerate(INPUTS, 1):
                                accepted = await api(
                                    "POST",
                                    base + "/inputs",
                                    json={"command_id": str(uuid4()), "text": text},
                                )
                                save_new(
                                    output / f"turn-{turn_number:02}-accepted.json",
                                    {"accepted": accepted, "text": text},
                                )
                                scope = driver.ExecutionScope(
                                    UUID(created["job_file_id"]),
                                    UUID(accepted["execution_id"]),
                                    driver.ExecutionKind.CONSULTANT_TURN,
                                )
                                async with (
                                    client.app.state.database.sessions.begin() as session
                                ):
                                    writer = await driver.executions.claim_writer(
                                        session, scope, writer_id=uuid4()
                                    )
                                result = await SmokeRunner(
                                    client.app.state.database.sessions,
                                    saver,
                                    sdk,
                                    settings,
                                    interview_plans_enabled=True,
                                ).run(writer)
                                if not hasattr(result, "consultant_reply"):
                                    raise RuntimeError("Paused Turn retained; no retry")
                                save_new(
                                    output / f"turn-{turn_number:02}-result.json",
                                    asdict(result),
                                )
                                status = await api(
                                    "GET",
                                    base
                                    + "/consultant-turns/"
                                    + accepted["execution_id"],
                                )
                                save_new(
                                    output / f"turn-{turn_number:02}-status.json",
                                    status,
                                )
                                if status["status"] != "completed":
                                    raise RuntimeError("Turn not formally completed")
                                originals = (await api("GET", base + "/interviews"))[
                                    "messages"
                                ]
                                if not any(
                                    item["source_id"] == accepted["source_id"]
                                    and item["speaker"] == "employee"
                                    and item["interview_text"] == text
                                    for item in originals
                                ):
                                    raise RuntimeError(
                                        "HTTP input lacks exact eligible original source"
                                    )
                                view = await snapshot(f"turn-{turn_number:02}")
                                require_first_turn(view, valid_edits[turn_number])
                                if turn_number == 1:
                                    first_plan = view["plan"]
                                elif view["plan"] == first_plan or not (
                                    control.trigger_count == 1
                                    and control.completed_steps > 0
                                    and not control.pending
                                    and control.next_a
                                ):
                                    raise RuntimeError(
                                        "Second Turn lacks changed plan and real within-Work C/next-A proof"
                                    )
                                completed += 1
                        finally:
                            await sdk.close()

            async def bounded_scenario():
                # Conservative outer wall clock also bounds an in-flight provider call.
                seconds = min(600, (core.DEADLINE - datetime.now(UTC)).total_seconds())
                if seconds <= 0:
                    raise RuntimeError("Absolute deadline expired")
                async with asyncio.timeout(seconds):
                    await scenario()

            client.portal.call(bounded_scenario)
    except BaseException as error:
        save_new(
            output / "failure.json",
            {
                "error_type": type(error).__name__,
                "guard": guard.state(),
                "completed_turns": completed,
            },
        )
        raise
    finally:
        capacity_module.require_request_capacity = old_capacity
        tool_steps.require_request_capacity = old_step_capacity
        save_new(
            output / "final-ledger.json",
            {
                "guard": guard.state(),
                "prior_sha256": manifest["prior_sha256"],
                "completed_turns": completed,
                "mechanical_smoke_passed": completed == 2,
                "semantic_retention_requires_review": True,
            },
        )
    print(
        json.dumps(
            {
                "output": str(output),
                "completed_turns": completed,
                "mechanical_smoke_passed": completed == 2,
            }
        )
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--prepare", action="store_true")
    mode.add_argument("--execute", action="store_true")
    parser.add_argument("--name", default="note-smoke-" + uuid4().hex)
    parser.add_argument("--prior")
    parser.add_argument("--stop-metadata", default=str(STOP_PATH))
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "provider_calls": 0,
                    "credential_read": False,
                    "database_connected": False,
                    "synthetic_cases": 1,
                    "http_turns": 2,
                    "notes_enabled": True,
                    "background_memory": 0,
                    "prior": load_prior(args.prior, args.stop_metadata)
                    if args.prior
                    else None,
                    "additional_counters": COUNTERS,
                    "additional_usd": "1.00",
                    "global_usd": "8.00",
                    "minutes": 10,
                    "absolute_deadline": core.DEADLINE.isoformat(),
                    "output": str(output_path(args.name)),
                }
            )
        )
    elif args.prepare:
        if not args.prior:
            parser.error("prepare requires latest normalized --prior")
        prepare(args)
    else:
        execute(args)


if __name__ == "__main__":
    main()
