"""Bounded synthetic cases through the unchanged current Memory parent."""
import argparse
import asyncio
import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import version
from uuid import uuid4

from support import FIRST, HERE, ROOT, generation_messages, load_module

LONG = ROOT / "docs/experiments/product-validation/data/long-interview-memory-2026-10-04"
own_support = sys.modules["support"]
sys.modules["support"] = load_module("occ2_long_support", LONG / "support.py")
try:
    live = load_module("occ2_existing_memory_flow", LONG / "experiment.py")
finally:
    sys.modules["support"] = own_support
live.MAX_CALLS = 256
live.MAX_INPUT = 4_000_000


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    live.dump(path, value)


class Recorder(live.Recorder):
    async def request(self, request):
        if request.url.path.endswith("/compact"):
            self.event({"event": "compact_blocked_before_send"})
            raise asyncio.CancelledError("experiment_compact_stop")
        await super().request(request)


def seed(settings, file_id, messages):
    last_source = None
    with live.psycopg.connect(settings.url, options=f"-c search_path={settings.schema}") as connection:
        connection.execute(
            "INSERT INTO job_files (job_file_id,creation_command_id,initial_display_name,display_name,employee_name) VALUES (%s,%s,'合成訪談','合成訪談','合成')",
            (file_id, uuid4()))
        for message in messages:
            source_id = uuid4()
            connection.execute(
                "INSERT INTO interview_texts (job_file_id,source_id,speaker,interview_text) VALUES (%s,%s,%s,%s)",
                (file_id, source_id, message["speaker"], message["text"]))
            connection.execute(
                "INSERT INTO formal_interviews (job_file_id,interview_sequence,source_id) VALUES (%s,%s,%s)",
                (file_id, message["interview_sequence"], source_id))
            if message["interview_sequence"] == 6:
                last_source = source_id
    if last_source is None:
        raise ValueError("Fixed employee frontier 6 missing")
    return last_source


def freeze(run_dir, settings):
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    corpus = json.loads((FIRST / "corpus.json").read_text(encoding="utf-8"))
    known = {row["id"] for row in corpus}
    assert len(cases) == 14 and len(corpus) == 805
    for case in cases:
        assert set(case["grades"]) | set(case["hard_negatives"]) <= known
        assert case["kind"] in ("positive", "insufficient", "out_of_corpus")
        assert (case["kind"] == "positive") == any(grade == 3 for grade in case["grades"].values())
        generation_messages(case)
    for split in ("development", "holdout"):
        group = [c for c in cases if c["split"] == split]
        assert len(group) == 7
        assert [sum(c["kind"] == kind for c in group) for kind in ("positive", "insufficient", "out_of_corpus")] == [4, 2, 1]
    paths = list((ROOT / "apps/api/src/caliburn").rglob("*.py"))
    paths += list((ROOT / "apps/api/migrations").rglob("*.py"))
    paths += [LONG / "experiment.py", LONG / "support.py", live.memory_probe.HERE / "experiment.py",
              LONG.parent / "design-comparisons-2026-10-04/provider_observations.py"]
    paths += [FIRST / name for name in ("prepare.py", "evaluation.py", "experiment.py", "validation.py")]
    paths += [path for path in HERE.iterdir() if path.suffix in (".py", ".md", ".json")]
    sources = {path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8") for path in sorted(set(paths))}
    dump(run_dir / "supporting-sources.json", sources)
    dump(run_dir / "manifest.json", {
        "frozen_utc": datetime.now(UTC).isoformat(), "schema": settings.schema,
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "git_branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT, text=True).strip(),
        "dirty_tree": "User and earlier work retained; exact used source contents archived.",
        "model": "gpt-6-luna", "reasoning_effort": "high", "openai": version("openai"),
        "python": sys.version, "cases_sha256": sha(HERE / "cases.json"),
        "protocol_sha256": sha(HERE / "protocol.md"), "corpus_sha256": sha(FIRST / "corpus.json"),
        "supporting_sources_sha256": sha(run_dir / "supporting-sources.json"),
        "files_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(set(paths))},
        "instructions": {"B1": live.SITUATION_INSTRUCTIONS, "B2": live.UNDERSTANDING_INSTRUCTIONS},
        "maximum_generation_calls": 256, "maximum_admitted_input": 4_000_000,
        "maximum_output_per_call": 8192, "maximum_cost_usd": 2,
        "maximum_theoretical_cost_usd": 1.548576,
        "fixed_method": {"input": "published_B2", "representation": "TOP", "method": "dense_exact", "k": 10},
        "labels_reviewed_before_generation": True, "annotation_scope": "engineering synthetic reference, not expert truth",
        "case_order": [c["case_id"] for c in sorted(cases, key=lambda c: (c["split"] != "development", c["case_id"]))]})
    return sorted(cases, key=lambda c: (c["split"] != "development", c["case_id"]))


async def run(run_dir):
    settings = live.DatabaseSettings(url="postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test", schema=f"eval_occ2_{uuid4().hex}")
    cases = freeze(run_dir, settings)
    await asyncio.to_thread(live.memory_probe.initialize_schema, settings)
    recorder = Recorder(run_dir)
    database = live.Database(settings)
    try:
        async with live.httpx2.AsyncClient(follow_redirects=False,
                event_hooks={"request": [recorder.request], "response": [recorder.response]}) as transport:
            async with live.create_responses_client(api_key=live.read_openai_api_key(ROOT / "apps/api/.env"),
                    timeout_seconds=120, http_client=transport) as client:
                dsn = live.make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
                async with live.AsyncPostgresSaver.from_conn_string(dsn,
                        serde=live.create_graph_serializer(allowed_types=live.MEMORY_CHECKPOINT_TYPES)) as saver:
                    await saver.setup()
                    model = live.ModelSettings(api_key="configured-by-client", max_output_tokens=8192,
                        max_model_steps=64, max_outbound_attempts=128, max_attempts_per_request=1,
                        turn_timeout_seconds=720)
                    dispatch = live.MemoryRoleDispatch(
                        live.WorkSituationAnalystRunner(database.sessions, saver, client, model),
                        live.WorkUnderstandingAnalystRunner(database.sessions, saver, client, model))
                    parent = live.MemoryBatchWorkflow(database.sessions, run_role=dispatch)
                    candidates = live.MemoryCandidateWorkflow(database.sessions)
                    for case in cases:
                        recorder.phase = {"phase": "memory_capture", "case_id": case["case_id"], "split": case["split"]}
                        case_dir = run_dir / case["case_id"]
                        case_dir.mkdir()
                        messages = generation_messages(case)
                        dump(case_dir / "messages.json", messages)
                        file_id = uuid4()
                        source_id = await asyncio.to_thread(seed, settings, file_id, messages)
                        scope = live.ExecutionScope(file_id, uuid4(), live.ExecutionKind.MEMORY_BATCH)
                        async with database.sessions.begin() as session:
                            await live.executions.admit_execution(session, scope)
                            writer = await live.executions.claim_writer(session, scope, writer_id=uuid4())
                        started = await candidates.start(writer, source_id)
                        if started is None:
                            raise ValueError("Candidate did not start")
                        before = recorder.calls
                        snapshot = await parent.run(writer)
                        fixed = await live.memory_probe.read_snapshot(candidates, snapshot)
                        dump(case_dir / "snapshot.json", fixed)
                        capture = {"case_id": case["case_id"], "job_file_id": str(file_id),
                            "execution_id": str(scope.execution_id), "snapshot_id": str(snapshot.snapshot_id),
                            "published": True, "model_calls": recorder.calls - before,
                            "object_count": len(fixed["objects"])}
                        live.memory_probe.append(run_dir / "capture.jsonl", capture)
                        print(json.dumps(capture), flush=True)
        dump(run_dir / "complete.json", {"finished_utc": datetime.now(UTC).isoformat(),
            "cases": len(cases), "calls": recorder.calls, "admitted_input": recorder.admitted_input})
    except BaseException as exc:
        dump(run_dir / "failure.json", {"type": type(exc).__name__, "case": recorder.phase,
            "calls": recorder.calls, "admitted_input": recorder.admitted_input,
            "utc": datetime.now(UTC).isoformat()})
        raise
    finally:
        await database.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("run", default="run-01", nargs="?")
    args = parser.parse_args()
    run_dir = HERE / args.run
    run_dir.mkdir(exist_ok=False)
    # Match the existing Windows research harness: psycopg requires Selector.
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(asyncio.wait_for(run(run_dir), timeout=3600))
