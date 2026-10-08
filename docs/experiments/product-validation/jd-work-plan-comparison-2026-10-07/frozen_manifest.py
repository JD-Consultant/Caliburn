"""Freeze new material bytes and actual production arm templates, without a key."""

import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from decimal import Decimal
from importlib.metadata import version
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OLD = HERE.with_name("interview-plan-comparison-2026-10-07")
sys.path.insert(0, str(OLD))
import manifest as predecessor
from caliburn.adapters.openai_pricing import GPT_6_LUNA_STANDARD_2026_09_30
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.planning_instructions import (
    FOCUS_INSTRUCTIONS,
    INTERVIEW_PLAN_INSTRUCTIONS,
)
from caliburn.agents.job_consultant.tools import consultant_tool_definitions

LIMITS = {
    "limit_usd": "4.00",
    "max_generations": 2600,
    "max_compacts": 32,
    "max_outbound": 6000,
    "max_counted_input": 150000000,
    "batch_deadline": None,
    "turn_observation_seconds": 700,
    "memory_observation_seconds": 180,
    "review_seconds": 300,
    "pilot_generations": 160,
    "pilot_compacts": 2,
}
PLAN_GATE = {
    "revision": "recoverable-input-rejections-recorded-v2",
    "reason": "Formal ToolRejection permits model input correction; requiring zero rejection would select P2 samples by random tool behavior. Prior v1 strict failure remains unchanged.",
    "recoverable_codes": {
        "read_interview_plan": ["invalid_arguments"],
        "edit_interview_plan": [
            "invalid_arguments",
            "invalid_patch",
            "patch_context_not_found",
            "ambiguous_patch_context",
            "patch_limit_exceeded",
            "write_result_limit_exceeded",
        ],
    },
    "unknown_scope_persistence_or_app_capacity_rejections": "stop before next outbound",
    "receipt": "actual creation, local patch, formal readback and subsequent Turn full-text use; retain all rejection costs and unfinished content edits",
}
PILOT = [("warehouse", "P1", 1), ("warehouse", "P2", 1)]
FORMAL = [
    ("warehouse", "P1", 1),
    ("warehouse", "P2", 1),
    ("course_admin", "P2", 1),
    ("course_admin", "P1", 1),
    ("warehouse", "P2", 2),
    ("warehouse", "P1", 2),
    ("course_admin", "P1", 2),
    ("course_admin", "P2", 2),
]


def arm_templates():
    common = CONSULTANT_INSTRUCTIONS + "\n\n" + FOCUS_INSTRUCTIONS
    templates = {
        group: {
            "instructions": common
            + ("\n\n" + INTERVIEW_PLAN_INSTRUCTIONS if group == "P2" else ""),
            "tools": consultant_tool_definitions(interview_plans_enabled=group == "P2"),
        }
        for group in ["P1", "P2"]
    }
    plan = {"read_interview_plan", "edit_interview_plan"}
    if [
        item for item in templates["P2"]["tools"] if item.get("name") not in plan
    ] != templates["P1"]["tools"]:
        raise ValueError("P1/P2 ordered tools differ beyond Plan")
    for group in templates:
        if "read_jd_changes" not in {
            item.get("name") for item in templates[group]["tools"]
        }:
            raise ValueError("Both arms must retain existing Changes")
    return templates


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    hashes = predecessor.source_hashes()
    extras = [
        *HERE.glob("*.py"),
        *HERE.glob("*.md"),
        HERE / "private_facts.json",
        OLD / "append_stream.py",
    ]
    # The reused observer is loaded independently of its historical entrypoint.
    extras += [OLD / "diagnostics/repaired_comparison.py"]
    for path in extras:
        hashes[path.relative_to(ROOT).as_posix()] = sha(path)
    return dict(sorted(hashes.items()))


def database_locator(url):
    from urllib.parse import urlsplit

    parts = urlsplit(url)
    if (
        parts.scheme not in {"postgresql", "postgresql+psycopg"}
        or parts.hostname != "127.0.0.1"
        or not parts.path.endswith("_test")
        or parts.query
        or parts.fragment
    ):
        raise ValueError("Use an explicit loopback PostgreSQL _test database")
    return f"{parts.hostname}:{parts.port or 5432}{parts.path}"


def freeze(
    destination, *, limit_usd, authorization_reference, database_url, carry=None
):
    if not Decimal(limit_usd).is_finite() or not 0 < Decimal(limit_usd) <= Decimal(
        LIMITS["limit_usd"]
    ):
        raise ValueError(
            "New batch requires an explicit finite limit within the proposal"
        )
    if not authorization_reference.strip():
        raise ValueError("Record the effective user authorization reference")
    hashes = source_hashes()
    snapshot = destination.parent / "source-snapshot"
    snapshot.mkdir()
    for relative, expected in hashes.items():
        contents = (ROOT / relative).read_bytes()
        if hashlib.sha256(contents).hexdigest() != expected:
            raise RuntimeError("Source changed during freeze")
        target = snapshot / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(contents)
    from dataclasses import asdict

    data = {
        "revision": "jd-work-plan-mechanical-carry-v2"
        if carry
        else "jd-work-plan-new-materials-v1",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "authorization_reference": authorization_reference,
        "model": "gpt-6-luna",
        "reasoning_effort": "high",
        "runtime": {
            "python": platform.python_version(),
            "dependencies": {
                package: version(package)
                for package in [
                    "openai",
                    "langgraph",
                    "pydantic",
                    "SQLAlchemy",
                    "httpx2",
                ]
            },
        },
        "pricing": asdict(GPT_6_LUNA_STANDARD_2026_09_30),
        "max_output_tokens": 16384,
        "service_tier": "default",
        "rag_enabled": False,
        "initial_jd": "empty",
        "initial_memory": "empty",
        "initial_plan": "null",
        "database": database_locator(database_url),
        "schema_namespace": "intplan_jdwork_",
        "limits": {**LIMITS, "limit_usd": str(Decimal(limit_usd))},
        "arm_templates": arm_templates(),
        "pilot": PILOT,
        "formal": FORMAL,
        "turn_limits": {"pilot": 6, "formal": 20},
        "manual_edit_after_completed_turn": 10,
        "controlled_repeat_2": "45000 until official saved and read-verified A adopted within-Work C; B unchanged",
        "disclosure_policy": "mandatory independent anonymous per-subquestion review; exact accepted source; 300 seconds; no keyword dispatch",
        "source_sha256": hashes,
        "plan_mechanism_gate": PLAN_GATE,
        "pilot_accounting": "160 generations and 2 compacts cumulative across mechanical pilot revisions; no pilot phase reset",
    }
    if carry is not None:
        from dataclasses import asdict

        current_pricing = json.loads(
            json.dumps(asdict(GPT_6_LUNA_STANDARD_2026_09_30), default=str)
        )
        if current_pricing != carry["prior_pricing"] or Decimal(limit_usd) > Decimal(
            carry["prior_limits"]["limit_usd"]
        ):
            raise ValueError(
                "Carried research cannot silently change prices or increase its total budget"
            )
        data["carry"] = carry
    destination.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
    )
    return data


def verify(data):
    if (
        source_hashes() != data["source_sha256"]
        or arm_templates() != data["arm_templates"]
    ):
        raise RuntimeError(
            "Frozen source or actual arm template changed; stop before outbound"
        )
    if data.get("carry"):
        from carry import verify_carry

        verify_carry(HERE / "runs", data["carry"])
