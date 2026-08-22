"""Scoped Deep Agents backends for the consultant virtual JD workspace.

The framework owns generic file operations.  This module only supplies the
application projections and the policy that keeps the working draft inside
the one document-scoped workspace.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections.abc import Awaitable, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from deepagents.backends import BackendProtocol, CompositeBackend, StoreBackend
from deepagents.backends.protocol import (
    DeleteResult,
    EditResult,
    FileData,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GlobResult,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)
from deepagents.backends.utils import (
    _glob_search_files,
    create_file_data,
    file_data_to_string,
    grep_matches_from_files,
    slice_read_response,
    validate_path,
)

from app.adapters.langgraph.postgres import PostgresConsultantRuntime
from app.consultant.context import DocumentSourceLookup
from app.consultant.skill_backend import PackageSkillBackend
from app.consultant.state import EmployeeSource
from app.consultant.workspace_resources import (
    WorkspaceCatalog,
    project_workspace_files,
)
from app.consultant.workspace_review import (
    WorkspaceReviewDecision,
    derive_workspace_review,
    workspace_review_files,
)
from app.consultant.workspace_state import (
    StoreBackedWorkspace,
    WorkspaceDiagnostic,
    WorkspaceValidationStatus,
    approved_document_digest,
)
from app.consultant.workspace_validation import (
    active_conflict_diagnostics,
    WorkspacePayloadValidation,
    evidence_basis_digest,
    validate_workspace_payload,
)


_HANDLE_PATTERN = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-[0-9]{3,}"
_WORKSPACE_ENTITY = re.compile(
    rf"(?:duties|tasks)/{_HANDLE_PATTERN}\.json"
    rf"|opks/(?:o|p|k|s)/{_HANDLE_PATTERN}\.json"
)
_WORKSPACE_DOCUMENT = {"header.json"}


def _safe_absolute_path(path: str) -> bool:
    if not isinstance(path, str) or not path.startswith("/"):
        return False
    if path.startswith("//") or "\\" in path:
        return False
    parts = PurePosixPath(path).parts
    return "." not in parts and ".." not in parts


def _normalized_directory(path: str) -> str:
    return path.rstrip("/") or "/"


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _file_data_map(contents: Mapping[str, str]) -> dict[str, FileData]:
    return {path: create_file_data(content) for path, content in contents.items()}


class _StaticProjectionBackend(BackendProtocol):
    """Read-only, mount-relative projection over application-created text."""

    def __init__(self, contents: Mapping[str, str]) -> None:
        self._files = _file_data_map(contents)

    def ls(self, path: str) -> LsResult:
        if not _safe_absolute_path(path):
            return LsResult(error="permission denied: invalid projection path")
        root = _normalized_directory(path)
        prefix = "/" if root == "/" else f"{root}/"
        entries: list[FileInfo] = []
        subdirectories: set[str] = set()
        for file_path, file_data in self._files.items():
            if not file_path.startswith(prefix):
                continue
            relative = file_path[len(prefix) :]
            if "/" in relative:
                subdirectories.add(f"{prefix}{relative.split('/', 1)[0]}/")
                continue
            entries.append(
                {
                    "path": file_path,
                    "is_dir": False,
                    "size": len(file_data_to_string(file_data)),
                    "modified_at": file_data.get("modified_at", ""),
                }
            )
        entries.extend(
            {
                "path": directory,
                "is_dir": True,
                "size": 0,
                "modified_at": "",
            }
            for directory in sorted(subdirectories)
        )
        entries.sort(key=lambda item: item.get("path", ""))
        return LsResult(entries=entries)

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        if not _safe_absolute_path(file_path):
            return ReadResult(error="permission denied: invalid projection path")
        file_data = self._files.get(file_path)
        if file_data is None:
            return ReadResult(error=f"File '{file_path}' not found")
        return slice_read_response(file_data, offset, limit)

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        if path is not None and not _safe_absolute_path(path):
            return GrepResult(error="permission denied: invalid projection path")
        return grep_matches_from_files(
            self._files,
            pattern,
            path,
            glob,
            max_count=max_count,
        )

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        if path is not None and not _safe_absolute_path(path):
            return GlobResult(error="permission denied: invalid projection path")
        result = _glob_search_files(self._files, pattern, path)
        if result == "No files found":
            return GlobResult(matches=[])
        matches: list[FileInfo] = []
        for file_path in result.splitlines():
            file_data = self._files[file_path]
            matches.append(
                {
                    "path": file_path,
                    "is_dir": False,
                    "size": len(file_data_to_string(file_data)),
                    "modified_at": file_data.get("modified_at", ""),
                }
            )
        return GlobResult(matches=matches)

    def write(self, file_path: str, content: str) -> WriteResult:
        del content
        return _read_only_write_result(file_path)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        del old_string, new_string, replace_all
        if not _safe_absolute_path(file_path):
            return EditResult(error="permission denied: invalid projection path")
        return EditResult(error="permission denied: projection is read-only")

    def delete(self, file_path: str) -> DeleteResult:
        if not _safe_absolute_path(file_path):
            return DeleteResult(error="permission denied: invalid projection path")
        return DeleteResult(error="permission denied: projection is read-only")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            if not _safe_absolute_path(path):
                responses.append(
                    FileDownloadResponse(
                        path=path,
                        error="permission_denied",
                    )
                )
                continue
            file_data = self._files.get(path)
            responses.append(
                FileDownloadResponse(
                    path=path,
                    content=(
                        file_data_to_string(file_data).encode("utf-8")
                        if file_data is not None
                        else None
                    ),
                    error=None if file_data is not None else "file_not_found",
                )
            )
        return responses

    def upload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return [
            FileUploadResponse(path=path, error="permission_denied")
            for path, _content in files
        ]


def _read_only_write_result(path: str) -> WriteResult:
    if not _safe_absolute_path(path):
        return WriteResult(error="permission denied: invalid projection path")
    return WriteResult(error="permission denied: projection is read-only")


class ApprovedProjectionBackend(_StaticProjectionBackend):
    """Expose the approved JD baseline as a mount-relative projection."""

    def __init__(self, catalog: WorkspaceCatalog) -> None:
        super().__init__(_canonical_document_files(catalog))


class WorkspaceReviewProjectionBackend(BackendProtocol):
    """Fresh, read-only semantic review over the actual Store workspace bytes."""

    def __init__(
        self,
        *,
        workspace: StoreBackedWorkspace,
        catalog: WorkspaceCatalog,
        source_lookup: DocumentSourceLookup,
        selected_skill_ids: tuple[str, ...],
        decision_loader: Callable[
            [], Awaitable[Sequence[WorkspaceReviewDecision]]
        ],
    ) -> None:
        self.workspace = workspace
        self.catalog = catalog
        self.source_lookup = source_lookup
        self.selected_skill_ids = selected_skill_ids
        self.decision_loader = decision_loader

    @staticmethod
    def _sync_unavailable() -> str:
        return "review projection requires the async backend method"

    def ls(self, path: str) -> LsResult:
        del path
        return LsResult(error=self._sync_unavailable())

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        del file_path, offset, limit
        return ReadResult(error=self._sync_unavailable())

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        del pattern, path, glob, max_count
        return GrepResult(error=self._sync_unavailable())

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        del pattern, path
        return GlobResult(error=self._sync_unavailable())

    def write(self, file_path: str, content: str) -> WriteResult:
        del content
        return _read_only_write_result(file_path)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        del old_string, new_string, replace_all
        if not _safe_absolute_path(file_path):
            return EditResult(error="permission denied: invalid projection path")
        return EditResult(error="permission denied: projection is read-only")

    def delete(self, file_path: str) -> DeleteResult:
        if not _safe_absolute_path(file_path):
            return DeleteResult(error="permission denied: invalid projection path")
        return DeleteResult(error="permission denied: projection is read-only")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [
            FileDownloadResponse(path=path, error="permission_denied") for path in paths
        ]

    def upload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return [
            FileUploadResponse(path=path, error="permission_denied")
            for path, _content in files
        ]

    def _unavailable_validation(
        self,
        *,
        code: str,
        message: str,
    ) -> WorkspacePayloadValidation:
        return WorkspacePayloadValidation(
            document=None,
            diagnostics=(
                WorkspaceDiagnostic(code=code, path="/workspace", message=message),
            ),
            current_sources=(),
            evidence_by_handle={},
            default_basis=None,
        )

    async def _files(self) -> dict[str, str]:
        # read_snapshot recomputes the digest from Store bytes and marks a
        # mismatched manifest unvalidated before any projection is built.
        snapshot = await self.workspace.read_snapshot()
        manifest = snapshot.manifest
        current_sources = await self.source_lookup.current_sources(
            self.catalog.document_id
        )
        current_catalog = WorkspaceCatalog.from_snapshot(
            self.catalog.document,
            sources=current_sources,
        )
        current_evidence_digest = evidence_basis_digest(current_sources)
        if manifest.validation_status not in {
            WorkspaceValidationStatus.VALID,
            WorkspaceValidationStatus.CONFLICTED,
        }:
            validation = self._unavailable_validation(
                code="workspace-not-valid",
                message="Workspace review requires the current Store files to validate.",
            )
        elif manifest.approved_baseline_digest != approved_document_digest(
            self.catalog.document
        ):
            validation = self._unavailable_validation(
                code="approved-baseline-stale",
                message="Workspace review baseline no longer matches the approved document.",
            )
            manifest = manifest.model_copy(
                update={"validation_status": WorkspaceValidationStatus.UNVALIDATED}
            )
        elif manifest.evidence_basis_digest != current_evidence_digest:
            validation = self._unavailable_validation(
                code="evidence-basis-stale",
                message="Workspace review Evidence changed since the last validation.",
            )
            manifest = manifest.model_copy(
                update={"validation_status": WorkspaceValidationStatus.UNVALIDATED}
            )
        else:
            validation = validate_workspace_payload(
                snapshot.files,
                catalog=current_catalog,
                selected_skill_ids=self.selected_skill_ids,
                loaded_skill_ids=self.selected_skill_ids,
            )
            active_conflicts = active_conflict_diagnostics(
                files=snapshot.files,
                approved_document=self.catalog.document,
                manifest=manifest,
            )
            if validation.document is not None:
                manifest = manifest.model_copy(
                    update={
                        "validation_status": (
                            WorkspaceValidationStatus.CONFLICTED
                            if active_conflicts
                            else WorkspaceValidationStatus.VALID
                        ),
                        "diagnostics": active_conflicts,
                    }
                )
        decisions = tuple(await self.decision_loader())
        projection = derive_workspace_review(
            self.catalog.document,
            validation,
            manifest,
            decisions,
        )
        return workspace_review_files(projection)

    async def als(self, path: str) -> LsResult:
        if not _safe_absolute_path(path):
            return LsResult(error="permission denied: invalid review path")
        return _StaticProjectionBackend(await self._files()).ls(path)

    async def aread(
        self, file_path: str, offset: int = 0, limit: int = 2000
    ) -> ReadResult:
        if not _safe_absolute_path(file_path):
            return ReadResult(error="permission denied: invalid review path")
        return _StaticProjectionBackend(await self._files()).read(
            file_path, offset=offset, limit=limit
        )

    async def agrep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        if path is not None and not _safe_absolute_path(path):
            return GrepResult(error="permission denied: invalid review path")
        return _StaticProjectionBackend(await self._files()).grep(
            pattern, path=path, glob=glob, max_count=max_count
        )

    async def aglob(self, pattern: str, path: str | None = None) -> GlobResult:
        if path is not None and not _safe_absolute_path(path):
            return GlobResult(error="permission denied: invalid review path")
        return _StaticProjectionBackend(await self._files()).glob(pattern, path)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        return self.write(file_path, content)

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        return self.edit(file_path, old_string, new_string, replace_all)

    async def adelete(self, file_path: str) -> DeleteResult:
        return self.delete(file_path)

    async def adownload_files(
        self, paths: list[str]
    ) -> list[FileDownloadResponse]:
        return _StaticProjectionBackend(await self._files()).download_files(paths)

    async def aupload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return self.upload_files(files)


def _canonical_document_files(catalog: WorkspaceCatalog) -> dict[str, str]:
    projection = project_workspace_files(
        catalog.document,
        handle_registry=catalog.handle_to_stable,
    )
    resources = {
        path.removeprefix("/workspace") or "/": content
        for path, content in projection.files.items()
    }
    relative_paths = sorted(path.lstrip("/") for path in resources)
    resources["/index.json"] = _json_text(
        {
            "approved_resource_paths": [
                f"/approved/{path}" for path in relative_paths
            ],
            "workspace_relative_resource_paths": relative_paths,
        }
    )
    return resources


class WorkspacePolicyBackend(BackendProtocol):
    """Enforce Caliburn's narrow JD workspace policy over StoreBackend."""

    def __init__(
        self,
        backend: StoreBackend,
    ) -> None:
        self._backend = backend
        self._mutation_lock = threading.Lock()

    @property
    def store_backend(self) -> StoreBackend:
        return self._backend

    @property
    def _workspace_prefix(self) -> str:
        return "/workspace/"

    def _file_policy(self, path: str) -> str | None:
        if not _safe_absolute_path(path):
            return "permission denied: workspace path must be an absolute POSIX path"
        if not path.startswith(self._workspace_prefix):
            return "permission denied: path is outside the workspace"
        relative = path[len(self._workspace_prefix) :]
        if not relative or relative.endswith("/"):
            return "permission denied: workspace path must identify one resource file"
        if relative in _WORKSPACE_DOCUMENT or _WORKSPACE_ENTITY.fullmatch(relative):
            return None
        return "permission denied: invalid workspace resource path"

    def validate_workspace_file_path(self, path: str) -> str:
        """Return a framework-canonical workspace resource path or reject it."""

        try:
            canonical = validate_path(path)
        except (TypeError, ValueError) as error:
            raise ValueError(f"permission denied: invalid workspace path: {error}") from error
        error = self._file_policy(canonical)
        if error is not None:
            raise ValueError(error)
        return canonical

    def _scope_policy(self, path: str) -> str | None:
        if not _safe_absolute_path(path):
            return "permission denied: workspace path must be an absolute POSIX path"
        if path == "/":
            return None
        if path in {"/workspace", "/workspace/"}:
            return None
        if path.startswith(self._workspace_prefix):
            return None
        return "permission denied: path is outside the workspace"

    def _search_path(self, path: str | None) -> tuple[str | None, str | None]:
        if path is None or path in {"/", "/workspace", "/workspace/"}:
            return self._workspace_prefix, None
        error = self._scope_policy(path)
        if error is not None:
            return None, error
        return path, None

    def _filter_ls(self, entries: list[FileInfo] | None) -> list[FileInfo]:
        result: list[FileInfo] = []
        for entry in entries or []:
            path = entry.get("path", "")
            if path == "/workspace/" or path.startswith(self._workspace_prefix):
                result.append(entry)
        if not any(entry.get("path") == "/workspace/" for entry in result):
            result.insert(
                0,
                {
                    "path": "/workspace/",
                    "is_dir": True,
                    "size": 0,
                    "modified_at": "",
                },
            )
        return result

    def ls(self, path: str) -> LsResult:
        error = self._scope_policy(path)
        if error is not None:
            return LsResult(error=error)
        result = self._backend.ls(path)
        if result.error:
            return result
        return LsResult(entries=self._filter_ls(result.entries))

    async def als(self, path: str) -> LsResult:
        error = self._scope_policy(path)
        if error is not None:
            return LsResult(error=error)
        result = await self._backend.als(path)
        if result.error:
            return result
        return LsResult(entries=self._filter_ls(result.entries))

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        error = self._file_policy(file_path)
        if error is not None:
            return ReadResult(error=error)
        return self._backend.read(file_path, offset=offset, limit=limit)

    async def aread(
        self, file_path: str, offset: int = 0, limit: int = 2000
    ) -> ReadResult:
        error = self._file_policy(file_path)
        if error is not None:
            return ReadResult(error=error)
        return await self._backend.aread(file_path, offset=offset, limit=limit)

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        search_path, error = self._search_path(path)
        if error is not None:
            return GrepResult(error=error)
        return self._backend.grep(pattern, search_path, glob, max_count=max_count)

    async def agrep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        search_path, error = self._search_path(path)
        if error is not None:
            return GrepResult(error=error)
        return await self._backend.agrep(
            pattern,
            search_path,
            glob,
            max_count=max_count,
        )

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        search_path, error = self._search_path(path)
        if error is not None:
            return GlobResult(error=error)
        return self._backend.glob(pattern, search_path)

    async def aglob(self, pattern: str, path: str | None = None) -> GlobResult:
        search_path, error = self._search_path(path)
        if error is not None:
            return GlobResult(error=error)
        return await self._backend.aglob(pattern, search_path)

    def write(self, file_path: str, content: str) -> WriteResult:
        error = self._file_policy(file_path)
        if error is not None:
            return WriteResult(error=error)
        with self._mutation_lock:
            return self._write_create_only(file_path, content)

    @asynccontextmanager
    async def _async_mutation_guard(self):
        while not self._mutation_lock.acquire(blocking=False):
            await asyncio.sleep(0)
        try:
            yield
        finally:
            self._mutation_lock.release()

    def _write_create_only(self, file_path: str, content: str) -> WriteResult:
        existing = self._backend.read(file_path, offset=0, limit=1)
        if existing.error is None:
            return WriteResult(
                error=f"Error: File '{file_path}' already exists; use edit_file"
            )
        if "not found" not in existing.error.casefold():
            return WriteResult(error=existing.error)
        return self._backend.write(file_path, content)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        error = self._file_policy(file_path)
        if error is not None:
            return WriteResult(error=error)
        async with self._async_mutation_guard():
            return await self._awrite_create_only(file_path, content)

    async def _awrite_create_only(
        self, file_path: str, content: str
    ) -> WriteResult:
        existing = await self._backend.aread(file_path, offset=0, limit=1)
        if existing.error is None:
            return WriteResult(
                error=f"Error: File '{file_path}' already exists; use edit_file"
            )
        if "not found" not in existing.error.casefold():
            return WriteResult(error=existing.error)
        return await self._backend.awrite(file_path, content)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        error = self._file_policy(file_path)
        if error is not None:
            return EditResult(error=error)
        if replace_all:
            return EditResult(error="Error: replace_all=True is not permitted")
        with self._mutation_lock:
            return self._backend.edit(
                file_path,
                old_string,
                new_string,
                replace_all=False,
            )

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        error = self._file_policy(file_path)
        if error is not None:
            return EditResult(error=error)
        if replace_all:
            return EditResult(error="Error: replace_all=True is not permitted")
        async with self._async_mutation_guard():
            return await self._backend.aedit(
                file_path,
                old_string,
                new_string,
                replace_all=False,
            )

    def delete(self, file_path: str) -> DeleteResult:
        error = self._file_policy(file_path)
        if error is not None:
            return DeleteResult(error=error)
        relative = file_path[len(self._workspace_prefix) :]
        if relative in _WORKSPACE_DOCUMENT:
            return DeleteResult(
                error="permission denied: workspace header cannot be deleted"
            )
        with self._mutation_lock:
            return self._backend.delete(file_path)

    async def adelete(self, file_path: str) -> DeleteResult:
        error = self._file_policy(file_path)
        if error is not None:
            return DeleteResult(error=error)
        relative = file_path[len(self._workspace_prefix) :]
        if relative in _WORKSPACE_DOCUMENT:
            return DeleteResult(
                error="permission denied: workspace header cannot be deleted"
            )
        async with self._async_mutation_guard():
            return await self._backend.adelete(file_path)

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        invalid = [path for path in paths if self._file_policy(path) is not None]
        if invalid:
            return [
                FileDownloadResponse(path=path, error="permission_denied")
                for path in paths
            ]
        return self._backend.download_files(paths)

    async def adownload_files(
        self, paths: list[str]
    ) -> list[FileDownloadResponse]:
        invalid = [path for path in paths if self._file_policy(path) is not None]
        if invalid:
            return [
                FileDownloadResponse(path=path, error="permission_denied")
                for path in paths
            ]
        return await self._backend.adownload_files(paths)

    def upload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return [
            FileUploadResponse(path=path, error="permission_denied")
            for path, _content in files
        ]

    async def aupload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return self.upload_files(files)


class EmployeeSourceProjectionBackend(BackendProtocol):
    """Lazily expose one document's current sources and correction lineages."""

    def __init__(
        self,
        lookup: DocumentSourceLookup,
        *,
        document_id: UUID,
        catalog: WorkspaceCatalog,
    ) -> None:
        self.lookup = lookup
        self.document_id = document_id
        self.catalog = catalog

    def _sync_unavailable(self) -> str:
        return "source projection requires the async backend method"

    def ls(self, path: str) -> LsResult:
        return LsResult(error=self._sync_unavailable())

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        del offset, limit
        return ReadResult(error=self._sync_unavailable())

    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        del pattern, path, glob, max_count
        return GrepResult(error=self._sync_unavailable())

    def glob(self, pattern: str, path: str | None = None) -> GlobResult:
        del pattern, path
        return GlobResult(error=self._sync_unavailable())

    def write(self, file_path: str, content: str) -> WriteResult:
        del content
        return _read_only_write_result(file_path)

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        del old_string, new_string, replace_all
        if not _safe_absolute_path(file_path):
            return EditResult(error="permission denied: invalid projection path")
        return EditResult(error="permission denied: projection is read-only")

    def delete(self, file_path: str) -> DeleteResult:
        if not _safe_absolute_path(file_path):
            return DeleteResult(error="permission denied: invalid projection path")
        return DeleteResult(error="permission denied: projection is read-only")

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [
            FileDownloadResponse(path=path, error="permission_denied")
            for path in paths
        ]

    def upload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return [
            FileUploadResponse(path=path, error="permission_denied")
            for path, _content in files
        ]

    async def _files(self, *, include_lineages: bool) -> dict[str, str]:
        current = await self.lookup.current_sources(self.document_id)
        contents: dict[str, str] = {}
        for source in current:
            handle = self.catalog.handle_for_id(source.source_id)
            contents[f"/current/{handle}.txt"] = source.text
            contents[f"/current/{handle}.json"] = _json_text(
                _source_metadata(self.catalog, source)
            )
            if not include_lineages:
                continue
            lineage = await self.lookup.lineage(self.document_id, source.source_id)
            for revision, item in enumerate(lineage, start=1):
                root = f"/lineages/{handle}/{revision:03d}"
                contents[f"{root}.txt"] = item.text
                contents[f"{root}.json"] = _json_text(
                    {
                        "lineage_handle": handle,
                        "revision": revision,
                        **_source_metadata(self.catalog, item),
                    }
                )
        return contents

    async def als(self, path: str) -> LsResult:
        if not _safe_absolute_path(path):
            return LsResult(error="permission denied: invalid source path")
        return _StaticProjectionBackend(
            await self._files(include_lineages=True)
        ).ls(path)

    async def aread(
        self, file_path: str, offset: int = 0, limit: int = 2000
    ) -> ReadResult:
        if not _safe_absolute_path(file_path):
            return ReadResult(error="permission denied: invalid source path")
        return _StaticProjectionBackend(
            await self._files(include_lineages=True)
        ).read(file_path, offset=offset, limit=limit)

    async def agrep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
    ) -> GrepResult:
        if path is not None and not _safe_absolute_path(path):
            return GrepResult(error="permission denied: invalid source path")
        normalized = _normalized_directory(path or "/")
        if normalized not in {"/", "/current"} and not normalized.startswith(
            "/current/"
        ):
            return GrepResult(
                error="permission denied: lexical grep only searches current sources"
            )
        contents = await self._files(include_lineages=False)
        return _StaticProjectionBackend(contents).grep(
            pattern,
            path=path,
            glob=glob,
            max_count=max_count,
        )

    async def aglob(self, pattern: str, path: str | None = None) -> GlobResult:
        if path is not None and not _safe_absolute_path(path):
            return GlobResult(error="permission denied: invalid source path")
        return _StaticProjectionBackend(
            await self._files(include_lineages=True)
        ).glob(pattern, path)

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        del content
        return _read_only_write_result(file_path)

    async def aedit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        del old_string, new_string, replace_all
        if not _safe_absolute_path(file_path):
            return EditResult(error="permission denied: invalid projection path")
        return EditResult(error="permission denied: projection is read-only")

    async def adelete(self, file_path: str) -> DeleteResult:
        if not _safe_absolute_path(file_path):
            return DeleteResult(error="permission denied: invalid projection path")
        return DeleteResult(error="permission denied: projection is read-only")

    async def adownload_files(
        self, paths: list[str]
    ) -> list[FileDownloadResponse]:
        contents = _file_data_map(await self._files(include_lineages=True))
        result: list[FileDownloadResponse] = []
        for path in paths:
            file_data = contents.get(path)
            result.append(
                FileDownloadResponse(
                    path=path,
                    content=(
                        file_data_to_string(file_data).encode("utf-8")
                        if file_data is not None
                        else None
                    ),
                    error=None if file_data is not None else "file_not_found",
                )
            )
        return result

    async def aupload_files(
        self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return self.upload_files(files)


def _source_metadata(catalog: WorkspaceCatalog, source: EmployeeSource) -> dict[str, Any]:
    def handle_for(source_id: UUID | None) -> str | None:
        if source_id is None:
            return None
        try:
            return catalog.handle_for_id(source_id)
        except KeyError:
            return None

    return {
        "source_id": str(source.source_id),
        "source_handle": catalog.handle_for_id(source.source_id),
        "kind": source.kind.value,
        "speaker": source.speaker,
        "text_sha256": source.text_sha256,
        "created_at": source.created_at.isoformat(),
        "processing_status": source.processing_status.value,
        "validity": source.validity.value,
        "supersedes_source_handle": handle_for(source.supersedes_source_id),
        "superseded_by_source_handle": handle_for(source.superseded_by_source_id),
    }


@dataclass(frozen=True, slots=True)
class ConsultantWorkspaceBackendBinding:
    """All backends for one document-scoped consultant workspace."""

    composite_backend: CompositeBackend
    skill_backend: PackageSkillBackend
    workspace: StoreBackedWorkspace
    workspace_backend: WorkspacePolicyBackend
    source_backend: EmployeeSourceProjectionBackend
    approved_backend: ApprovedProjectionBackend
    review_backend: WorkspaceReviewProjectionBackend
    catalog: WorkspaceCatalog
    document_id: UUID

    @property
    def backend(self) -> CompositeBackend:
        return self.composite_backend


def build_consultant_workspace_backend(
    *,
    runtime: PostgresConsultantRuntime,
    document_id: UUID,
    workspace: StoreBackedWorkspace,
    catalog: WorkspaceCatalog,
    selected_skill_ids: tuple[str, ...],
    source_lookup: DocumentSourceLookup | None = None,
) -> ConsultantWorkspaceBackendBinding:
    """Build the single five-root composite backend for one active workspace."""

    if not isinstance(document_id, UUID):
        raise TypeError("document_id must be a UUID value")
    if catalog.document_id != document_id:
        raise ValueError("workspace catalog document scope does not match document_id")
    if workspace.document_id != document_id:
        raise ValueError("Store-backed workspace scope does not match document_id")

    workspace_backend = WorkspacePolicyBackend(workspace.backend)
    skill_backend = PackageSkillBackend(selected_skill_ids)
    lookup = source_lookup or DocumentSourceLookup(runtime)
    source_backend = EmployeeSourceProjectionBackend(
        lookup,
        document_id=document_id,
        catalog=catalog,
    )
    approved_backend = ApprovedProjectionBackend(catalog)

    async def load_review_decisions() -> Sequence[WorkspaceReviewDecision]:
        return await runtime.workspace_review_decisions(document_id)

    review_backend = WorkspaceReviewProjectionBackend(
        workspace=workspace,
        catalog=catalog,
        source_lookup=lookup,
        selected_skill_ids=selected_skill_ids,
        decision_loader=load_review_decisions,
    )
    composite_backend = CompositeBackend(
        default=workspace_backend,
        routes={
            "/skills/": skill_backend,
            "/sources/": source_backend,
            "/approved/": approved_backend,
            "/review/": review_backend,
        },
    )
    return ConsultantWorkspaceBackendBinding(
        composite_backend=composite_backend,
        skill_backend=skill_backend,
        workspace=workspace,
        workspace_backend=workspace_backend,
        source_backend=source_backend,
        approved_backend=approved_backend,
        review_backend=review_backend,
        catalog=catalog,
        document_id=document_id,
    )
