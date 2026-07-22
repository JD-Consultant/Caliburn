"""Path-safe, hash-verified case/suite loader with hard gold isolation (V3-5 §6/§8).

``load_case_inputs`` returns the runtime-only document set; its type has no
gold/reference/adjudication field and ``run_trial`` never receives them.
``load_case_gold`` may re-read runtime files (grading needs the transcript),
but nothing on the runtime path imports gold. All hashes are computed from
parsed canonical JSON records, never from OS line endings (§6.2/§8.1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from pydantic import Field, ValidationError

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.evidence import EvidenceKind, Polarity
from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.domain.identifiers import Sha256, StableName
from app.interview_vnext.domain.interpretation import TurnInsufficiencyCode
from app.interview_vnext.domain.transcript import TranscriptRole
from app.interview_vnext.llm.context import ReferenceSnapshot

from .contracts import (
    CaseSplit,
    DifficultyTag,
    ExpectedCommit,
    GoldRequirement,
    QualifierExact,
    TurnEvalCase,
    TurnEvalGold,
    TurnEvalInitialFixture,
    TurnEvalReferenceOutput,
    TurnEvalSuiteManifest,
    TurnEvalTranscriptTurn,
    define_turn_eval_suite_manifest,
)


EXPECTED_CASE_FILES = frozenset(
    {
        "case.json",
        "transcript.jsonl",
        "initial_state.json",
        "reference_snapshot.json",
        "gold.json",
        "reference_output.json",
        "adjudication.md",
    }
)
# 只有這三份進 runtime hash;gold/reference_output/adjudication 屬 evaluation 面。
RUNTIME_FILE_KEYS = ("transcript", "initial_state", "reference_snapshot")

SPLIT_DIRS = {CaseSplit.DEVELOPMENT: "development", CaseSplit.CHALLENGE: "challenge"}
DEVELOPMENT_CASE_COUNT = 8
CHALLENGE_CASE_COUNT = 4


class CaseLoadError(ValueError):
    """Any integrity violation while loading case/suite artifacts."""

    def __init__(self, message: str, *, path: Path | None = None) -> None:
        suffix = f" ({path})" if path is not None else ""
        super().__init__(f"{message}{suffix}")


class TurnEvalCaseInputs(DomainModel):
    """Runtime-only case documents (§8.2). No gold-side field may ever be added."""

    case: TurnEvalCase
    transcript: tuple[TurnEvalTranscriptTurn, ...] = Field(min_length=1)
    initial_fixture: TurnEvalInitialFixture
    reference_snapshot: ReferenceSnapshot
    runtime_input_hash: Sha256


class TurnEvalCaseGold(DomainModel):
    """Evaluation-side documents; loaded only after a trial reaches its outcome."""

    case_id: str
    gold: TurnEvalGold
    reference_output: TurnEvalReferenceOutput
    adjudication_raw_sha256: Sha256
    runtime_input_hash: Sha256
    evaluation_contract_hash: Sha256
    case_content_hash: Sha256


class TurnEvalSuite(DomainModel):
    suite_version: StableName
    manifest: TurnEvalSuiteManifest
    runtime_inputs: tuple[TurnEvalCaseInputs, ...]
    evaluation_contracts: tuple[TurnEvalCaseGold, ...]


# ── byte-level reading(§6.2:UTF-8、LF、無 BOM;不改寫文字)──────────────


def _read_case_bytes(path: Path) -> bytes:
    if path.is_symlink():
        raise CaseLoadError("case files cannot be symlinks", path=path)
    if not path.is_file():
        raise CaseLoadError("case file is missing", path=path)
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise CaseLoadError("case files cannot start with a UTF-8 BOM", path=path)
    if b"\r" in data:
        raise CaseLoadError("case files must use LF line endings", path=path)
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CaseLoadError("case files must be valid UTF-8", path=path) from exc
    return data


def _read_json(path: Path) -> object:
    data = _read_case_bytes(path)
    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise CaseLoadError(f"invalid JSON: {exc}", path=path) from exc


# §8.2:load_case_inputs 在 gold.json 被暫時移走時仍要能跑;runtime 面只強制
# 這四份,evaluation 三份由 load_case_gold/load_suite 強制。未知檔一律拒絕。
RUNTIME_REQUIRED_FILES = frozenset(
    {"case.json", "transcript.jsonl", "initial_state.json", "reference_snapshot.json"}
)


def _validate_case_dir(case_dir: Path, *, required: frozenset[str]) -> None:
    if case_dir.is_symlink() or not case_dir.is_dir():
        raise CaseLoadError("case directory is missing or a symlink", path=case_dir)
    names = set()
    for entry in case_dir.iterdir():
        if entry.is_symlink():
            raise CaseLoadError("case directory cannot contain symlinks", path=entry)
        if entry.is_dir():
            raise CaseLoadError("case directory cannot contain subdirectories", path=entry)
        names.add(entry.name)
    unknown = names - EXPECTED_CASE_FILES
    if unknown:
        raise CaseLoadError(
            f"case directory contains unknown files: {sorted(unknown)}", path=case_dir
        )
    missing = required - names
    if missing:
        raise CaseLoadError(
            f"case directory is missing files: {sorted(missing)}", path=case_dir
        )


# ── occurrence resolution(與 production verifier 同語意:overlapping find)──


def quote_occurrences(text: str, quote: str) -> int:
    positions = 0
    start = 0
    while True:
        found = text.find(quote, start)
        if found < 0:
            return positions
        positions += 1
        start = found + 1


def _require_occurrence(
    *, text: str, quote: str, occurrence: int, what: str, path: Path
) -> None:
    found = quote_occurrences(text, quote)
    if occurrence > found:
        raise CaseLoadError(
            f"{what}: quote occurrence {occurrence} not found ({found} present)",
            path=path,
        )


# ── runtime inputs(§8.2 gold 隔離:此路徑絕不讀 gold/reference/adjudication)─


def load_case_inputs(case_dir: Path) -> TurnEvalCaseInputs:
    _validate_case_dir(case_dir, required=RUNTIME_REQUIRED_FILES)
    try:
        case = TurnEvalCase.model_validate(_read_json(case_dir / "case.json"))
    except ValidationError as exc:
        raise CaseLoadError(f"invalid case.json: {exc}", path=case_dir) from exc
    if case.case_id != case_dir.name:
        raise CaseLoadError(
            f"case_id {case.case_id!r} does not match directory name {case_dir.name!r}",
            path=case_dir,
        )

    transcript_path = case_dir / "transcript.jsonl"
    raw = _read_case_bytes(transcript_path).decode("utf-8")
    lines = raw.split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    if not lines:
        raise CaseLoadError("transcript cannot be empty", path=transcript_path)
    turns: list[TurnEvalTranscriptTurn] = []
    for index, line in enumerate(lines, 1):
        if not line.strip():
            raise CaseLoadError(
                f"transcript line {index} is blank", path=transcript_path
            )
        try:
            turns.append(TurnEvalTranscriptTurn.model_validate(json.loads(line)))
        except (json.JSONDecodeError, ValidationError) as exc:
            raise CaseLoadError(
                f"transcript line {index} is invalid: {exc}", path=transcript_path
            ) from exc

    sequences = tuple(turn.sequence for turn in turns)
    if sequences != tuple(range(1, len(turns) + 1)):
        raise CaseLoadError(
            "transcript sequences must be contiguous from 1", path=transcript_path
        )
    keys = tuple(turn.turn_key for turn in turns)
    if len(keys) != len(set(keys)):
        raise CaseLoadError("transcript turn keys must be unique", path=transcript_path)
    if turns[0].role != TranscriptRole.CONSULTANT:
        raise CaseLoadError(
            "transcript must start with a consultant turn", path=transcript_path
        )
    for previous, current in zip(turns, turns[1:], strict=False):
        if previous.role == current.role:
            raise CaseLoadError(
                "transcript roles must alternate", path=transcript_path
            )
        if current.occurred_offset_seconds <= previous.occurred_offset_seconds:
            raise CaseLoadError(
                "transcript offsets must be strictly increasing", path=transcript_path
            )
    last = turns[-1]
    if last.role != TranscriptRole.EMPLOYEE or last.turn_key != case.target_turn_key:
        raise CaseLoadError(
            "transcript must end with the target employee turn", path=transcript_path
        )

    fixture_path = case_dir / "initial_state.json"
    try:
        fixture = TurnEvalInitialFixture.model_validate(_read_json(fixture_path))
    except ValidationError as exc:
        raise CaseLoadError(f"invalid initial_state.json: {exc}", path=fixture_path) from exc
    turns_by_key = {turn.turn_key: turn for turn in turns}
    if fixture.open_episode is not None:
        opened = turns_by_key.get(fixture.open_episode.opened_turn_key)
        if opened is None or opened.sequence >= last.sequence:
            raise CaseLoadError(
                "open_episode.opened_turn_key must be an earlier transcript turn",
                path=fixture_path,
            )
    for item in fixture.prior_evidence:
        source = turns_by_key.get(item.source_turn_key)
        if source is None:
            raise CaseLoadError(
                f"prior evidence {item.evidence_key!r} references unknown turn "
                f"{item.source_turn_key!r}",
                path=fixture_path,
            )
        if source.role != TranscriptRole.EMPLOYEE or source.sequence >= last.sequence:
            raise CaseLoadError(
                f"prior evidence {item.evidence_key!r} must quote an earlier employee turn",
                path=fixture_path,
            )
        _require_occurrence(
            text=source.text,
            quote=item.quote,
            occurrence=item.quote_occurrence,
            what=f"prior evidence {item.evidence_key!r}",
            path=fixture_path,
        )
    source_groups = tuple(item.source_turn_key for item in fixture.prior_evidence)
    closed_groups: set[str] = set()
    previous_source = None
    for source_key in source_groups:
        if source_key != previous_source:
            if source_key in closed_groups:
                raise CaseLoadError(
                    "prior evidence source groups must be contiguous",
                    path=fixture_path,
                )
            if previous_source is not None:
                closed_groups.add(previous_source)
            previous_source = source_key
    seeded_turns = set(source_groups)
    prior_employee_turns = {
        turn.turn_key
        for turn in turns
        if turn.role == TranscriptRole.EMPLOYEE
        and turn.turn_key != case.target_turn_key
    }
    if seeded_turns != prior_employee_turns:
        raise CaseLoadError(
            "every non-target employee turn requires exactly one prior seed group",
            path=fixture_path,
        )

    snapshot_path = case_dir / "reference_snapshot.json"
    try:
        snapshot = ReferenceSnapshot.model_validate(_read_json(snapshot_path))
    except ValidationError as exc:
        raise CaseLoadError(
            f"invalid reference_snapshot.json: {exc}", path=snapshot_path
        ) from exc
    if case.task_type == "turn_interpret" and snapshot.snippets:
        # §6.4:第一批 turn cases 固定空 snippets,證明員工事實不來自 reference。
        raise CaseLoadError(
            "turn_interpret v1 cases require an empty reference snapshot",
            path=snapshot_path,
        )

    runtime_case = case.model_dump(mode="json")
    runtime_case["files"] = {
        key: value
        for key, value in runtime_case["files"].items()
        if key in RUNTIME_FILE_KEYS
    }
    runtime_input_hash = canonical_hash(
        {
            "case": runtime_case,
            "transcript": [turn.model_dump(mode="json") for turn in turns],
            "initial_fixture": fixture.model_dump(mode="json"),
            "reference_snapshot": snapshot.model_dump(mode="json"),
        }
    )
    return TurnEvalCaseInputs(
        case=case,
        transcript=tuple(turns),
        initial_fixture=fixture,
        reference_snapshot=snapshot,
        runtime_input_hash=runtime_input_hash,
    )


# ── evaluation contract(只在 trial 拿到 terminal outcome 後載入)────────────


def load_case_gold(case_dir: Path) -> TurnEvalCaseGold:
    _validate_case_dir(case_dir, required=EXPECTED_CASE_FILES)
    inputs = load_case_inputs(case_dir)
    case = inputs.case
    target = inputs.transcript[-1]
    prior_keys = {
        item.evidence_key for item in inputs.initial_fixture.prior_evidence
    }

    gold_path = case_dir / "gold.json"
    try:
        gold = TurnEvalGold.model_validate(_read_json(gold_path))
    except ValidationError as exc:
        raise CaseLoadError(f"invalid gold.json: {exc}", path=gold_path) from exc
    if gold.case_id != case.case_id:
        raise CaseLoadError("gold case_id does not match the case", path=gold_path)
    for observation in gold.observations:
        for anchor in observation.source_anchors:
            if anchor.turn_key != case.target_turn_key:
                raise CaseLoadError(
                    f"gold {observation.gold_id!r} anchors a non-target turn "
                    f"{anchor.turn_key!r}; the verifier only accepts target-turn quotes",
                    path=gold_path,
                )
            _require_occurrence(
                text=target.text,
                quote=anchor.quote,
                occurrence=anchor.occurrence,
                what=f"gold {observation.gold_id!r}",
                path=gold_path,
            )
        unknown_targets = set(observation.correction_target_evidence_keys) - prior_keys
        if unknown_targets:
            raise CaseLoadError(
                f"gold {observation.gold_id!r} references unknown prior evidence "
                f"{sorted(unknown_targets)}",
                path=gold_path,
            )
    expectation = gold.state_expectation
    for label, keyset in (
        ("prior_evidence_superseded_keys", expectation.prior_evidence_superseded_keys),
        ("forbidden_superseded_keys", expectation.forbidden_superseded_keys),
    ):
        unknown_keys = set(keyset) - prior_keys
        if unknown_keys:
            raise CaseLoadError(
                f"state expectation {label} references unknown prior evidence "
                f"{sorted(unknown_keys)}",
                path=gold_path,
            )

    reference_path = case_dir / "reference_output.json"
    try:
        reference = TurnEvalReferenceOutput.model_validate(_read_json(reference_path))
    except ValidationError as exc:
        raise CaseLoadError(
            f"invalid reference_output.json: {exc}", path=reference_path
        ) from exc
    if reference.case_id != case.case_id:
        raise CaseLoadError(
            "reference output case_id does not match the case", path=reference_path
        )
    for index, proposal in enumerate(reference.output.literal_observations, 1):
        _require_occurrence(
            text=target.text,
            quote=proposal.quote,
            occurrence=proposal.quote_occurrence,
            what=f"reference proposal p{index:04d}",
            path=reference_path,
        )
    for topic in reference.output.emergent_topics:
        _require_occurrence(
            text=target.text,
            quote=topic.quote,
            occurrence=topic.quote_occurrence,
            what="reference emergent topic",
            path=reference_path,
        )
    for proposal_index, targets in reference.correction_target_bindings.items():
        unknown_bindings = set(targets) - prior_keys
        if unknown_bindings:
            raise CaseLoadError(
                f"reference binding {proposal_index!r} references unknown prior evidence "
                f"{sorted(unknown_bindings)}",
                path=reference_path,
            )

    adjudication_bytes = _read_case_bytes(case_dir / "adjudication.md")
    if not adjudication_bytes.strip():
        raise CaseLoadError(
            "adjudication.md cannot be empty", path=case_dir / "adjudication.md"
        )
    adjudication_raw_sha256 = (
        "sha256:" + hashlib.sha256(adjudication_bytes).hexdigest()
    )

    evaluation_contract_hash = canonical_hash(
        {
            "gold": gold.model_dump(mode="json"),
            "reference_output": reference.model_dump(mode="json"),
            "adjudication_raw_sha256": adjudication_raw_sha256,
        }
    )
    case_content_hash = canonical_hash(
        {
            "case_id": case.case_id,
            "runtime_input_hash": inputs.runtime_input_hash,
            "evaluation_contract_hash": evaluation_contract_hash,
        }
    )
    return TurnEvalCaseGold(
        case_id=case.case_id,
        gold=gold,
        reference_output=reference,
        adjudication_raw_sha256=adjudication_raw_sha256,
        runtime_input_hash=inputs.runtime_input_hash,
        evaluation_contract_hash=evaluation_contract_hash,
        case_content_hash=case_content_hash,
    )


# ── suite balance(§7.1)─────────────────────────────────────────────────────


def _gold_has_denial(gold: TurnEvalGold) -> bool:
    for observation in gold.observations:
        polarity = observation.qualifiers.polarity
        if isinstance(polarity, QualifierExact) and polarity.value == Polarity.DENIED:
            return True
        if EvidenceKind.NEGATION in observation.allowed_kinds:
            return True
    return False


def assert_suite_balance(
    entries: Sequence[tuple[TurnEvalCaseInputs, TurnEvalCaseGold]],
) -> None:
    """§7.1 case balance assertions;違反任何一條整套 suite 拒載。"""

    by_split: dict[CaseSplit, int] = {CaseSplit.DEVELOPMENT: 0, CaseSplit.CHALLENGE: 0}
    tags: set[DifficultyTag] = set()
    target_hashes: dict[str, str] = {}
    has_action = has_denial = has_noop = False
    has_known_correction = has_unknown_correction = has_injection = False
    for inputs, evaluation in entries:
        by_split[inputs.case.split] += 1
        tags.update(inputs.case.difficulty_tags)
        target_text = inputs.transcript[-1].text
        target_hash = canonical_hash({"text": target_text})
        duplicate = target_hashes.get(target_hash)
        if duplicate is not None:
            raise CaseLoadError(
                f"cases {duplicate} and {inputs.case.case_id} share the same target text"
            )
        target_hashes[target_hash] = inputs.case.case_id
        gold = evaluation.gold
        for observation in gold.observations:
            if (
                observation.requirement == GoldRequirement.REQUIRED
                and EvidenceKind.ACTION in observation.allowed_kinds
            ):
                has_action = True
            if observation.correction_target_evidence_keys:
                has_known_correction = True
        if _gold_has_denial(gold):
            has_denial = True
        if gold.expected_commit == ExpectedCommit.RECEIPT_ONLY:
            has_noop = True
        if (
            TurnInsufficiencyCode.CORRECTION_TARGET_UNKNOWN
            in gold.required_insufficiencies
        ):
            has_unknown_correction = True
        # injection 以 failure_purpose 判,adversarial tag 只涵蓋難度面;
        # 兩者分開,才能分別報「缺 adversarial」與「缺 injection case」。
        if "injection" in inputs.case.failure_purpose:
            has_injection = True
    if by_split[CaseSplit.DEVELOPMENT] != DEVELOPMENT_CASE_COUNT:
        raise CaseLoadError(
            f"suite requires exactly {DEVELOPMENT_CASE_COUNT} development cases, "
            f"got {by_split[CaseSplit.DEVELOPMENT]}"
        )
    if by_split[CaseSplit.CHALLENGE] != CHALLENGE_CASE_COUNT:
        raise CaseLoadError(
            f"suite requires exactly {CHALLENGE_CASE_COUNT} challenge cases, "
            f"got {by_split[CaseSplit.CHALLENGE]}"
        )
    if tags != set(DifficultyTag):
        raise CaseLoadError(
            "suite must cover typical, edge and adversarial difficulty tags"
        )
    missing = [
        name
        for name, present in (
            ("positive action", has_action),
            ("denial", has_denial),
            ("no-op", has_noop),
            ("known correction", has_known_correction),
            ("unknown correction", has_unknown_correction),
            ("injection", has_injection),
        )
        if not present
    ]
    if missing:
        raise CaseLoadError(f"suite is missing required case purposes: {missing}")


def load_suite(cases_root: Path, *, suite_version: str) -> TurnEvalSuite:
    """Load every case under development/ and challenge/, enforce balance and
    build the frozen (split, case_id)-ordered suite manifest (§7.1/§8.1)."""

    if cases_root.is_symlink() or not cases_root.is_dir():
        raise CaseLoadError("cases root is missing or a symlink", path=cases_root)
    entries: list[tuple[TurnEvalCaseInputs, TurnEvalCaseGold]] = []
    for split, dirname in SPLIT_DIRS.items():
        split_dir = cases_root / dirname
        if not split_dir.is_dir():
            raise CaseLoadError(f"missing split directory {dirname!r}", path=cases_root)
        for case_dir in sorted(split_dir.iterdir(), key=lambda item: item.name):
            inputs = load_case_inputs(case_dir)
            if inputs.case.split != split:
                raise CaseLoadError(
                    f"case {inputs.case.case_id} declares split "
                    f"{inputs.case.split.value!r} but lives under {dirname!r}",
                    path=case_dir,
                )
            entries.append((inputs, load_case_gold(case_dir)))
    assert_suite_balance(entries)
    ordered = sorted(
        entries, key=lambda pair: (pair[0].case.split.value, pair[0].case.case_id)
    )
    manifest = define_turn_eval_suite_manifest(
        suite_version=suite_version,
        cases=[
            {
                "case_id": inputs.case.case_id,
                "split": inputs.case.split,
                "runtime_input_hash": inputs.runtime_input_hash,
                "evaluation_contract_hash": evaluation.evaluation_contract_hash,
                "case_content_hash": evaluation.case_content_hash,
            }
            for inputs, evaluation in ordered
        ],
    )
    return TurnEvalSuite(
        suite_version=suite_version,
        manifest=manifest,
        runtime_inputs=tuple(inputs for inputs, _ in ordered),
        evaluation_contracts=tuple(evaluation for _, evaluation in ordered),
    )


def runtime_inputs_contain(inputs: TurnEvalCaseInputs, needle: str) -> bool:
    """Sentinel probe used by gold-isolation tests (§8.2)."""

    return needle in canonical_json(inputs.model_dump(mode="json"))
