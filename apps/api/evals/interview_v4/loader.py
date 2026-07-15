"""Load and cross-validate a complete interview evaluation case bundle."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evals.interview_v4.contracts import EvalCaseManifest, GoldContract, TranscriptTurn
from app.interview.verify import normalize


class CaseIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class CaseBundle:
    root: Path
    manifest: EvalCaseManifest
    transcript: tuple[TranscriptTurn, ...]
    gold: GoldContract
    initial_document: dict[str, Any]
    initial_state: dict[str, Any]
    reference_snapshot: dict[str, Any]
    review_events: list[dict[str, Any]]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaseIntegrityError(f"cannot read JSON {path}: {exc}") from exc


def _resolve_file(root: Path, relative: str) -> Path:
    root_resolved = root.resolve()
    path = (root / relative).resolve()
    if path.parent != root_resolved and root_resolved not in path.parents:
        raise CaseIntegrityError(f"case file escapes case root: {relative}")
    if not path.is_file():
        raise CaseIntegrityError(f"case file does not exist: {relative}")
    return path


def _read_transcript(path: Path) -> tuple[TranscriptTurn, ...]:
    rows: list[TranscriptTurn] = []
    for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(TranscriptTurn.model_validate_json(line))
        except Exception as exc:  # pydantic error includes the field path
            raise CaseIntegrityError(f"invalid transcript {path}:{lineno}: {exc}") from exc
    if not rows:
        raise CaseIntegrityError("transcript must contain at least one turn")
    seqs = [row.seq for row in rows]
    if seqs != sorted(seqs) or len(seqs) != len(set(seqs)):
        raise CaseIntegrityError("transcript seq must be strictly increasing and unique")
    return tuple(rows)


def _validate_gold_sources(bundle: CaseBundle) -> None:
    turns = {turn.seq: turn for turn in bundle.transcript}
    evidence_groups = (
        ("required_evidence", bundle.gold.required_evidence, "required"),
        ("optional_evidence", bundle.gold.optional_evidence, "optional"),
        ("forbidden_evidence", bundle.gold.forbidden_evidence, "forbidden"),
    )
    for group_name, group, expected_requirement in evidence_groups:
        for item in group:
            if item.requirement != expected_requirement:
                raise CaseIntegrityError(
                    f"{item.label_id} is in {group_name} but requirement={item.requirement}"
                )
            turn = turns.get(item.source.turn_seq)
            if turn is None:
                raise CaseIntegrityError(
                    f"{item.label_id} points to missing turn {item.source.turn_seq}"
                )
            if turn.role != "employee":
                raise CaseIntegrityError(
                    f"{item.label_id} points to non-employee turn {item.source.turn_seq}"
                )
            if normalize(item.source.quote) not in normalize(turn.text):
                raise CaseIntegrityError(
                    f"{item.label_id} quote is not in employee turn {item.source.turn_seq}"
                )


def load_case(case_dir: str | Path) -> CaseBundle:
    root = Path(case_dir).resolve()
    manifest_path = _resolve_file(root, "case.json")
    manifest = EvalCaseManifest.model_validate(_read_json(manifest_path))
    transcript = _read_transcript(_resolve_file(root, manifest.transcript))
    gold = GoldContract.model_validate(_read_json(_resolve_file(root, manifest.gold)))
    if gold.case_id != manifest.case_id:
        raise CaseIntegrityError(
            f"gold case_id {gold.case_id!r} != manifest case_id {manifest.case_id!r}"
        )
    initial_document = _read_json(_resolve_file(root, manifest.initial.document_fixture))
    initial_state = _read_json(_resolve_file(root, manifest.initial.session_state_fixture))
    reference_snapshot = _read_json(_resolve_file(root, manifest.initial.reference_snapshot))
    review_events = _read_json(_resolve_file(root, manifest.initial.review_events_fixture))
    if not isinstance(initial_document, dict) or not isinstance(initial_state, dict):
        raise CaseIntegrityError("initial document and state must be JSON objects")
    if not isinstance(reference_snapshot, dict) or not isinstance(review_events, list):
        raise CaseIntegrityError("reference snapshot must be an object and review events a list")
    if manifest.source_audit:
        _resolve_file(root, manifest.source_audit)
    _resolve_file(root, manifest.annotation.adjudication_notes)
    bundle = CaseBundle(
        root=root,
        manifest=manifest,
        transcript=transcript,
        gold=gold,
        initial_document=initial_document,
        initial_state=initial_state,
        reference_snapshot=reference_snapshot,
        review_events=review_events,
    )
    _validate_gold_sources(bundle)
    employee_seqs = {turn.seq for turn in transcript if turn.role == "employee"}
    for boundary in manifest.replay.episode_boundaries:
        if boundary.opened_employee_seq not in employee_seqs:
            raise CaseIntegrityError(
                f"episode open seq {boundary.opened_employee_seq} is not an employee turn"
            )
        if boundary.closed_employee_seq not in employee_seqs:
            raise CaseIntegrityError(
                f"episode close seq {boundary.closed_employee_seq} is not an employee turn"
            )
    return bundle
