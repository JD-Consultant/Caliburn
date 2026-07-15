"""Pure, immutable domain contracts for interview vNext."""

from .commands import ApplyEvidenceCommand, AppendTranscriptTurnCommand, TransitionSessionCommand
from .evidence import Evidence, EvidenceQualifiers, Inference, QuoteSpan
from .episode import EpisodeState, Gap
from .job_model import CandidateJobItem
from .reducers import ReductionResult, apply_evidence, append_transcript_turn, transition_session
from .review import ReviewDecision
from .session import InterviewSession
from .state import InterviewState
from .transcript import TranscriptTurn

__all__ = [
    "ApplyEvidenceCommand",
    "AppendTranscriptTurnCommand",
    "CandidateJobItem",
    "EpisodeState",
    "Evidence",
    "EvidenceQualifiers",
    "Gap",
    "Inference",
    "InterviewSession",
    "InterviewState",
    "QuoteSpan",
    "ReductionResult",
    "ReviewDecision",
    "TranscriptTurn",
    "TransitionSessionCommand",
    "apply_evidence",
    "append_transcript_turn",
    "transition_session",
]
