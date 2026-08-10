"""Durable employee decisions for the independent OPKS Proposal contract."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.core.domain import (
    CurrentJdOpks,
    JdHeader,
    OpksEntityKind,
    OpksEvidenceLink,
    OpksItem,
    OpksProposal,
    OpksProposalAction,
    OpksProposalStatus,
    SourceKind,
    SourceRef,
    is_allowed_opks_transition,
)
from app.core.authority import commit_authority_change
from app.core.opks_integrity import stale_invalid_opks_proposals
from app.core.persistence import (
    OPKS_DIRECT_EDIT_SCHEMA_ID,
    OPKS_PROPOSAL_DECISION_SCHEMA_ID,
    JobAnalysisUnitOfWorkFactory,
    JournalEntry,
    OpksDirectEditPayload,
    OpksProposalDecisionPayload,
)

from .errors import (
    DocumentNotFound,
    IdempotencyConflict,
    InvalidProposalDecision,
    OpksProposalNotDecidable,
    OpksProposalNotFound,
)
from .transition import JobAnalysisState


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _direct_edit_entry_id(decision_id: str) -> str:
    return f"{decision_id}-direct-edit"


def remove_opks_item_and_indicator_refs(
    current_opks: CurrentJdOpks,
    entity_id: str,
) -> CurrentJdOpks:
    before = current_opks.item_by_id(entity_id)
    if before is None:
        return current_opks
    remaining: list[OpksItem] = []
    for item in current_opks.items:
        if item.entity_id == entity_id:
            continue
        if (
            before.entity_kind is OpksEntityKind.INDICATOR
            and entity_id in item.indicator_refs
        ):
            item = item.model_copy(
                update={
                    "indicator_refs": tuple(
                        ref for ref in item.indicator_refs if ref != entity_id
                    )
                }
            )
        remaining.append(item)
    return CurrentJdOpks(items=tuple(remaining))


def _replace_proposal(
    proposals: tuple[OpksProposal, ...],
    decided: OpksProposal,
) -> tuple[OpksProposal, ...]:
    return tuple(
        decided if proposal.proposal_id == decided.proposal_id else proposal
        for proposal in proposals
    )


def _apply_item(
    current_opks: CurrentJdOpks,
    proposal: OpksProposal,
    item: OpksItem | None,
) -> CurrentJdOpks:
    if proposal.action is OpksProposalAction.ADD:
        assert item is not None
        return CurrentJdOpks(
            items=(
                *current_opks.items,
                item.model_copy(
                    update={
                        "display_order": current_opks.next_display_order(
                            item.entity_kind
                        )
                    }
                ),
            )
        )
    if proposal.action is OpksProposalAction.REVISE:
        assert item is not None
        existing = current_opks.item_by_id(proposal.entity_id)
        if existing is None:
            return current_opks
        return CurrentJdOpks(
            items=tuple(
                item.model_copy(update={"display_order": existing.display_order})
                if current.entity_id == proposal.entity_id
                else current
                for current in current_opks.items
            )
        )
    return remove_opks_item_and_indicator_refs(
        current_opks,
        proposal.entity_id,
    )


async def decide_opks_proposal(
    uow_factory: JobAnalysisUnitOfWorkFactory,
    *,
    document_id: UUID,
    proposal_id: str,
    decision_id: str,
    decision: str,
    edited_text: str | None = None,
    reason: str | None = None,
) -> OpksProposal:
    target_status = OpksProposalStatus(decision)
    payload = OpksProposalDecisionPayload(
        proposal_id=proposal_id,
        decision=target_status,
        employee_text=edited_text,
        reason=reason,
    )
    async with uow_factory() as uow:
        record = await uow.documents.get(document_id, for_update=True)
        if record is None:
            raise DocumentNotFound(f"document {document_id} was not found")
        current_jd = await uow.tasks.list(document_id)
        current_opks = CurrentJdOpks(items=await uow.opks.list(document_id))
        proposals = await uow.opks_proposals.list(document_id)

        replay = await uow.journal.get(document_id, decision_id)
        if replay is not None:
            if replay.kind != "proposal_decision" or replay.payload != payload:
                raise IdempotencyConflict(
                    f"entry {decision_id!r} already records another decision"
                )
            decided = next(
                (
                    proposal
                    for proposal in proposals
                    if proposal.proposal_id == proposal_id
                ),
                None,
            )
            if decided is None:
                raise OpksProposalNotFound(
                    f"OPKS proposal {proposal_id!r} was not found"
                )
            return decided

        refreshed = stale_invalid_opks_proposals(
            proposals,
            current_opks=current_opks,
            current_jd=current_jd,
        )
        proposal = next(
            (
                candidate
                for candidate in refreshed
                if candidate.proposal_id == proposal_id
            ),
            None,
        )
        if proposal is None:
            raise OpksProposalNotFound(
                f"OPKS proposal {proposal_id!r} was not found"
            )
        if proposal.status is OpksProposalStatus.STALE:
            if refreshed != proposals:
                await commit_authority_change(
                    uow,
                    record=record,
                    state=JobAnalysisState(
                        jd_header=record.jd_header,
                        current_duties=await uow.duties.list(document_id),
                        work_model=record.work_model,
                        current_jd=current_jd,
                        proposals=await uow.proposals.list(document_id),
                        current_opks=current_opks,
                        opks_proposals=refreshed,
                    ),
                    updated_at=_utcnow(),
                )
            return proposal
        if not is_allowed_opks_transition(proposal.status, target_status):
            raise OpksProposalNotDecidable(
                f"OPKS proposal {proposal_id!r} is {proposal.status.value}"
            )
        if (
            target_status is OpksProposalStatus.EDITED
            and proposal.after is None
        ):
            raise InvalidProposalDecision(
                "a remove OPKS proposal has no replacement text to edit"
            )

        now = _utcnow()
        edited_after: OpksItem | None = None
        applied_item = proposal.after
        journal_entries = [
            JournalEntry(
                document_id=document_id,
                entry_id=decision_id,
                kind="proposal_decision",
                payload_schema_id=OPKS_PROPOSAL_DECISION_SCHEMA_ID,
                payload=payload,
                created_at=now,
            )
        ]
        if target_status is OpksProposalStatus.EDITED:
            if proposal.after is None or edited_text is None:
                raise InvalidProposalDecision(
                    "an edited OPKS decision requires replacement text"
                )
            edited_after = proposal.after.model_copy(update={"text": edited_text})
            edit_entry_id = _direct_edit_entry_id(decision_id)
            applied_item = edited_after.model_copy(
                update={
                    "evidence_links": (
                        *edited_after.evidence_links,
                        OpksEvidenceLink(
                            source_ref=SourceRef(
                                kind=SourceKind.DIRECT_EDIT,
                                id=edit_entry_id,
                            )
                        ),
                    )
                }
            )
            journal_entries.append(
                JournalEntry(
                    document_id=document_id,
                    entry_id=edit_entry_id,
                    kind="direct_edit",
                    payload_schema_id=OPKS_DIRECT_EDIT_SCHEMA_ID,
                    payload=OpksDirectEditPayload(
                        action="edit",
                        before=proposal.after,
                        after=applied_item,
                    ),
                    created_at=now,
                )
            )

        terminal = target_status is not OpksProposalStatus.DEFERRED
        decided = OpksProposal.model_validate(
            {
                **proposal.model_dump(),
                "status": target_status,
                "edited_after": edited_after,
                "rejection_reason": reason,
                "resolved_at": now if terminal else None,
            }
        )
        next_opks = current_opks
        if target_status in {
            OpksProposalStatus.ACCEPTED,
            OpksProposalStatus.EDITED,
        }:
            next_opks = _apply_item(current_opks, proposal, applied_item)

        next_proposals = stale_invalid_opks_proposals(
            _replace_proposal(refreshed, decided),
            current_opks=next_opks,
            current_jd=current_jd,
            now=now,
        )
        decided = next(
            proposal
            for proposal in next_proposals
            if proposal.proposal_id == proposal_id
        )
        await commit_authority_change(
            uow,
            record=record,
            state=JobAnalysisState(
                jd_header=record.jd_header,
                current_duties=await uow.duties.list(document_id),
                work_model=record.work_model,
                current_jd=current_jd,
                proposals=await uow.proposals.list(document_id),
                current_opks=next_opks,
                opks_proposals=next_proposals,
            ),
            journal_entries=tuple(journal_entries),
            updated_at=now,
        )
        return decided
