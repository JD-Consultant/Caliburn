"""Materialized immutable state validated at the aggregate boundary."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from .base import DomainModel
from .episode import EpisodeState, EpisodeStatus, Gap
from .evidence import Evidence, EvidenceStatus, Inference
from .job_model import CandidateJobItem, CandidateStatus
from .review import ReviewAction, ReviewDecision
from .session import InterviewSession
from .transcript import TranscriptTurn


def _assert_unique(values: tuple[UUID, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} IDs must be unique")


class InterviewState(DomainModel):
    schema_version: Literal["interview_state.v1"] = "interview_state.v1"
    session: InterviewSession
    turns: tuple[TranscriptTurn, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    inferences: tuple[Inference, ...] = ()
    episodes: tuple[EpisodeState, ...] = ()
    gaps: tuple[Gap, ...] = ()
    candidates: tuple[CandidateJobItem, ...] = ()
    reviews: tuple[ReviewDecision, ...] = ()
    processed_command_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def aggregate_links_are_closed(self) -> "InterviewState":
        session_id = self.session.session_id
        collections = (
            (tuple(turn.turn_id for turn in self.turns), "turn"),
            (tuple(item.evidence_id for item in self.evidence), "evidence"),
            (tuple(item.inference_id for item in self.inferences), "inference"),
            (tuple(item.episode_id for item in self.episodes), "episode"),
            (tuple(item.gap_id for item in self.gaps), "gap"),
            (tuple(item.candidate_id for item in self.candidates), "candidate"),
            (tuple(item.review_id for item in self.reviews), "review"),
            (self.processed_command_ids, "processed command"),
        )
        for values, label in collections:
            _assert_unique(values, label)

        if self.session.turn_count != len(self.turns):
            raise ValueError("session turn_count must equal materialized turns")

        turn_by_id = {turn.turn_id: turn for turn in self.turns}
        expected_sequences = list(range(1, len(self.turns) + 1))
        if [turn.sequence for turn in self.turns] != expected_sequences:
            raise ValueError("turn sequences must be contiguous and ordered")
        for index, turn in enumerate(self.turns):
            if turn.session_id != session_id:
                raise ValueError("turn belongs to another session")
            expected_previous = self.turns[index - 1].turn_id if index else None
            if turn.previous_turn_id != expected_previous:
                raise ValueError("turn previous_turn_id chain is invalid")

        episode_by_id = {item.episode_id: item for item in self.episodes}
        gap_by_id = {item.gap_id: item for item in self.gaps}
        evidence_by_id = {item.evidence_id: item for item in self.evidence}
        inference_by_id = {item.inference_id: item for item in self.inferences}
        candidate_by_id = {item.candidate_id: item for item in self.candidates}
        review_by_id = {item.review_id: item for item in self.reviews}

        if self.session.active_episode_id is not None:
            active = episode_by_id.get(self.session.active_episode_id)
            if active is None or active.status == EpisodeStatus.CLOSED:
                raise ValueError("active_episode_id must reference a non-closed episode")

        non_closed_episode_ids = {
            episode.episode_id
            for episode in self.episodes
            if episode.status != EpisodeStatus.CLOSED
        }
        expected_active = (
            {self.session.active_episode_id}
            if self.session.active_episode_id is not None
            else set()
        )
        if non_closed_episode_ids != expected_active:
            raise ValueError("session active_episode_id must match the only non-closed episode")

        for episode in self.episodes:
            if episode.session_id != session_id:
                raise ValueError("episode belongs to another session")
            if episode.opened_turn_id not in turn_by_id:
                raise ValueError("episode opened_turn_id does not exist")
            if episode.closed_turn_id is not None and episode.closed_turn_id not in turn_by_id:
                raise ValueError("episode closed_turn_id does not exist")
            if (
                episode.closed_turn_id is not None
                and turn_by_id[episode.closed_turn_id].sequence
                < turn_by_id[episode.opened_turn_id].sequence
            ):
                raise ValueError("episode cannot close before its opening turn")
            if not set(episode.evidence_ids) <= evidence_by_id.keys():
                raise ValueError("episode references missing evidence")
            if not set(episode.gap_ids) <= gap_by_id.keys():
                raise ValueError("episode references missing gaps")
            if any(
                evidence_by_id[evidence_id].episode_id != episode.episode_id
                for evidence_id in episode.evidence_ids
            ):
                raise ValueError("episode and evidence linkage must be bidirectional")
            if any(
                gap_by_id[gap_id].episode_id != episode.episode_id
                for gap_id in episode.gap_ids
            ):
                raise ValueError("episode and gap linkage must be bidirectional")

        for item in self.evidence:
            if item.session_id != session_id:
                raise ValueError("evidence belongs to another session")
            if item.turn_id not in turn_by_id:
                raise ValueError("evidence turn does not exist")
            if item.episode_id is not None and item.episode_id not in episode_by_id:
                raise ValueError("evidence episode does not exist")
            if (
                item.episode_id is not None
                and item.evidence_id not in episode_by_id[item.episode_id].evidence_ids
            ):
                raise ValueError("evidence and episode linkage must be bidirectional")
            if item.status == EvidenceStatus.SUPERSEDED:
                replacement = evidence_by_id.get(item.superseded_by)
                if replacement is None or item.evidence_id not in replacement.supersedes:
                    raise ValueError("superseded evidence lineage is not bidirectional")
            for target_id in item.supersedes:
                target = evidence_by_id.get(target_id)
                if target is None or target.superseded_by != item.evidence_id:
                    raise ValueError("replacement evidence lineage is not bidirectional")

        for item in self.evidence:
            lineage_path: set[UUID] = set()
            cursor: Evidence | None = item
            while cursor is not None:
                if cursor.evidence_id in lineage_path:
                    raise ValueError("evidence supersede lineage cannot contain a cycle")
                lineage_path.add(cursor.evidence_id)
                cursor = (
                    evidence_by_id.get(cursor.superseded_by)
                    if cursor.superseded_by is not None
                    else None
                )

        for item in self.inferences:
            if item.session_id != session_id:
                raise ValueError("inference belongs to another session")
            if not set(item.supporting_evidence_ids) <= evidence_by_id.keys():
                raise ValueError("inference references missing supporting evidence")
            if not set(item.contradicting_evidence_ids) <= evidence_by_id.keys():
                raise ValueError("inference references missing contradicting evidence")

        for gap in self.gaps:
            if gap.session_id != session_id:
                raise ValueError("gap belongs to another session")
            if gap.episode_id not in episode_by_id:
                raise ValueError("gap episode does not exist")
            if gap.gap_id not in episode_by_id[gap.episode_id].gap_ids:
                raise ValueError("gap and episode linkage must be bidirectional")
            if not set(gap.supporting_evidence_ids) <= evidence_by_id.keys():
                raise ValueError("gap references missing evidence")
            if not set(gap.asked_turn_ids) <= turn_by_id.keys():
                raise ValueError("gap references missing asked turns")

        for item in self.candidates:
            if item.session_id != session_id:
                raise ValueError("candidate belongs to another session")
            if not set(item.evidence_ids) <= evidence_by_id.keys():
                raise ValueError("candidate references missing evidence")
            if not set(item.inference_ids) <= inference_by_id.keys():
                raise ValueError("candidate references missing inference")
            if item.review_decision_id is not None:
                review = review_by_id.get(item.review_decision_id)
                if review is None or review.candidate_id != item.candidate_id:
                    raise ValueError("candidate review decision does not exist")

        for review in self.reviews:
            if review.session_id != session_id:
                raise ValueError("review belongs to another session")
            candidate = candidate_by_id.get(review.candidate_id)
            if candidate is None:
                raise ValueError("review candidate does not exist")
            if candidate.review_decision_id != review.review_id:
                raise ValueError("review and candidate linkage is not bidirectional")
            expected_status = (
                CandidateStatus.REJECTED
                if review.action == ReviewAction.REJECT
                else CandidateStatus.ACCEPTED
            )
            if candidate.status != expected_status:
                raise ValueError("review action and candidate status disagree")
            if (
                review.action == ReviewAction.EDIT
                and candidate.statement != review.edited_statement
            ):
                raise ValueError("edited review text must equal the accepted candidate statement")
        return self
