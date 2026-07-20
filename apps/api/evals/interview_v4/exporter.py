"""Read-only session exporter with deterministic direct-identifier redaction.

The exporter never mutates interview/document repositories.  Automated
redaction is intentionally marked ``redaction_pending_review`` because names,
rare incidents and business secrets require human review before a real case may
be committed to the repository.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from evals.interview_v4.contracts import EvalCaseManifest, GoldContract


_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("EMAIL", re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")),
    ("UUID", re.compile(
        r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
        r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}\b"
    )),
    ("URL", re.compile(r"https?://[^\s<>'\"]+", re.IGNORECASE)),
    ("PHONE", re.compile(
        r"(?<!\d)(?:\+?886[-\s]?)?(?:0?9\d{2}[-\s]?\d{3}[-\s]?\d{3}|"
        r"0\d{1,2}[-\s]?\d{3,4}[-\s]?\d{4})(?!\d)"
    )),
)
_OPAQUE_SHA256 = re.compile(r"sha256:[0-9a-fA-F]{64}\Z")


@dataclass
class RedactionReport:
    counts: Counter[str] = field(default_factory=Counter)
    replacement_count: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "pattern_counts": dict(sorted(self.counts.items())),
            "explicit_replacement_count": self.replacement_count,
        }


class Deidentifier:
    """Stable per-export redaction; does not claim to detect personal names."""

    def __init__(self, replacements: Mapping[str, str] | None = None):
        self._replacements = sorted(
            ((str(key), str(value)) for key, value in (replacements or {}).items() if key),
            key=lambda pair: len(pair[0]),
            reverse=True,
        )
        self._tokens: dict[tuple[str, str], str] = {}
        self.report = RedactionReport()

    def _token(self, kind: str, value: str) -> str:
        key = (kind, value)
        if key not in self._tokens:
            number = sum(1 for existing_kind, _ in self._tokens if existing_kind == kind) + 1
            self._tokens[key] = f"[{kind}_{number}]"
        return self._tokens[key]

    def text(self, value: str) -> str:
        result = value
        for source, replacement in self._replacements:
            occurrences = result.count(source)
            if occurrences:
                result = result.replace(source, replacement)
                self.report.replacement_count += occurrences
        for kind, pattern in _PATTERNS:
            def replace(match: re.Match[str], *, _kind=kind) -> str:
                self.report.counts[_kind] += 1
                return self._token(_kind, match.group(0))
            result = pattern.sub(replace, result)
        return result

    def value(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {self.text(str(key)): self.value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self.value(item) for item in value]
        if isinstance(value, tuple):
            return [self.value(item) for item in value]
        return value


def find_direct_identifiers(value: Any) -> list[dict[str, str]]:
    """Return pattern kind/path only; never echo the sensitive match."""
    findings: list[dict[str, str]] = []

    def walk(node: Any, path: str) -> None:
        if isinstance(node, str):
            # A digest can randomly contain phone-like digit runs. It is an
            # opaque one-way identifier, not source text, and scanning it makes
            # privacy results probabilistic.
            if _OPAQUE_SHA256.fullmatch(node):
                return
            for kind, pattern in _PATTERNS:
                if pattern.search(node):
                    findings.append({"kind": kind, "path": path})
        elif isinstance(node, dict):
            for key, item in node.items():
                walk(item, f"{path}.{key}" if path else str(key))
        elif isinstance(node, list):
            for index, item in enumerate(node):
                walk(item, f"{path}[{index}]")

    walk(value, "")
    return findings


def _jsonable_row(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name in fields:
        value = getattr(row, name, None)
        if hasattr(value, "isoformat"):
            value = value.isoformat()
        result[name] = value
    return result


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _unavailable_fixture(fixture: str, reason: str) -> dict[str, Any]:
    return {
        "schema_version": "unavailable_fixture.v0.1",
        "available": False,
        "fixture": fixture,
        "reason": reason,
    }


async def export_session_case(
    *,
    repo,
    session_id,
    initial_document: dict[str, Any] | None,
    reference_snapshot: dict[str, Any] | None,
    output_root: str | Path,
    case_id: str,
    source_hash_salt: str,
    role_family: str,
    risk_tags: list[str],
    initial_state: dict[str, Any] | None = None,
    observed_document: dict[str, Any] | None = None,
    replacements: Mapping[str, str] | None = None,
    locale: str = "zh-TW",
    test_data: bool = False,
) -> Path:
    """Export one session without changing DB state.

    ``source_hash_salt`` is required so repository artifacts cannot be joined
    back to raw UUIDs with an unsalted dictionary attack.  The salt itself is
    not written.  The caller must perform manual privacy review afterwards.
    """
    if not source_hash_salt:
        raise ValueError("source_hash_salt is required and is never written to artifacts")
    session = await repo.get(session_id)
    if session is None:
        raise LookupError(f"interview session not found: {session_id}")
    turns = await repo.list_turns(session_id)
    reviews = await repo.list_review_events(session_id)
    calls = await repo.list_llm_calls(session_id)

    deid = Deidentifier(replacements)
    transcript_rows = [
        {
            "seq": int(turn.seq),
            "role": str(turn.role),
            "text": deid.text(str(turn.text)),
        }
        for turn in turns
    ]
    observed_state = deid.value({
        "phase": getattr(session, "phase", None),
        "focus": getattr(session, "focus", {}) or {},
        "counters": getattr(session, "counters", {}) or {},
        "human_touched": getattr(session, "human_touched", []) or [],
        "ledger_state": getattr(session, "ledger_state", {}) or {},
    })
    document = deid.value(initial_document) if initial_document is not None else _unavailable_fixture(
        "initial_document",
        "Production history retained only the latest mutable draft at export time.",
    )
    state = deid.value(initial_state) if initial_state is not None else _unavailable_fixture(
        "initial_state",
        "Production history did not retain a turn-zero session-state snapshot.",
    )
    refs = deid.value(reference_snapshot) if reference_snapshot is not None else _unavailable_fixture(
        "reference_snapshot",
        "The immutable reference snapshot used by the historical run was not persisted.",
    )
    observed_doc = deid.value(observed_document) if observed_document is not None else None
    review_rows = deid.value([
        _jsonable_row(review, ("seq", "doc_path", "decision", "op_meta", "created_at"))
        for review in reviews
    ])
    call_rows = deid.value([
        _jsonable_row(call, (
            "turn_seq", "role", "stage", "provider", "model", "requested_model",
            "resolved_model", "attempt_count", "outcome", "prompt_hash",
            "tool_schema_hash", "duration_ms", "prompt_tokens", "completion_tokens",
            "tool_calls", "guard_verdicts", "created_at",
        ))
        for call in calls
    ])
    scan_target = {
        "transcript": transcript_rows,
        "state": state,
        "observed_session_state": observed_state,
        "document": document,
        "observed_document": observed_doc,
        "reference_snapshot": refs,
        "reviews": review_rows,
        "calls": call_rows,
    }
    residual = find_direct_identifiers(scan_target)
    source_fingerprint = hashlib.sha256(
        f"{source_hash_salt}:{session_id}".encode("utf-8")
    ).hexdigest()

    replay_limitations = ["Gold labels and episode boundaries have not been annotated."]
    if not test_data:
        replay_limitations.insert(
            0,
            "Automated direct-identifier redaction does not detect names, rare events or business secrets.",
        )
    if initial_document is None:
        replay_limitations.append("Initial document fixture is unavailable; the observed export-time document is not a replay start state.")
    if initial_state is None:
        replay_limitations.append("Turn-zero session state is unavailable; export-time session state is observational only.")
    if reference_snapshot is None:
        replay_limitations.append("Historical immutable reference snapshot is unavailable and must not be reconstructed from current data for a scored replay.")

    manifest_data = {
        "schema_version": "interview_eval_case.v0.1",
        "case_id": case_id,
        "split": "development",
        "source_type": "migrated_provisional" if test_data else "real_incident",
        "locale": locale,
        "role_family": role_family,
        "risk_tags": risk_tags,
        "privacy": {
            "status": "synthetic" if test_data else "redaction_pending_review",
            "version": "test-data-owner-confirmed.v0.1" if test_data else "auto-direct-id.v0.1",
            "approved_use": "architecture_eval",
            "raw_source_in_repo": False,
            "residual_scan_passed": not residual,
            "manual_review_required": not test_data,
        },
        "initial": {
            "document_fixture": "initial_document.json",
            "session_state_fixture": "initial_state.json",
            "reference_snapshot": "reference_snapshot.json",
            "review_events_fixture": "review_events.json",
        },
        "transcript": "transcript.jsonl",
        "gold": "gold.json",
        "source_audit": "source_audit.json",
        "annotation": {
            "status": "draft",
            "annotator_roles": [],
            "guideline_version": "claim-label.v0.1",
            "adjudication_notes": "adjudication.md",
        },
        "replay": {
            "ready": False,
            "episode_boundaries": [],
            "limitations": replay_limitations,
        },
        "applicable_graders": ["case_integrity", "quote_validity", "source_subject"],
    }
    manifest = EvalCaseManifest.model_validate(manifest_data)
    gold = GoldContract(
        schema_version="interview_eval_gold.v0.1",
        case_id=case_id,
        unresolved_gaps=["Case exported but not yet annotated or domain-reviewed."],
    )

    root = Path(output_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    destination = root / case_id
    if destination.exists():
        raise FileExistsError(f"refusing to overwrite existing case: {destination}")
    temp = Path(tempfile.mkdtemp(prefix=f".{case_id}.", dir=root))
    try:
        _write_json(temp / "case.json", manifest.model_dump(mode="json"))
        (temp / "transcript.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in transcript_rows),
            encoding="utf-8",
        )
        _write_json(temp / "initial_document.json", document)
        _write_json(temp / "initial_state.json", state)
        _write_json(temp / "reference_snapshot.json", refs)
        _write_json(temp / "review_events.json", review_rows)
        _write_json(temp / "observed_session_state.json", observed_state)
        if observed_doc is not None:
            _write_json(temp / "observed_document.json", observed_doc)
        _write_json(temp / "gold.json", gold.model_dump(mode="json"))
        _write_json(temp / "source_audit.json", {
            "schema_version": "interview_eval_source_audit.v0.1",
            "source_fingerprint": f"sha256:{source_fingerprint}",
            "redaction": deid.report.as_dict(),
            "residual_direct_identifier_findings": residual,
            "llm_calls": call_rows,
            "fixture_provenance": {
                "initial_document": "provided" if initial_document is not None else "unavailable",
                "initial_state": "provided" if initial_state is not None else "unavailable",
                "reference_snapshot": "provided" if reference_snapshot is not None else "unavailable",
            },
            "observed_artifacts": {
                "session_state": "observed_session_state.json",
                "document": "observed_document.json" if observed_doc is not None else None,
                "stage": "latest_at_export_not_replay_initial",
            },
            "limitations": [
                "The production audit table does not contain complete prompts, raw responses or state deltas.",
                *([] if test_data else [
                    "Manual privacy review is mandatory before changing privacy.status to deidentified."
                ]),
            ],
        })
        (temp / "adjudication.md").write_text(
            "# Case adjudication\n\n"
            + ("Status: draft test data; domain annotation pending.\n\n" if test_data else
               "Status: draft; automated redaction pending manual privacy and domain review.\n\n")
            + "Do not set `replay.ready=true` until episode boundaries, initial fixtures and claim-level gold "
            "have been checked.\n",
            encoding="utf-8",
        )
        temp.replace(destination)
    except Exception:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    return destination
