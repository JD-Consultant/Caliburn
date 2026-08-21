"""Scoped Deep Agents backends for the consultant virtual JD workspace.

The framework owns generic file operations.  This module only supplies the
application projections and the policy that keeps the candidate state inside
the current run.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from deepagents.backends import BackendProtocol, CompositeBackend, StateBackend
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
    project_candidate_files,
)


_HANDLE_PATTERN = r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*-[0-9]{3,}"
_CANDIDATE_ENTITY = re.compile(
    rf"(?:duties|tasks)/{_HANDLE_PATTERN}\.json"
    rf"|opks/(?:o|p|k|s)/{_HANDLE_PATTERN}\.json"
)
_CANDIDATE_DOCUMENT = {"header.json", "review-groups.json"}


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


class PendingProjectionBackend(_StaticProjectionBackend):
    """Expose pending review memory without merging it into approved content."""

    def __init__(self, catalog: WorkspaceCatalog) -> None:
        super().__init__(_pending_files(catalog))


def _canonical_document_files(catalog: WorkspaceCatalog) -> dict[str, str]:
    projection_run = UUID("00000000-0000-0000-0000-000000000000")
    candidate_files = project_candidate_files(catalog, run_id=projection_run)
    prefix = f"/candidate/{projection_run}"
    return {
        path.removeprefix(prefix) or "/": content
        for path, content in candidate_files.items()
        if not path.endswith("/review-groups.json")
    }


def _pending_files(catalog: WorkspaceCatalog) -> dict[str, str]:
    changesets = sorted(
        catalog.pending,
        key=lambda item: (item.created_revision, str(item.changeset_id)),
    )
    contents: dict[str, str] = {
        "/index.json": _json_text(
            {
                "status": "pending",
                "changeset_ids": [str(item.changeset_id) for item in changesets],
            }
        )
    }
    for changeset in changesets:
        changeset_path = f"/changesets/{changeset.changeset_id}.json"
        contents[changeset_path] = _json_text(changeset.model_dump(mode="json"))
        for action in changeset.actions:
            action_path = (
                f"/changesets/{changeset.changeset_id}/actions/{action.action_id}.json"
            )
            contents[action_path] = _json_text(action.model_dump(mode="json"))
    return contents


class CandidatePolicyBackend(BackendProtocol):
    """Enforce Caliburn's narrow candidate policy over StateBackend."""

    def __init__(
        self,
        backend: StateBackend,
        *,
        run_id: UUID,
        initial_paths: Sequence[str] = (),
    ) -> None:
        if not isinstance(run_id, UUID):
            raise TypeError("candidate run_id must be a UUID")
        self._backend = backend
        self.run_id = run_id
        self.initial_paths = tuple(initial_paths)
        self._mutation_lock = threading.Lock()
        for path in self.initial_paths:
            error = self._file_policy(path)
            if error is not None:
                raise ValueError(error)

    @property
    def state_backend(self) -> StateBackend:
        return self._backend

    @property
    def _run_root(self) -> str:
        return f"/candidate/{self.run_id}"

    @property
    def _run_prefix(self) -> str:
        return f"{self._run_root}/"

    def _file_policy(self, path: str) -> str | None:
        if not _safe_absolute_path(path):
            return "permission denied: candidate path must be an absolute POSIX path"
        if not path.startswith(self._run_prefix):
            return "permission denied: path is outside the current candidate run"
        relative = path[len(self._run_prefix) :]
        if not relative or relative.endswith("/"):
            return "permission denied: candidate path must identify one resource file"
        if relative in _CANDIDATE_DOCUMENT or _CANDIDATE_ENTITY.fullmatch(relative):
            return None
        return "permission denied: invalid candidate resource path"

    def validate_candidate_file_path(self, path: str) -> str:
        """Return a framework-canonical current-run resource path or reject it."""

        try:
            canonical = validate_path(path)
        except (TypeError, ValueError) as error:
            raise ValueError(f"permission denied: invalid candidate path: {error}") from error
        error = self._file_policy(canonical)
        if error is not None:
            raise ValueError(error)
        return canonical

    def _scope_policy(self, path: str) -> str | None:
        if not _safe_absolute_path(path):
            return "permission denied: candidate path must be an absolute POSIX path"
        if path == "/":
            return None
        if path in {"/candidate", "/candidate/", self._run_root, self._run_prefix}:
            return None
        if path.startswith(self._run_prefix):
            return None
        return "permission denied: path is outside the current candidate run"

    def _search_path(self, path: str | None) -> tuple[str | None, str | None]:
        if path is None or path in {"/", "/candidate", "/candidate/"}:
            return self._run_prefix, None
        error = self._scope_policy(path)
        if error is not None:
            return None, error
        return path, None

    def _filter_ls(self, entries: list[FileInfo] | None) -> list[FileInfo]:
        result: list[FileInfo] = []
        for entry in entries or []:
            path = entry.get("path", "")
            if path == "/candidate/" or path.startswith(self._run_prefix):
                result.append(entry)
        if not any(entry.get("path") == "/candidate/" for entry in result):
            result.insert(
                0,
                {
                    "path": "/candidate/",
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
        relative = file_path[len(self._run_prefix) :]
        if relative in _CANDIDATE_DOCUMENT:
            return DeleteResult(
                error="permission denied: candidate document resource cannot be deleted"
            )
        with self._mutation_lock:
            return self._backend.delete(file_path)

    async def adelete(self, file_path: str) -> DeleteResult:
        error = self._file_policy(file_path)
        if error is not None:
            return DeleteResult(error=error)
        relative = file_path[len(self._run_prefix) :]
        if relative in _CANDIDATE_DOCUMENT:
            return DeleteResult(
                error="permission denied: candidate document resource cannot be deleted"
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
    """All backends and state inputs for one consultant run."""

    composite_backend: CompositeBackend
    skill_backend: PackageSkillBackend
    candidate_state_backend: StateBackend
    candidate_backend: CandidatePolicyBackend
    source_backend: EmployeeSourceProjectionBackend
    approved_backend: ApprovedProjectionBackend
    pending_backend: PendingProjectionBackend
    catalog: WorkspaceCatalog
    run_id: UUID
    document_id: UUID
    initial_files: dict[str, FileData]

    @property
    def backend(self) -> CompositeBackend:
        return self.composite_backend

    @property
    def current_run_catalog(self) -> WorkspaceCatalog:
        return self.catalog

    @property
    def candidate_files(self) -> dict[str, FileData]:
        return self.initial_files

    @property
    def initial_candidate_files(self) -> dict[str, str]:
        """Return canonical contents for the LangGraph ``files`` initializer."""

        return {
            path: file_data_to_string(file_data)
            for path, file_data in self.initial_files.items()
        }


def build_consultant_workspace_backend(
    *,
    runtime: PostgresConsultantRuntime,
    document_id: UUID,
    run_id: UUID,
    catalog: WorkspaceCatalog,
    selected_skill_ids: tuple[str, ...],
    source_lookup: DocumentSourceLookup | None = None,
) -> ConsultantWorkspaceBackendBinding:
    """Build the single five-root composite backend for one run."""

    if not isinstance(document_id, UUID) or not isinstance(run_id, UUID):
        raise TypeError("document_id and run_id must be UUID values")
    if catalog.document_id != document_id:
        raise ValueError("workspace catalog document scope does not match document_id")

    candidate_contents = project_candidate_files(catalog, run_id=run_id)
    initial_files = _file_data_map(candidate_contents)
    candidate_state_backend = StateBackend()
    candidate_backend = CandidatePolicyBackend(
        candidate_state_backend,
        run_id=run_id,
        initial_paths=tuple(candidate_contents),
    )
    skill_backend = PackageSkillBackend(selected_skill_ids)
    lookup = source_lookup or DocumentSourceLookup(runtime)
    source_backend = EmployeeSourceProjectionBackend(
        lookup,
        document_id=document_id,
        catalog=catalog,
    )
    approved_backend = ApprovedProjectionBackend(catalog)
    pending_backend = PendingProjectionBackend(catalog)
    composite_backend = CompositeBackend(
        default=candidate_backend,
        routes={
            "/skills/": skill_backend,
            "/sources/": source_backend,
            "/approved/": approved_backend,
            "/pending/": pending_backend,
        },
    )
    return ConsultantWorkspaceBackendBinding(
        composite_backend=composite_backend,
        skill_backend=skill_backend,
        candidate_state_backend=candidate_state_backend,
        candidate_backend=candidate_backend,
        source_backend=source_backend,
        approved_backend=approved_backend,
        pending_backend=pending_backend,
        catalog=catalog,
        run_id=run_id,
        document_id=document_id,
        initial_files=initial_files,
    )
