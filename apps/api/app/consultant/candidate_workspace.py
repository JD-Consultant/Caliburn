"""Run-scoped candidate state inside the one durable consultant graph."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
from typing import Annotated, Any, Literal
from uuid import UUID, uuid5

from pydantic import Field, JsonValue, StringConstraints, model_validator

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
    DocumentPatchOperation,
    DurableModel,
    NonEmptyText,
)


Digest = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
_UNRESOLVED = {
    DocumentChangeStatus.PENDING,
    DocumentChangeStatus.DEFERRED,
}
_SATISFIED = {
    DocumentChangeStatus.ACCEPTED,
    DocumentChangeStatus.EDIT_ACCEPTED,
}


class CandidateWorkspaceError(ValueError):
    pass


class CandidateRevisionConflict(CandidateWorkspaceError):
    pass


class CandidateToolCallConflict(CandidateWorkspaceError):
    pass


class CandidateDependencyError(CandidateWorkspaceError):
    pass


class CandidateEditRejected(CandidateWorkspaceError):
    """A deterministic candidate-stage issue the model can correct in the same run."""

    def __init__(
        self,
        *,
        baseline_revision: int,
        candidate_revision: int,
        issues: Sequence[str],
    ) -> None:
        self.baseline_revision = baseline_revision
        self.candidate_revision = candidate_revision
        self.issues = tuple(issue for issue in issues if issue.strip())
        if not self.issues:
            raise ValueError("candidate rejection requires an actionable issue")
        super().__init__("; ".join(self.issues))


class CandidateEditAction(DurableModel):
    """Compact semantic projection of one persisted candidate patch action."""

    action_id: UUID
    operation: DocumentPatchOperation
    path: NonEmptyText
    before: JsonValue | None = None
    after: JsonValue | None = None
    depends_on_action_ids: tuple[UUID, ...] = ()
    supersedes_action_ids: tuple[UUID, ...] = ()
    atomic_subgroup_id: UUID | None = None
    status: DocumentChangeStatus
    stale_reason: NonEmptyText | None = None


def _edit_action(action: DocumentPatchAction) -> CandidateEditAction:
    return CandidateEditAction(
        action_id=action.action_id,
        operation=action.operation,
        path=action.path,
        before=action.before,
        after=action.after,
        depends_on_action_ids=action.depends_on_action_ids,
        supersedes_action_ids=action.supersedes_action_ids,
        atomic_subgroup_id=action.atomic_subgroup_id,
        status=action.status,
        stale_reason=action.stale_reason,
    )


class CandidateToolReceipt(DurableModel):
    request_sha256: Digest
    candidate_revision: int = Field(ge=1)
    revision_digest: Digest
    changeset_id: UUID
    source_ids: tuple[UUID, ...] = Field(min_length=1)
    action_ids: tuple[UUID, ...] = Field(min_length=1)
    external_dependency_action_ids: tuple[UUID, ...] = ()
    actions: tuple[CandidateEditAction, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def action_projection_matches_handles(self) -> CandidateToolReceipt:
        if self.action_ids != tuple(action.action_id for action in self.actions):
            raise ValueError("candidate tool receipt action handles do not match actions")
        return self


class CandidateEditReceipt(DurableModel):
    status: Literal["applied"] = "applied"
    candidate_revision: int = Field(ge=1)
    revision_digest: Digest
    changeset_id: UUID
    action_ids: tuple[UUID, ...] = Field(min_length=1)
    external_dependency_action_ids: tuple[UUID, ...] = ()
    actions: tuple[CandidateEditAction, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def action_projection_matches_handles(self) -> CandidateEditReceipt:
        if self.action_ids != tuple(action.action_id for action in self.actions):
            raise ValueError("candidate edit receipt action handles do not match actions")
        return self


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
            or receipt.source_ids != self.changeset.source_ids
            or receipt.action_ids
            != tuple(action.action_id for action in self.changeset.actions)
            or receipt.actions
            != tuple(_edit_action(action) for action in self.changeset.actions)
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


def candidate_staging_baseline(
    state: Mapping[str, Any],
    *,
    run_id: UUID,
) -> int:
    """Return the application-verified baseline retained for one active run."""

    actual_revision = int(state.get("revision", 0))
    active_payload = state.get("active_candidate")
    if active_payload is None:
        return actual_revision
    active = CandidateWorkspace.model_validate(active_payload)
    if active.run_id != run_id:
        raise CandidateRevisionConflict("active candidate belongs to another run")
    if actual_revision < active.baseline_revision:
        raise CandidateRevisionConflict(
            "thread revision predates the active candidate baseline"
        )
    return active.baseline_revision


def _receipt_from_tool(receipt: CandidateToolReceipt) -> CandidateEditReceipt:
    return CandidateEditReceipt(
        candidate_revision=receipt.candidate_revision,
        revision_digest=receipt.revision_digest,
        changeset_id=receipt.changeset_id,
        action_ids=receipt.action_ids,
        external_dependency_action_ids=receipt.external_dependency_action_ids,
        actions=receipt.actions,
    )


def candidate_edit_receipt_for_tool_call(
    workspace: CandidateWorkspace,
    tool_call_id: str,
) -> CandidateEditReceipt:
    """Return the persisted result for one payload-bound candidate Tool call."""

    try:
        receipt = workspace.tool_receipts[tool_call_id]
    except KeyError as error:
        raise CandidateToolCallConflict(
            f"candidate tool call {tool_call_id} has no persisted receipt"
        ) from error
    return _receipt_from_tool(receipt)


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
    root_ids = tuple(sorted(set(roots), key=str))
    for action_id in root_ids:
        action = actions.get(action_id)
        if action is None:
            raise CandidateDependencyError(
                f"external dependency {action_id} does not exist"
            )
        if action.status not in _UNRESOLVED:
            raise CandidateDependencyError(
                f"external dependency {action_id} is {action.status.value}"
            )

    members_by_group: dict[UUID, tuple[DocumentPatchAction, ...]] = {}
    for action in actions.values():
        if action.atomic_subgroup_id is None:
            continue
        members_by_group[action.atomic_subgroup_id] = (
            *members_by_group.get(action.atomic_subgroup_id, ()),
            action,
        )

    selected: set[UUID] = set()
    pending = list(reversed(root_ids))
    while pending:
        action_id = pending.pop()
        action = actions.get(action_id)
        if action is None:
            raise CandidateDependencyError(
                f"external dependency {action_id} does not exist"
            )
        if action.status in _SATISFIED:
            continue
        if action.status not in _UNRESOLVED:
            raise CandidateDependencyError(
                f"external dependency {action_id} is {action.status.value}"
            )
        if action_id in selected:
            continue
        selected.add(action_id)
        pending.extend(reversed(action.depends_on_action_ids))
        if action.atomic_subgroup_id is not None:
            for member in members_by_group[action.atomic_subgroup_id]:
                if member.status in _SATISFIED:
                    continue
                if member.status not in _UNRESOLVED:
                    raise CandidateDependencyError(
                        "external atomic subgroup contains terminal action "
                        f"{member.action_id} ({member.status.value})"
                    )
                if member.action_id not in selected:
                    pending.append(member.action_id)

    ordered: list[DocumentPatchAction] = []
    visiting: set[UUID] = set()
    visited: set[UUID] = set()

    def visit(action_id: UUID) -> None:
        if action_id in visiting:
            raise CandidateDependencyError("external dependency cycle")
        if action_id in visited:
            return
        visiting.add(action_id)
        action = actions[action_id]
        for dependency_id in action.depends_on_action_ids:
            if dependency_id in selected:
                visit(dependency_id)
        visiting.remove(action_id)
        visited.add(action_id)
        ordered.append(action)

    for action_id in root_ids:
        if action_id in selected:
            visit(action_id)
    for action_id in sorted(selected, key=str):
        visit(action_id)
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

    expected_baseline = candidate_staging_baseline(state, run_id=stage.run_id)
    if stage.baseline_revision != expected_baseline:
        raise CandidateRevisionConflict(
            f"expected baseline revision {expected_baseline}, "
            f"found {stage.baseline_revision}"
        )
    existing_payload = state.get("active_candidate")
    existing = (
        CandidateWorkspace.model_validate(existing_payload)
        if existing_payload is not None
        else None
    )
    if existing is not None:
        if existing.run_id != stage.run_id:
            raise CandidateRevisionConflict("active candidate belongs to another run")
        if existing.baseline_revision != stage.baseline_revision:
            raise CandidateRevisionConflict("active candidate baseline changed")
        replay = existing.tool_receipts.get(stage.tool_call_id)
        if replay is not None:
            if replay.request_sha256 != stage.request_sha256:
                raise CandidateToolCallConflict(
                    f"candidate tool call {stage.tool_call_id} was reused with another payload"
                )
            return existing, _receipt_from_tool(replay)
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
        source_ids=changeset.source_ids,
        action_ids=tuple(action.action_id for action in changeset.actions),
        external_dependency_action_ids=external_dependencies,
        actions=tuple(_edit_action(action) for action in changeset.actions),
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
