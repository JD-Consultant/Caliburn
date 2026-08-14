"""Run-scoped candidate state inside the one durable consultant graph."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Annotated, Any, Literal
from uuid import UUID, uuid5

from pydantic import Field, StringConstraints, model_validator

from app.consultant.candidate_wire import CandidateEditBatch
from app.consultant.document_authority import (
    DocumentAuthorityError,
    apply_document_actions,
)
from app.consultant.document_review import create_document_changeset
from app.consultant.results import ReviewableDocumentChange, SkillId
from app.consultant.state import (
    ApprovedJobDocument,
    DocumentChangeSet,
    DocumentChangeStatus,
    DocumentPatchAction,
    DurableModel,
    NonEmptyText,
)


Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_UNRESOLVED = {
    DocumentChangeStatus.PENDING,
    DocumentChangeStatus.DEFERRED,
}


class CandidateWorkspaceError(ValueError):
    pass


class CandidateRevisionConflict(CandidateWorkspaceError):
    pass


class CandidateToolCallConflict(CandidateWorkspaceError):
    pass


class CandidateDependencyError(CandidateWorkspaceError):
    pass


class CandidateToolReceipt(DurableModel):
    request_sha256: Digest
    candidate_revision: int = Field(ge=1)
    revision_digest: Digest
    changeset_id: UUID
    action_ids: tuple[UUID, ...] = Field(min_length=1)
    external_dependency_action_ids: tuple[UUID, ...] = ()


class CandidateEditReceipt(DurableModel):
    status: Literal["applied"] = "applied"
    candidate_revision: int = Field(ge=1)
    revision_digest: Digest
    changeset_id: UUID
    action_ids: tuple[UUID, ...] = Field(min_length=1)
    external_dependency_action_ids: tuple[UUID, ...] = ()


class CandidateWorkspace(DurableModel):
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    candidate_revision: int = Field(ge=1)
    request_sha256: Digest
    revision_digest: Digest
    used_skill_ids: tuple[SkillId, ...]
    changeset: DocumentChangeSet
    tool_receipts: dict[str, CandidateToolReceipt]

    @model_validator(mode="after")
    def latest_revision_has_a_matching_receipt(self) -> CandidateWorkspace:
        if len(self.used_skill_ids) != len(set(self.used_skill_ids)):
            raise ValueError("duplicate candidate used_skill_ids")
        if not self.tool_receipts:
            raise ValueError("candidate workspace requires a tool receipt")
        latest = [
            receipt
            for receipt in self.tool_receipts.values()
            if receipt.candidate_revision == self.candidate_revision
        ]
        if len(latest) != 1:
            raise ValueError("candidate workspace latest revision receipt is ambiguous")
        receipt = latest[0]
        if (
            receipt.request_sha256 != self.request_sha256
            or receipt.revision_digest != self.revision_digest
            or receipt.changeset_id != self.changeset.changeset_id
            or receipt.action_ids
            != tuple(action.action_id for action in self.changeset.actions)
        ):
            raise ValueError("candidate workspace latest receipt does not match changeset")
        return self


class CandidateStageRequest(DurableModel):
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    tool_call_id: NonEmptyText
    batch: CandidateEditBatch
    selected_skill_ids: tuple[SkillId, ...]
    loaded_skill_ids: tuple[SkillId, ...]

    @model_validator(mode="after")
    def skill_receipts_are_consistent(self) -> CandidateStageRequest:
        if len(self.selected_skill_ids) != len(set(self.selected_skill_ids)):
            raise ValueError("duplicate selected_skill_ids")
        if len(self.loaded_skill_ids) != len(set(self.loaded_skill_ids)):
            raise ValueError("duplicate loaded_skill_ids")
        if not set(self.loaded_skill_ids) <= set(self.selected_skill_ids):
            raise ValueError("loaded Skills must be selected")
        return self


class VerifiedCandidateStage(DurableModel):
    run_id: UUID
    baseline_revision: int = Field(ge=0)
    base_candidate_revision: int = Field(ge=0)
    tool_call_id: NonEmptyText
    request_sha256: Digest
    summary: NonEmptyText
    changes: tuple[ReviewableDocumentChange, ...] = Field(min_length=1)
    used_skill_ids: tuple[SkillId, ...]

    @model_validator(mode="after")
    def used_skills_are_unique(self) -> VerifiedCandidateStage:
        if len(self.used_skill_ids) != len(set(self.used_skill_ids)):
            raise ValueError("duplicate candidate used_skill_ids")
        return self


def _canonical_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return sha256(encoded).hexdigest()


def candidate_request_sha256(request: CandidateStageRequest) -> str:
    payload = request.model_dump(mode="json", exclude={"tool_call_id"})
    return _canonical_digest(payload)


def candidate_revision_digest(changeset: DocumentChangeSet) -> str:
    return _canonical_digest(changeset.model_dump(mode="json"))


def _receipt_from_tool(receipt: CandidateToolReceipt) -> CandidateEditReceipt:
    return CandidateEditReceipt(
        candidate_revision=receipt.candidate_revision,
        revision_digest=receipt.revision_digest,
        changeset_id=receipt.changeset_id,
        action_ids=receipt.action_ids,
        external_dependency_action_ids=receipt.external_dependency_action_ids,
    )


def _review_actions(
    review_queue: Mapping[str, dict[str, Any]],
) -> dict[UUID, DocumentPatchAction]:
    actions: dict[UUID, DocumentPatchAction] = {}
    for raw in review_queue.values():
        bundle = DocumentChangeSet.model_validate(raw)
        for action in bundle.actions:
            if action.action_id in actions:
                raise CandidateDependencyError(
                    f"duplicate review action identity {action.action_id}"
                )
            actions[action.action_id] = action
    return actions


def _dependency_closure(
    roots: Sequence[UUID],
    actions: Mapping[UUID, DocumentPatchAction],
) -> tuple[DocumentPatchAction, ...]:
    ordered: list[DocumentPatchAction] = []
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(action_id: UUID) -> None:
        if action_id in visiting:
            raise CandidateDependencyError("external dependency cycle")
        if action_id in visited:
            return
        action = actions.get(action_id)
        if action is None:
            raise CandidateDependencyError(
                f"external dependency {action_id} does not exist"
            )
        if action.status not in _UNRESOLVED:
            raise CandidateDependencyError(
                f"external dependency {action_id} is {action.status.value}"
            )
        visiting.add(action_id)
        for dependency_id in action.depends_on_action_ids:
            visit(dependency_id)
        visiting.remove(action_id)
        visited.add(action_id)
        ordered.append(action)

    for root in sorted(set(roots), key=str):
        visit(root)
    return tuple(ordered)


def _entity_ids(document: ApprovedJobDocument) -> frozenset[UUID]:
    return frozenset(
        {
            *(item.duty_id for item in document.duties),
            *(item.task_id for item in document.tasks),
            *(item.item_id for item in document.opks),
        }
    )


def candidate_mapping_authority(
    state: Mapping[str, Any],
    *,
    depends_on_action_ids: Sequence[UUID],
    supersedes_action_ids: Sequence[UUID],
) -> tuple[frozenset[UUID], frozenset[UUID]]:
    """Derive only application-owned handles while the adapter holds its lock."""

    document = ApprovedJobDocument.model_validate(state["approved_document"])
    actions = _review_actions(state.get("review_queue", {}))
    dependency_actions = _dependency_closure(depends_on_action_ids, actions)
    supersession_actions = _dependency_closure(supersedes_action_ids, actions)
    try:
        conditional_document = apply_document_actions(document, dependency_actions)
    except DocumentAuthorityError as error:
        raise CandidateDependencyError(
            f"external dependency closure is not a valid conditional baseline: {error}"
        ) from error
    allowed_actions = frozenset(
        action.action_id
        for action in (*dependency_actions, *supersession_actions)
    )
    return _entity_ids(document) | _entity_ids(conditional_document), allowed_actions


def _resolved_candidate_dependencies(
    state: Mapping[str, Any],
    changes: Sequence[ReviewableDocumentChange],
) -> tuple[ApprovedJobDocument, tuple[UUID, ...], tuple[ReviewableDocumentChange, ...]]:
    actions = _review_actions(state.get("review_queue", {}))
    all_dependency_roots = tuple(
        action_id for change in changes for action_id in change.depends_on_action_ids
    )
    all_supersession_roots = tuple(
        action_id for change in changes for action_id in change.supersedes_action_ids
    )
    dependency_actions = _dependency_closure(all_dependency_roots, actions)
    _dependency_closure(all_supersession_roots, actions)
    closure_by_root: dict[UUID, tuple[UUID, ...]] = {}
    for root in set(all_dependency_roots):
        closure_by_root[root] = tuple(
            action.action_id for action in _dependency_closure((root,), actions)
        )
    expanded_changes = tuple(
        change.model_copy(
            update={
                "depends_on_action_ids": tuple(
                    sorted(
                        {
                            action_id
                            for root in change.depends_on_action_ids
                            for action_id in closure_by_root[root]
                        },
                        key=str,
                    )
                )
            }
        )
        for change in changes
    )
    document = ApprovedJobDocument.model_validate(state["approved_document"])
    try:
        conditional_document = apply_document_actions(document, dependency_actions)
    except DocumentAuthorityError as error:
        raise CandidateDependencyError(
            f"external dependency closure is not a valid conditional baseline: {error}"
        ) from error
    return (
        conditional_document,
        tuple(action.action_id for action in dependency_actions),
        expanded_changes,
    )


def materialize_candidate_workspace(
    state: Mapping[str, Any],
    stage: VerifiedCandidateStage,
) -> tuple[CandidateWorkspace, CandidateEditReceipt]:
    """Purely validate and replace one candidate revision; never mutate input state."""

    actual_revision = int(state.get("revision", 0))
    if actual_revision != stage.baseline_revision:
        raise CandidateRevisionConflict(
            f"expected baseline revision {stage.baseline_revision}, found {actual_revision}"
        )
    existing_payload = state.get("active_candidate")
    existing = (
        CandidateWorkspace.model_validate(existing_payload)
        if existing_payload is not None
        else None
    )
    if existing is not None:
        replay = existing.tool_receipts.get(stage.tool_call_id)
        if replay is not None:
            if replay.request_sha256 != stage.request_sha256:
                raise CandidateToolCallConflict(
                    f"candidate tool call {stage.tool_call_id} was reused with another payload"
                )
            return existing, _receipt_from_tool(replay)
        if existing.run_id != stage.run_id:
            raise CandidateRevisionConflict("active candidate belongs to another run")
        if existing.baseline_revision != stage.baseline_revision:
            raise CandidateRevisionConflict("active candidate baseline changed")
    current_candidate_revision = existing.candidate_revision if existing else 0
    if stage.base_candidate_revision != current_candidate_revision:
        raise CandidateRevisionConflict(
            "expected candidate revision "
            f"{current_candidate_revision}, found {stage.base_candidate_revision}"
        )
    next_candidate_revision = current_candidate_revision + 1
    materialization_run_id = uuid5(
        stage.run_id,
        f"candidate-revision:{next_candidate_revision}",
    )
    conditional_document, external_dependencies, expanded_changes = (
        _resolved_candidate_dependencies(state, stage.changes)
    )
    changeset = create_document_changeset(
        document_id=conditional_document.document_id,
        run_id=materialization_run_id,
        summary=stage.summary,
        read_revision=stage.baseline_revision,
        document=conditional_document,
        changes=expanded_changes,
        existing_review_queue=state.get("review_queue", {}),
        interview_work=state.get("interview_work", {}),
        external_dependency_action_ids=external_dependencies,
    )
    revision_digest = candidate_revision_digest(changeset)
    tool_receipt = CandidateToolReceipt(
        request_sha256=stage.request_sha256,
        candidate_revision=next_candidate_revision,
        revision_digest=revision_digest,
        changeset_id=changeset.changeset_id,
        action_ids=tuple(action.action_id for action in changeset.actions),
        external_dependency_action_ids=external_dependencies,
    )
    receipts = dict(existing.tool_receipts) if existing is not None else {}
    receipts[stage.tool_call_id] = tool_receipt
    workspace = CandidateWorkspace(
        run_id=stage.run_id,
        baseline_revision=stage.baseline_revision,
        candidate_revision=next_candidate_revision,
        request_sha256=stage.request_sha256,
        revision_digest=revision_digest,
        used_skill_ids=stage.used_skill_ids,
        changeset=changeset,
        tool_receipts=receipts,
    )
    return workspace, _receipt_from_tool(tool_receipt)
