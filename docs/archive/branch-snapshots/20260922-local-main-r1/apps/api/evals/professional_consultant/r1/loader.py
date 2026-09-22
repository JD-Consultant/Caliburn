"""Strict R1 fixture loader with a blind runtime/evaluation split."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from app.professional_consultant.contracts import (
    EmployeeMessage,
    TaskDiscoveryInput,
    TranscriptRole,
    TranscriptTurn,
)

from .contracts import (
    JobAnalysisQualityRubric,
    R1CaseDocument,
    R1CaseExpectations,
    R1CaseMetadata,
    R1EvaluationCase,
    R1RuntimeCase,
)


class R1CaseLoadError(ValueError):
    pass


_Model = TypeVar("_Model", bound=BaseModel)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise R1CaseLoadError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read_utf8_lf(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise R1CaseLoadError(f"{path.name} must not contain a UTF-8 BOM")
    if b"\r" in data:
        raise R1CaseLoadError(f"{path.name} must use LF line endings")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise R1CaseLoadError(f"{path.name} must be UTF-8") from exc


def _parse_json_model(path: Path, model: type[_Model]) -> _Model:
    text = _read_utf8_lf(path)
    try:
        payload = json.loads(text, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, R1CaseLoadError) as exc:
        raise R1CaseLoadError(f"invalid {path.name}: {exc}") from exc
    encoded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    return model.model_validate_json(encoded)


def _load_transcript(path: Path) -> tuple[TranscriptTurn, ...]:
    text = _read_utf8_lf(path)
    turns: list[TranscriptTurn] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            raise R1CaseLoadError(f"{path.name} line {number} is blank")
        try:
            payload = json.loads(line, object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, R1CaseLoadError) as exc:
            raise R1CaseLoadError(
                f"invalid {path.name} line {number}: {exc}"
            ) from exc
        turns.append(
            TranscriptTurn.model_validate_json(
                json.dumps(payload, ensure_ascii=False, allow_nan=False)
            )
        )
    if not turns:
        raise R1CaseLoadError("transcript must not be empty")
    ids = [turn.turn_id for turn in turns]
    if len(set(ids)) != len(ids):
        raise R1CaseLoadError("transcript turn IDs must be unique")
    return tuple(turns)


def _metadata(document: R1CaseDocument) -> R1CaseMetadata:
    return R1CaseMetadata(
        case_id=document.case_id,
        case_family_id=document.case_family_id,
        source_type=document.source_type,
        source_session_ref=document.source_session_ref,
        title=document.title,
        capability=document.capability,
    )


def _case_document(case_dir: Path) -> R1CaseDocument:
    document = _parse_json_model(case_dir / "case.json", R1CaseDocument)
    if document.case_id != case_dir.name:
        raise R1CaseLoadError("case_id must match its directory name")
    return document


def load_runtime_case(case_dir: Path) -> R1RuntimeCase:
    document = _case_document(case_dir)
    transcript = _load_transcript(case_dir / document.files.transcript)
    targets = [turn for turn in transcript if turn.turn_id == document.target_message_id]
    if len(targets) != 1 or targets[0].role is not TranscriptRole.EMPLOYEE:
        raise R1CaseLoadError("target_message_id must identify one employee turn")
    target = targets[0]
    target_index = transcript.index(target)
    if target_index != len(transcript) - 1:
        raise R1CaseLoadError("target employee message must be the final turn")
    recent = transcript[:target_index]
    metadata = _metadata(document)
    runtime_input = TaskDiscoveryInput(
        schema_version="task_discovery_input.v1",
        employee_message=EmployeeMessage(message_id=target.turn_id, text=target.text),
        question_context=document.question_context,
        recent_transcript=recent,
        prior_claims=document.prior_claims,
        prior_stories=document.prior_stories,
        prior_work_units=document.prior_work_units,
        existing_task_candidates=document.existing_task_candidates,
        recent_questions=tuple(
            turn.text for turn in recent if turn.role is TranscriptRole.CONSULTANT
        ),
        omitted_relevant_context=document.omitted_relevant_context,
    )
    return R1RuntimeCase(metadata=metadata, runtime_input=runtime_input)


def load_runtime_suite(cases_root: Path) -> tuple[R1RuntimeCase, ...]:
    case_dirs = sorted(path for path in cases_root.iterdir() if path.is_dir())
    return tuple(load_runtime_case(path) for path in case_dirs)


def load_evaluation_case(case_dir: Path) -> R1EvaluationCase:
    document = _case_document(case_dir)
    expectations = _parse_json_model(
        case_dir / document.files.expectations, R1CaseExpectations
    )
    if expectations.case_id != document.case_id:
        raise R1CaseLoadError("expectations case_id must match case metadata")
    adjudication = _read_utf8_lf(case_dir / document.files.adjudication)
    if not adjudication.startswith("# "):
        raise R1CaseLoadError("adjudication must start with a Markdown heading")
    return R1EvaluationCase(
        metadata=_metadata(document),
        expectations=expectations,
        adjudication_markdown=adjudication,
    )


def load_evaluation_suite(cases_root: Path) -> tuple[R1EvaluationCase, ...]:
    case_dirs = sorted(path for path in cases_root.iterdir() if path.is_dir())
    return tuple(load_evaluation_case(path) for path in case_dirs)


def load_job_analysis_rubric(rubric_root: Path) -> JobAnalysisQualityRubric:
    return _parse_json_model(
        rubric_root / "job-analysis-quality-rubric.v1.json",
        JobAnalysisQualityRubric,
    )
