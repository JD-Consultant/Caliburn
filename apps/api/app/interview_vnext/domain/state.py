"""Materialized immutable state validated at the aggregate boundary."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import model_validator

from .base import DomainModel
from .episode import EpisodeState, EpisodeStatus, Gap
from .evidence import Evidence, EvidenceStatus, Inference, InferenceStatus
from .interpretation import TurnInterpretationRecord
from .invariants import assert_candidate_projectable
from .job_model import CandidateJobItem, CandidateStatus
from .question_frame import QuestionFrame, QuestionFrameStatus
from .review import ReviewAction, ReviewDecision
from .session import InterviewSession
from .support import ContextualAnswerSupport, LiteralEmployeeSpanSupport, QuoteMatch
from .transcript import TranscriptRole, TranscriptTurn


def _assert_unique(values: tuple[UUID, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} IDs must be unique")


class InterviewState(DomainModel):
    schema_version: Literal["interview_state.v3"] = "interview_state.v3"
    session: InterviewSession
    turns: tuple[TranscriptTurn, ...] = ()
    evidence: tuple[Evidence, ...] = ()
    inferences: tuple[Inference, ...] = ()
    episodes: tuple[EpisodeState, ...] = ()
    gaps: tuple[Gap, ...] = ()
    candidates: tuple[CandidateJobItem, ...] = ()
    reviews: tuple[ReviewDecision, ...] = ()
    question_frames: tuple[QuestionFrame, ...] = ()
    active_question_frame_id: UUID | None = None
    turn_interpretations: tuple[TurnInterpretationRecord, ...] = ()
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
            (tuple(item.question_frame_id for item in self.question_frames), "question frame"),
            (
                tuple(item.interpretation_id for item in self.turn_interpretations),
                "interpretation",
            ),
            (
                tuple(item.operation_id for item in self.turn_interpretations),
                "interpretation operation",
            ),
            (
                tuple(item.employee_turn_id for item in self.turn_interpretations),
                "interpretation turn",
            ),
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
            if item.source_turn_id not in turn_by_id:
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
            if item.status == EvidenceStatus.WITHDRAWN:
                withdrawal_turn = turn_by_id.get(item.withdrawn_by_turn_id)
                if withdrawal_turn is None or withdrawal_turn.role != TranscriptRole.EMPLOYEE:
                    raise ValueError("withdrawn evidence requires an employee source turn")
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
            if item.decision_evidence_id is not None:
                decision_evidence = evidence_by_id.get(item.decision_evidence_id)
                if decision_evidence is None or decision_evidence.status != EvidenceStatus.ACTIVE:
                    raise ValueError("inference decision evidence must be active")
                decision_turn = turn_by_id[decision_evidence.source_turn_id]
                if decision_turn.role != TranscriptRole.EMPLOYEE:
                    raise ValueError("inference decision evidence must come from employee")
            if (
                item.status in {InferenceStatus.CANDIDATE, InferenceStatus.INSUFFICIENT}
                and item.decision_evidence_id is not None
            ):
                raise ValueError("model-owned inference cannot retain human decision evidence")
            if item.status == InferenceStatus.SUPERSEDED:
                replacement = inference_by_id.get(item.superseded_by)
                if replacement is None or item.inference_id not in replacement.supersedes:
                    raise ValueError("superseded inference lineage is not bidirectional")
            for target_id in item.supersedes:
                target = inference_by_id.get(target_id)
                if target is None or target.superseded_by != item.inference_id:
                    raise ValueError("replacement inference lineage is not bidirectional")

        for item in self.inferences:
            lineage_path: set[UUID] = set()
            cursor: Inference | None = item
            while cursor is not None:
                if cursor.inference_id in lineage_path:
                    raise ValueError("inference supersede lineage cannot contain a cycle")
                lineage_path.add(cursor.inference_id)
                cursor = (
                    inference_by_id.get(cursor.superseded_by)
                    if cursor.superseded_by is not None
                    else None
                )

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
            if any(
                turn_by_id[turn_id].role != TranscriptRole.CONSULTANT
                for turn_id in gap.asked_turn_ids
            ):
                raise ValueError("gap asked_turn_ids must reference consultant turns")
            if gap.resolution_turn_id is not None:
                resolution_turn = turn_by_id.get(gap.resolution_turn_id)
                if resolution_turn is None or resolution_turn.role != TranscriptRole.EMPLOYEE:
                    raise ValueError("gap resolution_turn_id must reference an employee turn")
            if not set(gap.resolution_evidence_ids) <= evidence_by_id.keys():
                raise ValueError("gap references missing resolution evidence")
            for evidence_id in gap.resolution_evidence_ids:
                resolution_evidence = evidence_by_id[evidence_id]
                if (
                    resolution_evidence.status != EvidenceStatus.ACTIVE
                    or resolution_evidence.source_turn_id != gap.resolution_turn_id
                ):
                    raise ValueError(
                        "gap resolution evidence must be active and match resolution turn"
                    )

        for item in self.candidates:
            if item.session_id != session_id:
                raise ValueError("candidate belongs to another session")
            if not set(item.evidence_ids) <= evidence_by_id.keys():
                raise ValueError("candidate references missing evidence")
            if not set(item.inference_ids) <= inference_by_id.keys():
                raise ValueError("candidate references missing inference")
            for threshold in item.thresholds:
                if threshold.evidence_id is not None:
                    threshold_evidence = evidence_by_id.get(threshold.evidence_id)
                    if (
                        threshold_evidence is None
                        or threshold.evidence_id not in item.evidence_ids
                    ):
                        raise ValueError("candidate threshold evidence must close over lineage")
            if item.review_decision_id is not None:
                review = review_by_id.get(item.review_decision_id)
                if review is None or review.candidate_id != item.candidate_id:
                    raise ValueError("candidate review decision does not exist")
            if item.status in {CandidateStatus.VERIFIED, CandidateStatus.PROJECTED}:
                assert_candidate_projectable(item, evidence_by_id)

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

        frame_by_id = {frame.question_frame_id: frame for frame in self.question_frames}
        receipt_by_operation = {item.operation_id: item for item in self.turn_interpretations}
        interpreted_turn_ids = {item.employee_turn_id for item in self.turn_interpretations}

        for frame in self.question_frames:
            if frame.session_id != session_id:
                raise ValueError("question frame belongs to another session")
            consultant_turn = turn_by_id.get(frame.consultant_turn_id)
            if consultant_turn is None or consultant_turn.role != TranscriptRole.CONSULTANT:
                raise ValueError("question frame requires a consultant source turn")
            if frame.answer_turn_id is not None:
                answer_turn = turn_by_id.get(frame.answer_turn_id)
                if answer_turn is None or answer_turn.role != TranscriptRole.EMPLOYEE:
                    raise ValueError("question frame answer must be an employee turn")
                if answer_turn.sequence != consultant_turn.sequence + 1:
                    raise ValueError("question frame answer must immediately follow its question")
            if (
                frame.superseded_by_frame_id is not None
                and frame.superseded_by_frame_id not in frame_by_id
            ):
                raise ValueError("superseding question frame does not exist")
            if frame.consumed_operation_id is not None:
                receipt = receipt_by_operation.get(frame.consumed_operation_id)
                if receipt is None or receipt.question_frame_id != frame.question_frame_id:
                    raise ValueError("consumed frame requires its interpretation receipt")

        active_frame_ids = tuple(
            frame.question_frame_id
            for frame in self.question_frames
            if frame.status == QuestionFrameStatus.ACTIVE
        )
        expected_active_frame_ids = (
            (self.active_question_frame_id,) if self.active_question_frame_id is not None else ()
        )
        if active_frame_ids != expected_active_frame_ids:
            raise ValueError("active_question_frame_id must match the only active question frame")

        for receipt in self.turn_interpretations:
            if receipt.session_id != session_id:
                raise ValueError("interpretation receipt belongs to another session")
            employee_turn = turn_by_id.get(receipt.employee_turn_id)
            if employee_turn is None or employee_turn.role != TranscriptRole.EMPLOYEE:
                raise ValueError("interpretation receipt requires an employee turn")
            if receipt.question_frame_id is not None:
                receipt_frame = frame_by_id.get(receipt.question_frame_id)
                if receipt_frame is None:
                    raise ValueError("interpretation receipt frame does not exist")
                if (
                    receipt_frame.definition.definition_hash
                    != receipt.question_frame_definition_hash
                ):
                    raise ValueError("interpretation receipt frame definition hash mismatch")
            produced_evidence_ids = tuple(
                item.evidence_id
                for item in self.evidence
                if item.extractor_operation_id == receipt.operation_id
            )
            if receipt.accepted_evidence_ids != produced_evidence_ids:
                raise ValueError(
                    "accepted_evidence_ids must equal the evidence its operation produced, in order"
                )

        # At most one employee turn may await interpretation, and it must be the
        # transcript tail: the next consultant question cannot open until the
        # previous answer is interpreted (plan §7.2, §7.5).
        pending_employee_turns = tuple(
            turn
            for turn in self.turns
            if turn.role == TranscriptRole.EMPLOYEE and turn.turn_id not in interpreted_turn_ids
        )
        if len(pending_employee_turns) > 1:
            raise ValueError("at most one employee turn may await interpretation")
        if pending_employee_turns and pending_employee_turns[0].turn_id != self.turns[-1].turn_id:
            raise ValueError("an uninterpreted employee turn must be the transcript tail")

        if self.active_question_frame_id is not None:
            active_frame = frame_by_id[self.active_question_frame_id]
            if active_frame.answer_turn_id is not None:
                if not pending_employee_turns:
                    raise ValueError("answer-bound active frame requires a pending employee turn")
                if active_frame.answer_turn_id != pending_employee_turns[0].turn_id:
                    raise ValueError("answer-bound active frame must bind the pending employee tail")

        for item in self.evidence:
            source_turn = turn_by_id[item.source_turn_id]
            if source_turn.role != TranscriptRole.EMPLOYEE:
                raise ValueError("evidence must be supported by an employee turn")
            support = item.support
            if isinstance(support, LiteralEmployeeSpanSupport):
                if support.quote_match == QuoteMatch.EXACT:
                    quoted = source_turn.text[support.span.start : support.span.end]
                    if quoted != support.quote:
                        raise ValueError("literal support must quote its employee turn exactly")
            elif isinstance(support, ContextualAnswerSupport):
                receipt = receipt_by_operation.get(item.extractor_operation_id)
                if receipt is None:
                    raise ValueError("contextual evidence requires its interpretation receipt")
                if receipt.question_frame_id != support.question_frame_id:
                    raise ValueError("contextual evidence frame must match its receipt frame")
                if receipt.employee_turn_id != support.employee_turn_id:
                    raise ValueError("contextual evidence turn must match its receipt turn")
                if (
                    receipt.question_frame_definition_hash
                    != support.question_frame_definition_hash
                ):
                    raise ValueError("contextual evidence frame definition hash mismatch")
        return self
