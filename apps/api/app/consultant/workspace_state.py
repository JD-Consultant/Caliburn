"""Durable identity and validation metadata for one JD workspace."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from types import MappingProxyType
from typing import Literal, Mapping, Protocol, Sequence, cast
from uuid import UUID

from deepagents.backends import StoreBackend
from deepagents.backends.utils import file_data_to_string
from langgraph.store.base import BaseStore
from pydantic import AfterValidator, Field, StringConstraints, model_validator
from typing_extensions import Annotated

from app.consultant.state import ApprovedJobDocument, DurableModel


_MANIFEST_KEY = "manifest"


def _document_namespace(document_id: UUID, leaf: str) -> tuple[str, str, str, str]:
    if not isinstance(document_id, UUID):
        raise TypeError("document_id must be an application-issued UUID")
    return ("caliburn", "consultant", str(document_id), leaf)


def workspace_namespace(document_id: UUID) -> tuple[str, str, str, str]:
    return _document_namespace(document_id, "workspace")


def workspace_metadata_namespace(document_id: UUID) -> tuple[str, str, str, str]:
    return _document_namespace(document_id, "workspace-metadata")


def workspace_decision_namespace(document_id: UUID) -> tuple[str, str, str, str]:
    return _document_namespace(document_id, "workspace-decisions")


def _sha256_digest(value: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("must be a lowercase sha256 digest")
    return value


Sha256Digest = Annotated[
    str,
    StringConstraints(strict=True),
    AfterValidator(_sha256_digest),
]


class WorkspaceRebaseChange(Protocol):
    path: str
    before: str | None
    after: str | None


class WorkspaceRebasePlanProtocol(Protocol):
    expected_workspace_digest: Sha256Digest
    result_workspace_digest: Sha256Digest | None
    changes: Sequence[WorkspaceRebaseChange]


class WorkspaceValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"
    CONFLICTED = "conflicted"


class WorkspaceDiagnosticSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class WorkspaceDiagnostic(DurableModel):
    code: Annotated[str, StringConstraints(min_length=1)]
    path: Annotated[str, StringConstraints(min_length=1, max_length=160)] = "/workspace"
    message: Annotated[str, StringConstraints(min_length=1, max_length=240)]
    severity: WorkspaceDiagnosticSeverity = WorkspaceDiagnosticSeverity.ERROR


class WorkspaceManifest(DurableModel):
    schema_version: Literal[1] = 1
    generation: int = Field(ge=0)
    resource_digest: Sha256Digest
    approved_baseline_revision: int = Field(ge=0)
    approved_baseline_digest: Sha256Digest
    evidence_basis_digest: Sha256Digest
    validation_status: WorkspaceValidationStatus
    diagnostics: tuple[WorkspaceDiagnostic, ...] = ()
    entity_ids_by_handle: dict[str, UUID] = Field(default_factory=dict)

    @model_validator(mode="after")
    def manifest_is_internally_consistent(self) -> WorkspaceManifest:
        stable_ids = tuple(self.entity_ids_by_handle.values())
        if len(stable_ids) != len(set(stable_ids)):
            raise ValueError("duplicate stable ID in workspace handle registry")
        if self.validation_status is WorkspaceValidationStatus.VALID and any(
            diagnostic.severity is WorkspaceDiagnosticSeverity.ERROR
            for diagnostic in self.diagnostics
        ):
            raise ValueError("valid workspace cannot have error diagnostics")
        return self

    def validate_files(self, files: Mapping[str, str | bytes]) -> None:
        if (
            self.validation_status
            in {
                WorkspaceValidationStatus.VALID,
                WorkspaceValidationStatus.CONFLICTED,
            }
            and self.resource_digest != workspace_resource_digest(files)
        ):
            raise ValueError("resource digest does not match workspace files")


@dataclass(frozen=True, slots=True)
class WorkspaceSnapshot:
    files: Mapping[str, str]
    manifest: WorkspaceManifest

    def __post_init__(self) -> None:
        object.__setattr__(self, "files", MappingProxyType(dict(self.files)))


class StoreBackedWorkspace:
    """One document-scoped workspace composed from the official Store backend."""

    def __init__(self, *, store: BaseStore, document_id: UUID) -> None:
        self.store = store
        self.document_id = document_id
        self.backend = StoreBackend(
            namespace=lambda _runtime: workspace_namespace(document_id),
            store=store,
        )

    async def ensure_initialized(
        self,
        *,
        approved_document: ApprovedJobDocument,
        approved_revision: int,
    ) -> WorkspaceManifest:
        if approved_document.document_id != self.document_id:
            raise ValueError("approved document scope does not match workspace")
        if approved_revision < 0:
            raise ValueError("approved_revision must be non-negative")

        existing = await self._manifest()
        if existing is not None:
            return existing

        from app.consultant.workspace_resources import project_workspace_files

        files = await self._read_files()
        projection = project_workspace_files(approved_document, handle_registry={})
        if not files:
            for path, content in projection.files.items():
                result = await self.backend.awrite(path, content)
                if result.error is not None:
                    raise RuntimeError(result.error)
            files = dict(projection.files)
            validation_status = WorkspaceValidationStatus.VALID
        else:
            validation_status = WorkspaceValidationStatus.UNVALIDATED

        manifest = WorkspaceManifest(
            generation=0,
            resource_digest=workspace_resource_digest(files),
            approved_baseline_revision=approved_revision,
            approved_baseline_digest=_approved_document_digest(approved_document),
            evidence_basis_digest=cast(Sha256Digest, sha256(b"").hexdigest()),
            validation_status=validation_status,
            entity_ids_by_handle=dict(projection.handle_registry),
        )
        await self._put_manifest(manifest)
        return manifest

    async def read_snapshot(self) -> WorkspaceSnapshot:
        manifest = await self._manifest()
        if manifest is None:
            raise RuntimeError("workspace is not initialized")
        files = await self._read_files()
        actual_digest = workspace_resource_digest(files)
        if actual_digest != manifest.resource_digest:
            conflict_diagnostics = tuple(
                diagnostic
                for diagnostic in manifest.diagnostics
                if diagnostic.code == "workspace-rebase-conflict"
            )
            manifest = manifest.model_copy(
                update={
                    "resource_digest": actual_digest,
                    "validation_status": (
                        WorkspaceValidationStatus.CONFLICTED
                        if conflict_diagnostics
                        else WorkspaceValidationStatus.UNVALIDATED
                    ),
                    "diagnostics": conflict_diagnostics,
                }
            )
            await self._put_manifest(manifest)
        return WorkspaceSnapshot(files=files, manifest=manifest)

    async def commit_validation(
        self,
        *,
        expected_resource_digest: Sha256Digest,
        evidence_basis_digest: Sha256Digest,
        validation_status: WorkspaceValidationStatus,
        diagnostics: tuple[WorkspaceDiagnostic, ...],
        entity_ids_by_handle: Mapping[str, UUID],
    ) -> WorkspaceManifest:
        """Persist validation only if it still describes the real Store bytes."""

        current = await self.read_snapshot()
        if current.manifest.resource_digest != expected_resource_digest:
            raise ValueError("workspace changed during validation")
        manifest = current.manifest.model_copy(
            update={
                "generation": current.manifest.generation + 1,
                "resource_digest": expected_resource_digest,
                "evidence_basis_digest": evidence_basis_digest,
                "validation_status": validation_status,
                "diagnostics": diagnostics,
                "entity_ids_by_handle": dict(entity_ids_by_handle),
            }
        )
        await self._put_manifest(manifest)
        return manifest

    async def apply_rebase(
        self,
        *,
        plan: WorkspaceRebasePlanProtocol,
        approved_document: ApprovedJobDocument,
        approved_revision: int,
    ) -> WorkspaceManifest:
        """Apply one persisted, exact Store rebase and advance its baseline.

        The plan is intentionally accepted as a small protocol instead of an
        import from ``workspace_authority``.  That keeps the Store owner below
        the authority policy and lets recovery replay the same bytes without
        reconstructing a review payload.
        """

        if approved_document.document_id != self.document_id:
            raise ValueError("approved document scope does not match workspace")
        if approved_revision < 0:
            raise ValueError("approved_revision must be non-negative")

        current = await self.read_snapshot()
        actual_digest = workspace_resource_digest(current.files)
        expected_digest = plan.expected_workspace_digest
        result_digest = plan.result_workspace_digest
        baseline_digest = approved_document_digest(approved_document)
        if (
            current.manifest.approved_baseline_revision == approved_revision
            and current.manifest.approved_baseline_digest == baseline_digest
            and (result_digest is None or actual_digest == result_digest)
        ):
            return current.manifest

        if actual_digest != expected_digest:
            if result_digest is None or actual_digest != result_digest:
                raise ValueError("workspace changed before its persisted rebase")
            manifest = current.manifest.model_copy(
                update={
                    "generation": current.manifest.generation + 1,
                    "approved_baseline_revision": approved_revision,
                    "approved_baseline_digest": baseline_digest,
                    "validation_status": WorkspaceValidationStatus.UNVALIDATED,
                    "diagnostics": (),
                }
            )
            await self._put_manifest(manifest)
            return manifest

        files = dict(current.files)
        for change in plan.changes:
            before = files.get(change.path)
            if before != change.before:
                raise ValueError(f"workspace rebase before value changed: {change.path}")
            if change.after is None:
                if before is not None:
                    result = await self.backend.adelete(change.path)
                    if result.error is not None:
                        raise RuntimeError(result.error)
                    files.pop(change.path, None)
            else:
                result = await self.backend.awrite(change.path, change.after)
                if result.error is not None:
                    raise RuntimeError(result.error)
                files[change.path] = change.after

        after = await self.read_snapshot()
        after_digest = workspace_resource_digest(after.files)
        if result_digest is not None and after_digest != result_digest:
            raise ValueError("workspace rebase produced an unexpected digest")
        manifest = after.manifest.model_copy(
            update={
                "generation": after.manifest.generation + 1,
                "resource_digest": after_digest,
                "approved_baseline_revision": approved_revision,
                "approved_baseline_digest": baseline_digest,
                "validation_status": WorkspaceValidationStatus.UNVALIDATED,
                "diagnostics": (),
            }
        )
        await self._put_manifest(manifest)
        return manifest

    async def _manifest(self) -> WorkspaceManifest | None:
        item = await self.store.aget(
            workspace_metadata_namespace(self.document_id),
            _MANIFEST_KEY,
        )
        if item is None:
            return None
        return WorkspaceManifest.model_validate(item.value["manifest"])

    async def _put_manifest(self, manifest: WorkspaceManifest) -> None:
        await self.store.aput(
            workspace_metadata_namespace(self.document_id),
            _MANIFEST_KEY,
            {"manifest": manifest.model_dump(mode="json")},
        )

    async def _read_files(self) -> dict[str, str]:
        result = await self.backend.aglob("**/*", "/workspace")
        if result.error is not None:
            raise RuntimeError(result.error)
        files: dict[str, str] = {}
        for info in sorted(result.matches or [], key=lambda value: value["path"]):
            path = info["path"]
            read = await self.backend.aread(path)
            if read.error is not None:
                raise RuntimeError(read.error)
            if read.file_data is None:
                raise RuntimeError(f"workspace file has no content: {path}")
            files[path] = file_data_to_string(read.file_data)
        return files


def approved_document_digest(document: ApprovedJobDocument) -> Sha256Digest:
    encoded = json.dumps(
        document.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return cast(Sha256Digest, sha256(encoded).hexdigest())


_approved_document_digest = approved_document_digest


def workspace_resource_digest(files: Mapping[str, str | bytes]) -> Sha256Digest:
    """Hash exact workspace resource bytes with deterministic path ordering."""

    digest = sha256()
    for path, raw in sorted(files.items(), key=lambda item: str(item[0])):
        path_bytes = str(path).encode("utf-8")
        raw_bytes = raw.encode("utf-8") if isinstance(raw, str) else raw
        digest.update(path_bytes)
        digest.update(b"\0")
        digest.update(raw_bytes)
        digest.update(b"\0")
    return cast(Sha256Digest, digest.hexdigest())
