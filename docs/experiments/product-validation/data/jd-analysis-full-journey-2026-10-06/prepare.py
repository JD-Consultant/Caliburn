"""Freeze explicit inputs and start only the named experiment container; never reset data."""

import importlib.util
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
NAME = "caliburn-jd-analysis-full-20261006"
SCHEMA = "jd_analysis_full_20261006"


def main():
    helper = HERE.parent / "early-interview-recall-2026-10-05/study_manifest.py"
    spec = importlib.util.spec_from_file_location("study_manifest", helper)
    manifest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(manifest)
    if (HERE / "freeze").exists():
        raise RuntimeError(
            "This preparation is single-use; inspect evidence, do not restart"
        )
    prior = json.loads(
        subprocess.check_output(
            ["docker", "inspect", "caliburn-e2e-20261006-app-1"], text=True
        )
    )[0]
    existing = subprocess.check_output(
        ["docker", "ps", "-a", "--format", "{{.Names}}"], text=True
    ).splitlines()
    if NAME in existing:
        raise RuntimeError("Named experiment already exists; no implicit replacement")
    paths = [
        path
        for path in (ROOT / "apps/api/src").rglob("*")
        if path.is_file() and path.suffix != ".pyc" and "__pycache__" not in path.parts
    ]
    paths += list((ROOT / "apps/api/contracts/tools").glob("*.json"))
    paths += list(HERE.glob("*.py")) + [HERE / "README.md"]
    paths += [ROOT / "apps/api/tests/fixtures/job_analysis_quality/personas.json"]
    shared = HERE.parent / "full-interview-rag-2026-10-06"
    paths += [
        shared / name
        for name in (
            "batch_guard.py",
            "test_batch_guard.py",
            "journey.py",
            "source_probe.py",
            "rag_probe.py",
        )
    ]
    records = manifest.freeze_files(paths, root=ROOT, output=HERE / "freeze")
    manifest.save_new(
        HERE / "manifest.json",
        {
            "model": "gpt-6-luna",
            "reasoning_effort": "high",
            "limit_usd": "0.30",
            "seconds": 3600,
            "schema": SCHEMA,
            "container": NAME,
            "image_id": prior["Image"],
            "git_head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
            ).strip(),
            "source_hashes": records,
            "comparison": "descriptive prior adaptive journey",
            "source_archive_sha256": manifest.file_hash(HERE / "freeze/sources.zip"),
        },
    )
    environment = os.environ.copy()
    old_environment = dict(entry.split("=", 1) for entry in prior["Config"]["Env"])
    environment["CALIBURN_DATABASE_URL"] = old_environment["CALIBURN_DATABASE_URL"]
    args = [
        "docker",
        "run",
        "-d",
        "--name",
        NAME,
        "--init",
        "--read-only",
        "--tmpfs",
        "/tmp",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges:true",
        "--shm-size",
        "256m",
        "--network",
        "caliburn-e2e-20261006_default",
        "-p",
        "127.0.0.1:8107:8100",
        "-e",
        "CALIBURN_DATABASE_URL",
        "-e",
        f"CALIBURN_DATABASE_SCHEMA={SCHEMA}",
        "-e",
        "CALIBURN_DEV_ORIGIN=http://127.0.0.1:8107",
        "-e",
        "CALIBURN_OCCUPATION_REFERENCE_URL=http://ocs-indexer:8000",
        "--mount",
        f"type=bind,source={HERE},target=/witness",
        "--mount",
        f"type=bind,source={shared},target=/shared,readonly",
        "--mount",
        f"type=bind,source={ROOT / 'apps/api/.env'},target=/secret/openai.env,readonly",
        "--entrypoint",
        "python",
        prior["Image"],
        "/witness/guarded_app.py",
    ]
    completed = subprocess.run(
        args, env=environment, capture_output=True, text=True, check=False
    )
    if completed.returncode:
        raise RuntimeError(
            "Isolated container could not start; inspect Docker without printing secrets"
        )
    print(
        json.dumps(
            {
                "container": NAME,
                "container_id": completed.stdout.strip(),
                "schema": SCHEMA,
                "frozen_files": len(records),
            }
        )
    )


if __name__ == "__main__":
    main()
