"""Freeze the effective source, guides, cases and group capability templates."""

import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from caliburn.agents.job_consultant.planning_instructions import (
    FOCUS_INSTRUCTIONS,
    INTERVIEW_PLAN_INSTRUCTIONS,
)
from caliburn.agents.job_consultant.tools import consultant_tool_definitions

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
GUIDES = [
    "2026-09-09-complete-work-analysis-guide.md",
    "2026-09-09-customized-jd-depth-and-interview-calibration.md",
    "2026-09-09-jd-field-and-writing-guide.md",
]
LIMITS = {
    "pilot": {
        "limit_usd": "0.60",
        "seconds": 1800,
        "max_generations": 80,
        "max_compacts": 2,
        "max_outbound": 200,
        "max_counted_input": 4000000,
        "turns": 6,
    },
    "formal": {
        "limit_usd": "8.00",
        "seconds": 14400,
        "max_generations": 1500,
        "max_compacts": 16,
        "max_outbound": 3500,
        "max_counted_input": 40000000,
        "turns": 20,
    },
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    files = [
        *ROOT.glob("apps/api/src/caliburn/**/*.py"),
        *ROOT.glob("apps/api/contracts/**/*.json"),
        *ROOT.glob("apps/api/src/caliburn/contracts/generated/**/*.json"),
        ROOT / "apps/api/pyproject.toml",
        ROOT / "apps/api/uv.lock",
        *HERE.glob("*.py"),
        HERE / "private_facts.json",
        HERE / "protocol.md",
        HERE / "disclosure-policy.md",
        ROOT
        / "docs/experiments/product-validation/data/full-interview-rag-2026-10-06/batch_guard.py",
        *[ROOT / "docs/guides" / name for name in GUIDES],
    ]
    return {
        str(path.relative_to(ROOT)).replace("\\", "/"): sha(path)
        for path in sorted(files)
    }


def freeze(phase, destination):
    hashes = source_hashes()
    snapshot = destination.parent / "source-snapshot"
    snapshot.mkdir()
    for relative, expected in hashes.items():
        original = ROOT / relative
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        contents = original.read_bytes()
        if hashlib.sha256(contents).hexdigest() != expected:
            raise RuntimeError("Source changed while archiving frozen batch")
        target.write_bytes(contents)
    data = {
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "model": "gpt-6-luna",
        "reasoning_effort": "high",
        "runtime": {
            "python": platform.python_version(),
            "dependencies": {
                package: version(package)
                for package in ["openai", "langgraph", "pydantic", "SQLAlchemy"]
            },
        },
        "max_output_tokens": 16384,
        "service_tier": "default",
        "rag_enabled": False,
        "database": "127.0.0.1:55447/caliburn_intplan_test",
        "initial_jd": "empty",
        "initial_memory": "empty",
        "limits": LIMITS[phase],
        "guides": {name: sha(ROOT / "docs/guides" / name) for name in GUIDES},
        "common_focus": FOCUS_INSTRUCTIONS,
        "P2_plan_instructions": INTERVIEW_PLAN_INSTRUCTIONS,
        "tools": {
            group: consultant_tool_definitions(interview_plans_enabled=group == "P2")
            for group in ["P1", "P2"]
        },
        "source_sha256": hashes,
        "source_snapshot": "source-snapshot/<repository relative path>; exact bytes for every frozen source",
        "controlled_repeat_2": "A mid-work exact-count threshold 45000 until first actual A compact; otherwise native 128K/160K",
        "formal_limit_calibration": "Pilot 80 generations/175 outbound reached cap after 11 Turns at USD0.057428625; 1500/3500 bounded formal allowance retains USD8/4h/16compacts/40M",
        "disclosure_policy": "mandatory anonymous semantic review; no_question at most 2 nonconsecutive neutral reminders, then bounded incomplete closure; unknown_subtopics quote actual question only",
    }
    destination.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return data


def verify(data):
    if source_hashes() != data["source_sha256"]:
        raise RuntimeError(
            "Frozen experiment sources changed; stop before provider dispatch"
        )
