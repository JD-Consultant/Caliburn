"""OPKS 專用的薄 Proposal contract（ADR 0050、0051）。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from .base import DomainModel, Identifier, NonEmptyText
from .opks import OpksEntityKind, OpksItem


class OpksProposalAction(StrEnum):
    ADD = "add"
    REVISE = "revise"
    REMOVE = "remove"


class OpksProposalStatus(StrEnum):
    PENDING = "pending"
    DEFERRED = "deferred"
    ACCEPTED = "accepted"
    EDITED = "edited"
    REJECTED = "rejected"
    STALE = "stale"


OPKS_ALLOWED_STATUS_TRANSITIONS: dict[
    OpksProposalStatus, frozenset[OpksProposalStatus]
] = {
    OpksProposalStatus.PENDING: frozenset(
        {
            OpksProposalStatus.DEFERRED,
            OpksProposalStatus.ACCEPTED,
            OpksProposalStatus.EDITED,
            OpksProposalStatus.REJECTED,
            OpksProposalStatus.STALE,
        }
    ),
    OpksProposalStatus.DEFERRED: frozenset(
        {
            OpksProposalStatus.ACCEPTED,
            OpksProposalStatus.EDITED,
            OpksProposalStatus.REJECTED,
            OpksProposalStatus.STALE,
        }
    ),
    OpksProposalStatus.ACCEPTED: frozenset(),
    OpksProposalStatus.EDITED: frozenset(),
    OpksProposalStatus.REJECTED: frozenset(),
    OpksProposalStatus.STALE: frozenset(),
}

OPKS_TERMINAL_STATUSES = frozenset(
    status
    for status, allowed in OPKS_ALLOWED_STATUS_TRANSITIONS.items()
    if not allowed
)


def is_allowed_opks_transition(
    current: OpksProposalStatus, target: OpksProposalStatus
) -> bool:
    return target in OPKS_ALLOWED_STATUS_TRANSITIONS[current]


class OpksProposal(DomainModel):
    proposal_id: Identifier
    operation_id: Identifier
    entity_id: Identifier
    entity_kind: OpksEntityKind
    action: OpksProposalAction
    before: OpksItem | None = None
    after: OpksItem | None = None
    edited_after: OpksItem | None = None
    status: OpksProposalStatus = OpksProposalStatus.PENDING
    rejection_reason: NonEmptyText | None = None
    stale_reason: NonEmptyText | None = None
    base_authority_generation: int = Field(ge=0)
    created_at: datetime
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def snapshots_match_action(self):
        valid = {
            OpksProposalAction.ADD: self.before is None and self.after is not None,
            OpksProposalAction.REVISE: self.before is not None
            and self.after is not None,
            OpksProposalAction.REMOVE: self.before is not None
            and self.after is None,
        }[self.action]
        if not valid:
            raise ValueError(f"{self.action.value} proposal snapshot shape is invalid")
        return self

    @model_validator(mode="after")
    def snapshots_keep_identity_and_kind(self):
        for label, item in (
            ("before", self.before),
            ("after", self.after),
            ("edited_after", self.edited_after),
        ):
            if item is None:
                continue
            if item.entity_id != self.entity_id:
                raise ValueError(f"{label} must keep the proposal entity identity")
            if item.entity_kind is not self.entity_kind:
                raise ValueError(f"{label} must keep the proposal entity kind")
        return self

    @model_validator(mode="after")
    def edited_snapshot_changes_text_only(self):
        if self.status is OpksProposalStatus.EDITED:
            if self.edited_after is None:
                raise ValueError("edited status requires edited_after")
            if self.after is None:
                raise ValueError("edited status requires a non-null after snapshot")
            if self.edited_after.text == self.after.text:
                raise ValueError("edited_after must differ from after")
            if self.edited_after.model_dump(exclude={"text"}) != self.after.model_dump(
                exclude={"text"}
            ):
                raise ValueError("edited_after may only change text")
        elif self.edited_after is not None:
            raise ValueError("edited_after belongs to the edited status only")
        return self

    @model_validator(mode="after")
    def status_payloads_are_scoped(self):
        if (
            self.rejection_reason is not None
            and self.status is not OpksProposalStatus.REJECTED
        ):
            raise ValueError("rejection reason belongs to the rejected status only")
        if self.status is OpksProposalStatus.STALE:
            if self.stale_reason is None:
                raise ValueError("stale status requires an employee-visible reason")
        elif self.stale_reason is not None:
            raise ValueError("stale reason belongs to the stale status only")
        return self

    @model_validator(mode="after")
    def resolution_time_matches_status(self):
        if self.status in {
            OpksProposalStatus.PENDING,
            OpksProposalStatus.DEFERRED,
        }:
            if self.resolved_at is not None:
                raise ValueError("active proposal must not be resolved")
        elif self.resolved_at is None:
            raise ValueError("terminal proposal requires resolved_at")
        return self
