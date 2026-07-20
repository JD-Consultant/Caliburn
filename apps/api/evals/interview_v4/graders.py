"""Deterministic graders for portable interview eval artifacts."""
from __future__ import annotations

from typing import Any, Iterable

from app.interview.verify import normalize
from evals.interview_v4.contracts import GraderResult, TranscriptTurn
from evals.interview_v4.loader import CaseBundle, CaseIntegrityError, load_case
from evals.source_score import source_score


def grade_case_integrity(case_dir) -> GraderResult:
    try:
        bundle = load_case(case_dir)
    except (CaseIntegrityError, ValueError) as exc:
        return GraderResult(
            grader="case_integrity",
            passed=False,
            severity="critical",
            reason=str(exc),
        )
    return GraderResult(
        grader="case_integrity",
        passed=True,
        reason=f"ok: {bundle.manifest.case_id}, {len(bundle.transcript)} turns",
    )


def _source_parts(evidence: dict[str, Any]) -> tuple[int | None, str, str | None]:
    source = evidence.get("source") or {}
    turn_seq = source.get("turn_seq", source.get("turn_id"))
    quote = source.get("quote") or ""
    if isinstance(quote, dict):
        turn_seq = quote.get("turn_seq", quote.get("turn_id", turn_seq))
        quote = quote.get("text") or ""
    speaker = source.get("speaker")
    return turn_seq, str(quote), speaker


def grade_evidence_quotes(
    evidence: Iterable[dict[str, Any]], transcript: Iterable[TranscriptTurn]
) -> GraderResult:
    turns = {turn.seq: turn for turn in transcript}
    details: list[dict[str, Any]] = []
    for index, item in enumerate(evidence):
        turn_seq, quote, speaker = _source_parts(item)
        turn = turns.get(turn_seq)
        reasons: list[str] = []
        if turn is None:
            reasons.append("missing_turn")
        elif turn.role != "employee":
            reasons.append("non_employee_turn")
        if speaker not in (None, "employee"):
            reasons.append("source_speaker_not_employee")
        if not quote:
            reasons.append("empty_quote")
        elif turn is not None and normalize(quote) not in normalize(turn.text):
            reasons.append("quote_not_in_turn")
        details.append({
            "index": index,
            "evidence_id": item.get("evidence_id"),
            "turn_seq": turn_seq,
            "ok": not reasons,
            "reasons": reasons,
        })
    if not details:
        return GraderResult(
            grader="quote_validity",
            passed=None,
            applicable=False,
            reason="not applicable: no output evidence",
        )
    failed = [detail for detail in details if not detail["ok"]]
    return GraderResult(
        grader="quote_validity",
        passed=not failed,
        score=(len(details) - len(failed)) / len(details),
        severity="critical" if failed else None,
        reason=f"{len(details) - len(failed)}/{len(details)} evidence sources valid",
        details=details,
    )


def grade_projection_grounding(
    document: dict[str, Any],
    transcript: Iterable[TranscriptTurn],
    ref_codes: set[str],
    accepted: list[dict[str, Any]] | None = None,
) -> GraderResult:
    employee_turns = {turn.seq: turn.text for turn in transcript if turn.role == "employee"}
    result = source_score(
        document,
        turns=employee_turns,
        ref_codes=ref_codes,
        accepted=accepted,
    )
    if result["total"] == 0:
        return GraderResult(
            grader="projection_grounding",
            passed=None,
            applicable=False,
            reason="not applicable: no AI projection",
        )
    failed = [detail for detail in result["details"] if not detail["ok"]]
    return GraderResult(
        grader="projection_grounding",
        passed=not failed,
        score=result["score"],
        severity="critical" if failed else None,
        reason=f"unsupported_projection_count={len(failed)}",
        details=result["details"],
    )


def run_deterministic_graders(
    bundle: CaseBundle,
    *,
    final_document: dict[str, Any],
    final_state: dict[str, Any],
) -> list[GraderResult]:
    evidence = final_state.get("evidence") or []
    ref_codes = set(bundle.reference_snapshot.get("ref_codes") or [])
    return [
        grade_evidence_quotes(evidence, bundle.transcript),
        grade_projection_grounding(
            final_document,
            bundle.transcript,
            ref_codes,
            accepted=bundle.review_events,
        ),
    ]
