"""Blind review queue export/import and adjudication validation (§14).

A review item is ONE candidate edge (gold + output observation) or one output
observation with no candidate edge; the reviewer labels each with a single
``ReviewDecisionLabel`` (§13.2). Items only show what semantic judgement needs:
the employee turn, prior evidence, the one candidate observation, and (for an
edge) the one gold rubric — never provider/model/endpoint, slot/attempt,
latency/cost/token, split, or which side "should" win. The queue is reordered
by a batch seed and each item exposes only an opaque ``review_item_id``.
Import checks the item hash, forbids provider identity in the reason, and makes
a changed decision open a new revision instead of overwriting in place.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Sequence
from uuid import UUID, uuid5

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText, Sha256
from app.interview_vnext.domain.turn_identity import derive_proposal_ref
from app.interview_vnext.llm.turn_interpret import (
    ObservationProposal,
    TurnInterpretOutput,
)

from .contracts import (
    ReviewDecisionLabel,
    TurnEvalGold,
    TurnEvalGoldObservation,
    TurnEvalReviewDecision,
)
from .loader import TurnEvalCaseInputs
from .turn_graders import CandidateEdge


UNMATCHED_GOLD_ID = "__unmatched__"

# reason 內禁止出現的 provider identity 片段(§14.3)
_FORBIDDEN_REASON_MARKERS = (
    "openrouter",
    "anthropic",
    "claude",
    "openai",
    " gpt",
    "sonnet",
    "opus",
    "haiku",
    "gemini",
    "provider",
    "endpoint",
)


class ReviewCandidateView(DomainModel):
    """One output observation as the reviewer sees it (no provider identity)."""

    proposal_key: str
    subject: NonEmptyText
    kind: NonEmptyText
    claim: NonEmptyText
    quote: NonEmptyText
    quote_occurrence: int
    time_scope: NonEmptyText
    typicality: NonEmptyText
    polarity: NonEmptyText
    frequency_unit: NonEmptyText
    frequency_value: str | None
    frequency_verbatim: str | None
    importance: NonEmptyText
    ownership: NonEmptyText
    verifier_accepted: bool
    verifier_reason_codes: tuple[NonEmptyText, ...]


class ReviewGoldView(DomainModel):
    """Gold rubric visible to the reviewer (legal anchors, no expected winner)."""

    gold_id: str
    requirement: NonEmptyText
    semantic_target: NonEmptyText
    allowed_subjects: tuple[NonEmptyText, ...]
    allowed_kinds: tuple[NonEmptyText, ...]
    legal_quotes: tuple[NonEmptyText, ...]


class ReviewItem(DomainModel):
    schema_version: NonEmptyText = "turn_eval_review_item.v1"
    review_item_id: UUID
    review_item_hash: Sha256
    case_id: str  # 保留供 report 對齊;queue 排序不用它,不洩漏原順序
    gold_id: str  # UNMATCHED_GOLD_ID 表示 output 無候選 gold
    preceding_consultant_text: str | None
    current_employee_text: NonEmptyText
    prior_evidence_summaries: tuple[NonEmptyText, ...]
    candidate_observation: ReviewCandidateView
    gold_rubric: ReviewGoldView | None
    edge_qualifiers_pass: bool | None


def _candidate_view(
    proposal: ObservationProposal,
    *,
    proposal_key: str,
    accepted: bool,
    reason_codes: tuple[str, ...],
) -> ReviewCandidateView:
    q = proposal.qualifiers
    return ReviewCandidateView(
        proposal_key=proposal_key,
        subject=proposal.subject.value,
        kind=proposal.kind.value,
        claim=proposal.claim,
        quote=proposal.quote,
        quote_occurrence=proposal.quote_occurrence,
        time_scope=q.time_scope.value,
        typicality=q.typicality.value,
        polarity=q.polarity.value,
        frequency_unit=q.frequency.unit.value,
        frequency_value=q.frequency.value,
        frequency_verbatim=q.frequency.verbatim,
        importance=q.importance.value,
        ownership=q.ownership.value,
        verifier_accepted=accepted,
        verifier_reason_codes=reason_codes,
    )


def _gold_view(item: TurnEvalGoldObservation) -> ReviewGoldView:
    return ReviewGoldView(
        gold_id=item.gold_id,
        requirement=item.requirement.value,
        semantic_target=item.semantic_target,
        allowed_subjects=tuple(s.value for s in item.allowed_subjects),
        allowed_kinds=tuple(k.value for k in item.allowed_kinds),
        legal_quotes=tuple(a.quote for a in item.source_anchors),
    )


def build_review_items(
    *,
    batch_id: UUID,
    trial_id: UUID,
    inputs: TurnEvalCaseInputs,
    gold: TurnEvalGold,
    output: TurnInterpretOutput,
    accepted_proposal_keys: frozenset[str],
    verifier_reason_codes: dict[str, tuple[str, ...]],
    edges: Sequence[CandidateEdge],
    unmatched_proposal_keys: Sequence[str],
) -> tuple[ReviewItem, ...]:
    """One item per candidate edge plus one per output observation with no edge."""

    transcript = inputs.transcript
    preceding = transcript[-2].text if len(transcript) >= 2 else None
    prior_summaries = tuple(
        f"{item.subject.value}/{item.kind.value}: {item.claim}"
        for item in inputs.initial_fixture.prior_evidence
    )
    gold_by_id = {item.gold_id: item for item in gold.observations}
    proposal_by_key = {
        derive_proposal_ref(index): proposal
        for index, proposal in enumerate(output.literal_observations, 1)
    }

    items: list[ReviewItem] = []

    def make_item(gold_id: str, proposal_key: str, qualifiers_pass: bool | None):
        proposal = proposal_by_key[proposal_key]
        candidate = _candidate_view(
            proposal,
            proposal_key=proposal_key,
            accepted=proposal_key in accepted_proposal_keys,
            reason_codes=verifier_reason_codes.get(proposal_key, ()),
        )
        rubric = _gold_view(gold_by_id[gold_id]) if gold_id != UNMATCHED_GOLD_ID else None
        review_item_id = uuid5(
            batch_id,
            f"review/{trial_id}/{inputs.case.case_id}/{gold_id}/{proposal_key}",
        )
        body = {
            "case_id": inputs.case.case_id,
            "gold_id": gold_id,
            "preceding_consultant_text": preceding,
            "current_employee_text": transcript[-1].text,
            "prior_evidence_summaries": list(prior_summaries),
            "candidate_observation": candidate.model_dump(mode="json"),
            "gold_rubric": rubric.model_dump(mode="json") if rubric else None,
            "edge_qualifiers_pass": qualifiers_pass,
        }
        return ReviewItem(
            review_item_id=review_item_id,
            review_item_hash=canonical_hash(body),
            case_id=inputs.case.case_id,
            gold_id=gold_id,
            preceding_consultant_text=preceding,
            current_employee_text=transcript[-1].text,
            prior_evidence_summaries=prior_summaries,
            candidate_observation=candidate,
            gold_rubric=rubric,
            edge_qualifiers_pass=qualifiers_pass,
        )

    for edge in edges:
        items.append(make_item(edge.gold_id, edge.proposal_key, edge.qualifiers_pass))
    for key in unmatched_proposal_keys:
        items.append(make_item(UNMATCHED_GOLD_ID, key, None))
    return tuple(items)


def order_review_queue(
    items: Sequence[ReviewItem], *, ordering_seed: str
) -> tuple[ReviewItem, ...]:
    """以 batch 固定 seed 重排;不洩漏原始 case 順序(§14.1)。"""

    def sort_key(item: ReviewItem) -> str:
        return hashlib.sha256(
            f"{ordering_seed}:{item.review_item_id}".encode("utf-8")
        ).hexdigest()

    return tuple(sorted(items, key=sort_key))


class ReviewImportError(ValueError):
    """A submitted review decision violated the import contract (§14.3)."""


def reason_contains_provider_identity(reason: str) -> bool:
    folded = reason.casefold()
    return any(marker in folded for marker in _FORBIDDEN_REASON_MARKERS)


@dataclass(frozen=True)
class ImportedReview:
    decisions_by_item: dict[UUID, TurnEvalReviewDecision]


def import_review_decisions(
    items: Sequence[ReviewItem],
    decisions: Sequence[TurnEvalReviewDecision],
) -> ImportedReview:
    """Validate submitted decisions against the queue (§14.3)."""

    item_by_id = {item.review_item_id: item for item in items}
    accepted: dict[UUID, TurnEvalReviewDecision] = {}
    for decision in decisions:
        item = item_by_id.get(decision.review_item_id)
        if item is None:
            raise ReviewImportError(
                f"decision references unknown review item {decision.review_item_id}"
            )
        if decision.review_item_hash != item.review_item_hash:
            raise ReviewImportError(
                f"decision hash does not match review item {decision.review_item_id}"
            )
        if reason_contains_provider_identity(decision.reason):
            raise ReviewImportError(
                "review reason must not mention provider/model identity"
            )
        existing = accepted.get(decision.review_item_id)
        if existing is None:
            accepted[decision.review_item_id] = decision
            continue
        if existing == decision:
            continue  # idempotent re-submit
        if (
            decision.revision > existing.revision
            and decision.supersedes_revision == existing.revision
        ):
            accepted[decision.review_item_id] = decision
            continue
        raise ReviewImportError(
            f"conflicting decision for {decision.review_item_id} without a new revision"
        )
    return ImportedReview(decisions_by_item=accepted)


def missing_decisions(
    items: Sequence[ReviewItem], imported: ImportedReview
) -> tuple[UUID, ...]:
    """Review item IDs with no decision — batch is REVIEW_INCOMPLETE (§14.3)."""

    return tuple(
        item.review_item_id
        for item in items
        if item.review_item_id not in imported.decisions_by_item
    )


def edge_decision_map(
    imported: ImportedReview,
    review_items: Sequence[ReviewItem],
) -> dict[tuple[str, str], ReviewDecisionLabel]:
    """Map each adjudicated review item back to an (gold_id, proposal_key) key
    the matcher/metrics consume. Unmatched items key on UNMATCHED_GOLD_ID."""

    result: dict[tuple[str, str], ReviewDecisionLabel] = {}
    for item in review_items:
        decision = imported.decisions_by_item.get(item.review_item_id)
        if decision is None:
            continue
        result[(item.gold_id, item.candidate_observation.proposal_key)] = (
            decision.decision
        )
    return result
