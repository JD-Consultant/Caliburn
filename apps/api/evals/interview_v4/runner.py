"""Isolated, filesystem-backed C0 replay runner.

The runner never opens a production repository.  A processor receives deep
copies of case fixtures and returns explicit deltas.  The current v3
scribe/harvest adapter is provided below; tests may inject a deterministic
processor without an LLM.
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from evals.interview_v4.contracts import EvalRunArtifact, TrajectoryStep
from evals.interview_v4.graders import run_deterministic_graders
from evals.interview_v4.loader import CaseBundle, load_case


RUNNER_VERSION = "interview-c0-replay.v0.1"


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_json_bytes(value)).hexdigest()


def _case_content_hash(bundle: CaseBundle) -> str:
    return _digest({
        "manifest": bundle.manifest.model_dump(mode="json"),
        "transcript": [turn.model_dump(mode="json") for turn in bundle.transcript],
        "gold": bundle.gold.model_dump(mode="json"),
        "initial_document": bundle.initial_document,
        "initial_state": bundle.initial_state,
        "reference_snapshot": bundle.reference_snapshot,
        "review_events": bundle.review_events,
    })


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@dataclass
class ProcessorResult:
    document: dict[str, Any]
    state: dict[str, Any]
    candidate_output: dict[str, Any] = field(default_factory=dict)
    verifier_result: dict[str, Any] = field(default_factory=dict)
    projection_delta: list[dict[str, Any]] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)


class C0Processor(Protocol):
    async def process_employee_turn(
        self,
        *,
        document: dict[str, Any],
        state: dict[str, Any],
        employee_turns: dict[int, str],
        turn_seq: int,
    ) -> ProcessorResult: ...

    async def close_episode(
        self,
        *,
        document: dict[str, Any],
        state: dict[str, Any],
        employee_turns: dict[int, str],
        episode: dict[str, Any],
    ) -> ProcessorResult: ...

    async def finish(
        self,
        *,
        document: dict[str, Any],
        state: dict[str, Any],
        employee_turns: dict[int, str],
    ) -> ProcessorResult: ...


class SnapshotKnowledge:
    """Minimal immutable knowledge port used by current scribe/harvest replay.

    Snapshot shape::

        {"content_hash": "sha256:...", "competencies_by_ocs": {"CODE": {...}}}

    Missing selected codes fail loudly rather than falling through to a live
    corpus or silently changing the exam.
    """

    def __init__(self, snapshot: dict[str, Any]):
        from app.core.knowledge_dto import CompetencyPool

        self._model = CompetencyPool
        self._pools = copy.deepcopy(snapshot.get("competencies_by_ocs") or {})
        declared_hash = snapshot.get("content_hash")
        self.snapshot_id = str(declared_hash or _digest(snapshot))

    async def competencies(self, ocs_code: str):
        if ocs_code not in self._pools:
            raise KeyError(f"reference snapshot missing competencies for {ocs_code}")
        payload = copy.deepcopy(self._pools[ocs_code])
        if not payload.get("ocs_code"):
            payload["ocs_code"] = ocs_code
        return self._model.model_validate(payload)


class CurrentC0Processor:
    """Adapter around the current v3 scribe and episode harvest passes.

    ``knowledge`` must be backed by the case's immutable reference snapshot.
    This adapter cannot prove that property itself, so the caller provides a
    snapshot id which is recorded in limitations/outputs.
    """

    def __init__(
        self,
        *,
        llm,
        knowledge,
        header_codes: set[str] | None = None,
        ref_ocs_codes: tuple[str, ...] = (),
        reference_snapshot_id: str,
    ):
        if not reference_snapshot_id:
            raise ValueError("reference_snapshot_id is required")
        self.llm = llm
        self.knowledge = knowledge
        self.header_codes = header_codes or set()
        self.ref_ocs_codes = ref_ocs_codes
        self.reference_snapshot_id = reference_snapshot_id

    @staticmethod
    def _result(document, state, result, phase: str, snapshot_id: str) -> ProcessorResult:
        new_document = result.new_doc if result.new_doc is not None else document
        return ProcessorResult(
            document=copy.deepcopy(new_document),
            state=copy.deepcopy(state),
            candidate_output={
                "phase": phase,
                "landed_ops": copy.deepcopy(result.ops),
                "records_failed": result.records_failed,
                "progressed": result.progressed,
            },
            verifier_result={"guard_log": list(result.guard_log)},
            projection_delta=copy.deepcopy(result.ops),
            limitations=[
                f"reference_snapshot_id={snapshot_id}",
                "Current v3 passes do not expose raw model response or per-call token usage to this adapter.",
            ],
        )

    async def process_employee_turn(self, *, document, state, employee_turns, turn_seq):
        from app.interview.scribe import scribe_pass

        result = await scribe_pass(
            self.llm,
            self.knowledge,
            doc=copy.deepcopy(document),
            turns=dict(employee_turns),
            turn_id=turn_seq,
            header_codes=set(self.header_codes),
            ref_ocs_codes=self.ref_ocs_codes,
        )
        return self._result(document, state, result, "scribe", self.reference_snapshot_id)

    async def close_episode(self, *, document, state, employee_turns, episode):
        from app.interview.harvest import harvest_pass

        result = await harvest_pass(
            self.llm,
            self.knowledge,
            doc=copy.deepcopy(document),
            turns=dict(employee_turns),
            episode=copy.deepcopy(episode),
            header_codes=set(self.header_codes),
            ref_ocs_codes=self.ref_ocs_codes,
        )
        return self._result(document, state, result, "harvest", self.reference_snapshot_id)

    async def finish(self, *, document, state, employee_turns):
        return ProcessorResult(
            document=copy.deepcopy(document),
            state=copy.deepcopy(state),
            candidate_output={"phase": "finish", "action": "no_op"},
            verifier_result={"reason": "C0 analysis replay does not call production run_finish"},
            limitations=["Production attitude/final reconciliation is outside C0 analysis replay v0.1."],
        )


def _combine(first: ProcessorResult, second: ProcessorResult) -> ProcessorResult:
    return ProcessorResult(
        document=second.document,
        state=second.state,
        candidate_output={
            "turn": first.candidate_output,
            "episode_close": second.candidate_output,
        },
        verifier_result={
            "turn": first.verifier_result,
            "episode_close": second.verifier_result,
        },
        projection_delta=first.projection_delta + second.projection_delta,
        limitations=first.limitations + second.limitations,
    )


async def run_c0_case(
    case_dir: str | Path,
    *,
    processor: C0Processor,
    output_root: str | Path,
    git_sha: str,
    dirty_worktree: bool,
    trial_index: int = 1,
    allow_provisional: bool = False,
) -> Path:
    """Replay a case into a new immutable artifact directory."""
    bundle: CaseBundle = load_case(case_dir)
    if not bundle.manifest.replay.ready and not allow_provisional:
        raise ValueError(
            f"case {bundle.manifest.case_id} is provisional; set replay.ready only after adjudication"
        )
    if not git_sha:
        raise ValueError("git_sha is required for reproducible artifacts")
    document = copy.deepcopy(bundle.initial_document)
    state = copy.deepcopy(bundle.initial_state)
    employee_turns: dict[int, str] = {}
    boundaries = {
        boundary.closed_employee_seq: boundary
        for boundary in bundle.manifest.replay.episode_boundaries
    }
    trajectory_payloads: list[tuple[int, dict[str, Any], ProcessorResult]] = []
    limitations = list(bundle.manifest.replay.limitations)

    for turn in bundle.transcript:
        if turn.role != "employee":
            continue
        employee_turns[turn.seq] = turn.text
        state_before = copy.deepcopy(state)
        result = await processor.process_employee_turn(
            document=copy.deepcopy(document),
            state=copy.deepcopy(state),
            employee_turns=dict(employee_turns),
            turn_seq=turn.seq,
        )
        if turn.seq in boundaries:
            boundary = boundaries[turn.seq]
            episode = {
                "target": boundary.target,
                "opened_seq": boundary.opened_employee_seq,
                "closed_seq": boundary.closed_employee_seq,
                "reason": boundary.reason,
            }
            close_result = await processor.close_episode(
                document=copy.deepcopy(result.document),
                state=copy.deepcopy(result.state),
                employee_turns=dict(employee_turns),
                episode=episode,
            )
            result = _combine(result, close_result)
        document, state = copy.deepcopy(result.document), copy.deepcopy(result.state)
        trajectory_payloads.append((turn.seq, state_before, result))
        limitations.extend(result.limitations)

    finish = await processor.finish(
        document=copy.deepcopy(document),
        state=copy.deepcopy(state),
        employee_turns=dict(employee_turns),
    )
    document, state = copy.deepcopy(finish.document), copy.deepcopy(finish.state)
    limitations.extend(finish.limitations)
    graders = run_deterministic_graders(bundle, final_document=document, final_state=state)

    run_id = f"run_{uuid.uuid4().hex}"
    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / bundle.manifest.case_id / run_id
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{run_id}.", dir=destination.parent))
    try:
        trajectory_refs: list[TrajectoryStep] = []
        for turn_seq, state_before, result in trajectory_payloads:
            step_dir = temp / "steps" / str(turn_seq)
            _write_json(step_dir / "state_before.json", state_before)
            _write_json(step_dir / "candidate_output.json", result.candidate_output)
            _write_json(step_dir / "verifier_result.json", result.verifier_result)
            _write_json(step_dir / "state_delta.json", {
                "before": _digest(state_before),
                "after": _digest(result.state),
                "changed": _digest(state_before) != _digest(result.state),
            })
            _write_json(step_dir / "projection_delta.json", result.projection_delta)
            prefix = f"steps/{turn_seq}"
            trajectory_refs.append(TrajectoryStep(
                turn_seq=turn_seq,
                state_before=f"{prefix}/state_before.json",
                candidate_output=f"{prefix}/candidate_output.json",
                verifier_result=f"{prefix}/verifier_result.json",
                state_delta=f"{prefix}/state_delta.json",
                projection_delta=f"{prefix}/projection_delta.json",
            ))
        _write_json(temp / "final_state.json", state)
        _write_json(temp / "final_document.json", document)
        _write_json(
            temp / "grader_results.json",
            [grader.model_dump(mode="json") for grader in graders],
        )
        artifact = EvalRunArtifact(
            schema_version="interview_eval_run.v0.1",
            run_id=run_id,
            case_id=bundle.manifest.case_id,
            case_content_hash=_case_content_hash(bundle),
            candidate="C0",
            trial_index=trial_index,
            git_sha=git_sha,
            dirty_worktree=dirty_worktree,
            started_at=datetime.now(timezone.utc).isoformat(),
            runner_version=RUNNER_VERSION,
            model_calls=[],
            trajectory=trajectory_refs,
            final={
                "state": "final_state.json",
                "document": "final_document.json",
                "grader_results": "grader_results.json",
            },
            limitations=list(dict.fromkeys(limitations + [
                "Model calls are empty unless a future processor exposes raw provider call artifacts."
            ])),
        )
        _write_json(temp / "run.json", artifact.model_dump(mode="json"))
        temp.replace(destination)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return destination
