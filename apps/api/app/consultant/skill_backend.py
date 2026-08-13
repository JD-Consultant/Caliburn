"""Traversal-safe package-resource backend for consultant method Skills."""

from __future__ import annotations

from importlib.resources import files
from pathlib import PurePosixPath
from threading import Lock

from deepagents.backends import BackendProtocol
from deepagents.backends.protocol import (
    EditResult,
    FileDownloadResponse,
    FileUploadResponse,
    LsResult,
    ReadResult,
    WriteResult,
)
from deepagents.backends.utils import slice_read_response


CONSULTANT_SKILL_IDS = (
    "work-discovery",
    "story-interview",
    "task-boundary",
    "duty-grouping",
    "output",
    "performance-indicator",
    "knowledge",
    "skill",
    "completion-red-team",
)


def skill_path(skill_id: str) -> str:
    if skill_id not in CONSULTANT_SKILL_IDS:
        raise ValueError(f"unknown consultant Skill: {skill_id}")
    return f"/skills/{skill_id}/SKILL.md"


def load_packaged_skill_text(skill_id: str) -> str:
    skill_path(skill_id)
    resource = (
        files("app.consultant")
        .joinpath("skills")
        .joinpath(skill_id)
        .joinpath("SKILL.md")
    )
    return resource.read_text(encoding="utf-8")


class PackageSkillBackend(BackendProtocol):
    """Expose only explicitly selected, versioned Skill resources.

    Metadata discovery uses ``download_files``.  A model's full ``read_file``
    access goes through ``read`` and is limited to one successful full load per
    selected Skill in each interactive invocation.
    """

    def __init__(self, selected_skill_ids: tuple[str, ...]) -> None:
        if len(selected_skill_ids) != len(set(selected_skill_ids)):
            raise ValueError("duplicate selected consultant Skill")
        unknown = set(selected_skill_ids) - set(CONSULTANT_SKILL_IDS)
        if unknown:
            raise ValueError(f"unknown consultant Skills: {sorted(unknown)}")
        self._selected_skill_ids = selected_skill_ids
        self._contents = {
            skill_id: load_packaged_skill_text(skill_id)
            for skill_id in selected_skill_ids
        }
        self._read_counts = {skill_id: 0 for skill_id in selected_skill_ids}
        self._read_lock = Lock()

    @property
    def selected_skill_ids(self) -> tuple[str, ...]:
        return self._selected_skill_ids

    @property
    def loaded_skill_ids(self) -> tuple[str, ...]:
        with self._read_lock:
            return tuple(
                skill_id
                for skill_id in self._selected_skill_ids
                if self._read_counts[skill_id] > 0
            )

    def begin_run(self) -> None:
        """Reset model-read receipts for a newly assembled interactive run."""

        with self._read_lock:
            self._read_counts = {
                skill_id: 0 for skill_id in self._selected_skill_ids
            }

    def ls(self, path: str) -> LsResult:
        if path.rstrip("/") != "/skills" or not _is_safe_absolute_path(path):
            return LsResult(error="permission denied: only /skills can be listed")
        return LsResult(
            entries=[
                {
                    "path": f"/skills/{skill_id}/",
                    "is_dir": True,
                    "size": 0,
                    "modified_at": "",
                }
                for skill_id in sorted(self._selected_skill_ids)
            ]
        )

    def read(
        self,
        file_path: str,
        offset: int = 0,
        limit: int = 2000,
    ) -> ReadResult:
        skill_id = self._selected_skill_for_path(file_path)
        if skill_id is None:
            return ReadResult(error="permission denied: Skill was not selected")
        line_count = len(self._contents[skill_id].splitlines())
        if offset != 0 or limit < line_count:
            return ReadResult(
                error=(
                    "Skill must be loaded once in full with offset=0 and a "
                    f"limit of at least {line_count} lines"
                )
            )
        with self._read_lock:
            if self._read_counts[skill_id] >= 1:
                return ReadResult(error=f"Skill '{skill_id}' was already loaded")
            self._read_counts[skill_id] += 1
        return slice_read_response(
            {"content": self._contents[skill_id], "encoding": "utf-8"},
            offset,
            limit,
        )

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        responses: list[FileDownloadResponse] = []
        for path in paths:
            skill_id = self._selected_skill_for_path(path)
            if skill_id is None:
                responses.append(
                    FileDownloadResponse(
                        path=path,
                        error="permission_denied",
                    )
                )
            else:
                responses.append(
                    FileDownloadResponse(
                        path=path,
                        content=self._contents[skill_id].encode("utf-8"),
                    )
                )
        return responses

    def write(self, file_path: str, content: str) -> WriteResult:
        del file_path, content
        return WriteResult(error="permission denied: consultant Skills are read-only")

    def edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> EditResult:
        del file_path, old_string, new_string, replace_all
        return EditResult(error="permission denied: consultant Skills are read-only")

    def upload_files(
        self, files_to_upload: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        return [
            FileUploadResponse(path=path, error="permission_denied")
            for path, _content in files_to_upload
        ]

    def _selected_skill_for_path(self, path: str) -> str | None:
        if not _is_safe_absolute_path(path):
            return None
        for skill_id in self._selected_skill_ids:
            if path == skill_path(skill_id):
                return skill_id
        return None


def _is_safe_absolute_path(path: str) -> bool:
    if not path.startswith("/") or "\\" in path:
        return False
    parts = PurePosixPath(path).parts
    return ".." not in parts and "." not in parts
