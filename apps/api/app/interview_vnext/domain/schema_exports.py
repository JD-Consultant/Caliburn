"""Portable JSON Schema registry for vNext domain seams."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from pydantic import TypeAdapter

from .commands import (
    ApplyCandidateProposalsCommand,
    ApplyEvidenceCommand,
    ApplyGapProposalsCommand,
    ApplyInferenceProposalsCommand,
    ApplyReviewDecisionCommand,
    AppendTranscriptTurnCommand,
    DecideInferenceCommand,
    OpenEpisodeCommand,
    SupersedeInferenceCommand,
    TransitionCandidateCommand,
    TransitionEpisodeCommand,
    TransitionGapCommand,
    TransitionSessionCommand,
    WithdrawEvidenceCommand,
)
from .episode import EpisodeState, Gap
from .events import DomainEvent
from .evidence import Evidence, Inference
from .job_model import CandidateJobItem
from .reducers import ReductionResult
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
    "evidence.v2.schema.json": (
        "https://caliburn.local/schemas/evidence.v2.schema.json",
        "Caliburn interview vNext evidence v2",
        _model_schema(Evidence),
    ),
    "inference.v2.schema.json": (
        "https://caliburn.local/schemas/inference.v2.schema.json",
        "Caliburn interview vNext inference v2",
        _model_schema(Inference),
    ),
    "episode-state.v1.schema.json": (
        "https://caliburn.local/schemas/episode-state.v1.schema.json",
        "Caliburn interview vNext episode state v1",
        _model_schema(EpisodeState),
    ),
    "gap.v2.schema.json": (
        "https://caliburn.local/schemas/gap.v2.schema.json",
        "Caliburn interview vNext gap v2",
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
    "interview-state.v2.schema.json": (
        "https://caliburn.local/schemas/interview-state.v2.schema.json",
        "Caliburn interview vNext materialized state v2",
        _model_schema(InterviewState),
    ),
    "domain-event.v1.schema.json": (
        "https://caliburn.local/schemas/domain-event.v1.schema.json",
        "Caliburn interview vNext domain event v1",
        TypeAdapter(DomainEvent).json_schema,
    ),
    "reduction-result.v1.schema.json": (
        "https://caliburn.local/schemas/reduction-result.v1.schema.json",
        "Caliburn interview vNext reduction result v1",
        _model_schema(ReductionResult),
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
    "apply-evidence-command.v2.schema.json": (
        "https://caliburn.local/schemas/apply-evidence-command.v2.schema.json",
        "Caliburn interview vNext apply evidence command v2",
        _model_schema(ApplyEvidenceCommand),
    ),
    "withdraw-evidence-command.v1.schema.json": (
        "https://caliburn.local/schemas/withdraw-evidence-command.v1.schema.json",
        "Caliburn interview vNext withdraw evidence command v1",
        _model_schema(WithdrawEvidenceCommand),
    ),
    "open-episode-command.v1.schema.json": (
        "https://caliburn.local/schemas/open-episode-command.v1.schema.json",
        "Caliburn interview vNext open episode command v1",
        _model_schema(OpenEpisodeCommand),
    ),
    "transition-episode-command.v1.schema.json": (
        "https://caliburn.local/schemas/transition-episode-command.v1.schema.json",
        "Caliburn interview vNext transition episode command v1",
        _model_schema(TransitionEpisodeCommand),
    ),
    "apply-gap-proposals-command.v1.schema.json": (
        "https://caliburn.local/schemas/apply-gap-proposals-command.v1.schema.json",
        "Caliburn interview vNext apply gap proposals command v1",
        _model_schema(ApplyGapProposalsCommand),
    ),
    "transition-gap-command.v1.schema.json": (
        "https://caliburn.local/schemas/transition-gap-command.v1.schema.json",
        "Caliburn interview vNext transition gap command v1",
        _model_schema(TransitionGapCommand),
    ),
    "apply-inference-proposals-command.v1.schema.json": (
        "https://caliburn.local/schemas/apply-inference-proposals-command.v1.schema.json",
        "Caliburn interview vNext apply inference proposals command v1",
        _model_schema(ApplyInferenceProposalsCommand),
    ),
    "decide-inference-command.v1.schema.json": (
        "https://caliburn.local/schemas/decide-inference-command.v1.schema.json",
        "Caliburn interview vNext decide inference command v1",
        _model_schema(DecideInferenceCommand),
    ),
    "supersede-inference-command.v1.schema.json": (
        "https://caliburn.local/schemas/supersede-inference-command.v1.schema.json",
        "Caliburn interview vNext supersede inference command v1",
        _model_schema(SupersedeInferenceCommand),
    ),
    "apply-candidate-proposals-command.v1.schema.json": (
        "https://caliburn.local/schemas/apply-candidate-proposals-command.v1.schema.json",
        "Caliburn interview vNext apply candidate proposals command v1",
        _model_schema(ApplyCandidateProposalsCommand),
    ),
    "transition-candidate-command.v1.schema.json": (
        "https://caliburn.local/schemas/transition-candidate-command.v1.schema.json",
        "Caliburn interview vNext transition candidate command v1",
        _model_schema(TransitionCandidateCommand),
    ),
    "apply-review-decision-command.v1.schema.json": (
        "https://caliburn.local/schemas/apply-review-decision-command.v1.schema.json",
        "Caliburn interview vNext apply review decision command v1",
        _model_schema(ApplyReviewDecisionCommand),
    ),
}


def published_schema(filename: str) -> dict[str, Any]:
    schema_id, title, factory = SCHEMA_EXPORTS[filename]
    schema = factory()
    schema["$id"] = schema_id
    schema["title"] = title
    return schema
