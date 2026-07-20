"""Opt-in immutable capture contracts for replayable interview evaluations.

Production interview behavior does not depend on these helpers.  Capture is
enabled only for explicitly consented sessions and stores restricted artifacts
in dedicated tables rather than in Git.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.interview import agenda as AG
from app.interview.attitudes import ATTITUDES_SYS
from app.interview.consultant import CONSULTANT_SYSTEM
from app.interview.curation import CURATION_SYS
from app.interview.harvest import HARVEST_SYS
from app.interview.scribe import SCRIBE_SYS, _doc_ocs_codes
from app.interview.tools import CONSULTANT_TOOLS
from app.interview.trace_utils import canonical_hash


Sha256 = str


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvalSessionStart(_StrictModel):
    schema_version: Literal["interview_eval_session_start.v0.1"]
    consent_policy_version: str = Field(min_length=1)
    locale: str = Field(min_length=1)
    initial_document_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    initial_state_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reference_snapshot_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    prompt_bundle_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    tool_schema_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    code_git_sha: str = Field(min_length=1)
    dirty_worktree: bool
    limitations: list[str] = Field(default_factory=list)


class ModelCallTrace(_StrictModel):
    schema_version: Literal["interview_model_call_trace.v0.2"]
    turn_seq: int = Field(ge=0)
    stage: Literal[
        "consultant",
        "curation",
        "scribe",
        "harvest",
        "attitudes",
        "backstop",
    ]
    provider: str = Field(min_length=1)
    requested_model: str = Field(min_length=1)
    resolved_model: str | None = None
    attempt_count: int = Field(ge=1)
    prompt_hash: Sha256 | None = Field(default=None, pattern=r"^sha256:[0-9a-f]{64}$")
    tool_schema_hash: Sha256 | None = Field(
        default=None, pattern=r"^sha256:[0-9a-f]{64}$"
    )
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    latency_ms: int = Field(ge=0)
    outcome: Literal[
        "success",
        "timeout",
        "parse_failure",
        "provider_failure",
        "fallback",
    ]


class VerifyFinding(_StrictModel):
    schema_version: Literal["interview_verify_finding.v0.2"]
    op_index: int = Field(ge=0)
    check: Literal["contract", "quote", "src", "permission", "invariant", "hygiene"]
    reason_code: str = Field(min_length=1)
    target_kind: Literal[
        "task", "output", "indicator", "knowledge", "skill", "attitude", "header", "other"
    ]
    retryable: bool


class TurnTrajectory(_StrictModel):
    schema_version: Literal["interview_turn_trajectory.v0.1"]
    turn_seq: int = Field(ge=1)
    state_before_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    document_before_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    state_after_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    document_after_hash: Sha256 = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    model_call_ids: list[str] = Field(default_factory=list)
    stop_or_transition_reason: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)


def prompt_bundle_hash() -> str:
    skills_root = Path(__file__).resolve().parent / "skills"
    skills = {
        str(path.relative_to(skills_root)).replace("\\", "/"): path.read_text(encoding="utf-8")
        for path in sorted(skills_root.rglob("SKILL.md"))
    }
    return canonical_hash({
        "consultant": CONSULTANT_SYSTEM,
        "curation": CURATION_SYS,
        "scribe": SCRIBE_SYS,
        "harvest": HARVEST_SYS,
        "attitudes": ATTITUDES_SYS,
        "skills": skills,
    })


def static_tool_schema_hash() -> str:
    return canonical_hash(CONSULTANT_TOOLS + AG.agenda_tools([]))


def reference_codes(document: dict[str, Any], selected_codes: list[str]) -> list[str]:
    codes = list(_doc_ocs_codes(document))
    for code in selected_codes:
        if code and code not in codes:
            codes.append(code)
    return codes


async def build_reference_snapshot(knowledge, codes: list[str]) -> dict[str, Any]:
    async def fetch(code: str):
        tasks, competencies = await asyncio.gather(
            knowledge.occupation_tasks(code),
            knowledge.competencies(code),
        )
        return code, tasks.model_dump(mode="json"), competencies.model_dump(mode="json")

    rows = await asyncio.gather(*(fetch(code) for code in codes))
    snapshot: dict[str, Any] = {
        "schema_version": "interview_reference_snapshot.v0.1",
        "selected_ocs_codes": list(codes),
        "tasks_by_ocs": {code: tasks for code, tasks, _ in rows},
        "competencies_by_ocs": {code: competencies for code, _, competencies in rows},
    }
    snapshot["content_hash"] = canonical_hash(snapshot)
    return snapshot


CAPTURE_SCHEMA_MODELS: dict[str, type[BaseModel]] = {
    "eval-session-start.schema.json": EvalSessionStart,
    "model-call-trace.schema.json": ModelCallTrace,
    "turn-trajectory.schema.json": TurnTrajectory,
    "verify-finding.schema.json": VerifyFinding,
}
