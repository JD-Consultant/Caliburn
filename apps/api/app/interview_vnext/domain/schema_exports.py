"""Portable JSON Schema registry for vNext domain seams."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter

from .commands import ApplyEvidenceCommand, AppendTranscriptTurnCommand, TransitionSessionCommand
from .episode import EpisodeState, Gap
from .events import DomainEvent
from .evidence import Evidence, Inference
from .job_model import CandidateJobItem
from .review import ReviewDecision
from .session import InterviewSession
from .state import InterviewState
from .transcript import TranscriptTurn


SchemaFactory = Callable[[], dict[str, Any]]


def _model_schema(model) -> SchemaFactory:
    return model.model_json_schema


SCHEMA_EXPORTS: dict[str, tuple[str, str, SchemaFactory]] = {
    "interview-session.v1.schema.json": (
        "https://caliburn.local/schemas/interview-session.v1.schema.json",
        "Caliburn interview vNext session v1",
        _model_schema(InterviewSession),
    ),
    "transcript-turn.v1.schema.json": (
        "https://caliburn.local/schemas/transcript-turn.v1.schema.json",
        "Caliburn interview vNext transcript turn v1",
        _model_schema(TranscriptTurn),
    ),
    "evidence.v1.schema.json": (
        "https://caliburn.local/schemas/evidence.v1.schema.json",
        "Caliburn interview vNext evidence v1",
        _model_schema(Evidence),
    ),
    "inference.v1.schema.json": (
        "https://caliburn.local/schemas/inference.v1.schema.json",
        "Caliburn interview vNext inference v1",
        _model_schema(Inference),
    ),
    "episode-state.v1.schema.json": (
        "https://caliburn.local/schemas/episode-state.v1.schema.json",
        "Caliburn interview vNext episode state v1",
        _model_schema(EpisodeState),
    ),
    "gap.v1.schema.json": (
        "https://caliburn.local/schemas/gap.v1.schema.json",
        "Caliburn interview vNext gap v1",
        _model_schema(Gap),
    ),
    "candidate-job-item.v1.schema.json": (
        "https://caliburn.local/schemas/candidate-job-item.v1.schema.json",
        "Caliburn interview vNext candidate job item v1",
        _model_schema(CandidateJobItem),
    ),
    "review-decision.v1.schema.json": (
        "https://caliburn.local/schemas/review-decision.v1.schema.json",
        "Caliburn interview vNext review decision v1",
        _model_schema(ReviewDecision),
    ),
    "interview-state.v1.schema.json": (
        "https://caliburn.local/schemas/interview-state.v1.schema.json",
        "Caliburn interview vNext materialized state v1",
        _model_schema(InterviewState),
    ),
    "domain-event.v1.schema.json": (
        "https://caliburn.local/schemas/domain-event.v1.schema.json",
        "Caliburn interview vNext domain event v1",
        TypeAdapter(DomainEvent).json_schema,
    ),
    "transition-session-command.v1.schema.json": (
        "https://caliburn.local/schemas/transition-session-command.v1.schema.json",
        "Caliburn interview vNext transition session command v1",
        _model_schema(TransitionSessionCommand),
    ),
    "append-transcript-turn-command.v1.schema.json": (
        "https://caliburn.local/schemas/append-transcript-turn-command.v1.schema.json",
        "Caliburn interview vNext append transcript turn command v1",
        _model_schema(AppendTranscriptTurnCommand),
    ),
    "apply-evidence-command.v1.schema.json": (
        "https://caliburn.local/schemas/apply-evidence-command.v1.schema.json",
        "Caliburn interview vNext apply evidence command v1",
        _model_schema(ApplyEvidenceCommand),
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
